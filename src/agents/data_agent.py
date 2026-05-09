"""Data preprocessing planning agent.

What this file does:
    Converts task/data context into a validated DataProcessPlan. This version
    only plans preprocessing; it does not generate or run preprocessing code.

How it works:
    DataAgent reads a fixed prompt, appends TaskDefinition, data profile,
    inferred schema, and data quality report as JSON, calls LLMClient, extracts
    JSON from the response, validates it with DataProcessPlan, writes the result
    if requested, and records logs when a TaskLogger/RunLogger is supplied.

How to call it:
    from src.agents.data_agent import DataAgent

    plan = DataAgent().run(
        task_definition=task_definition,
        data_profile=data_profile,
        inferred_schema=inferred_schema,
        quality_report=quality_report,
    )
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.schemas.data_plan import DataProcessPlan
from src.schemas.requirement import TaskDefinition
from src.tools.llm_client import LLMClient
from src.utils.errors import LLMOutputParseError
from src.utils.ids import next_llm_call_id
from src.utils.io import read_text, write_json
from src.utils.log_events import EventTimer, build_error_data
from src.utils.run_logger import RunLogger
from src.utils.task_logger import TaskLogger
from src.utils.text import parse_json_from_text


DATA_AGENT_SYSTEM_PROMPT = (
    "You are AutoNexus data_agent. Return strict JSON only. "
    "Do not generate code in this stage."
)


class DataAgent:
    """LLM-backed agent that outputs only a DataProcessPlan."""

    agent_name = "data_agent"

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        prompt_path: str | Path = "src/prompts/data_agent.md",
        task_logger: TaskLogger | None = None,
        run_logger: RunLogger | None = None,
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.prompt_path = Path(prompt_path)
        self.task_logger = task_logger
        self.run_logger = run_logger

    def run(
        self,
        *,
        task_definition: TaskDefinition | dict[str, Any],
        data_profile: dict[str, Any],
        inferred_schema: dict[str, Any] | None = None,
        quality_report: dict[str, Any] | None = None,
        output_path: str | Path | None = None,
    ) -> DataProcessPlan:
        """Run data planning and return a validated DataProcessPlan."""
        timer = EventTimer.start()
        task_definition_data = _to_json_dict(task_definition)
        self._log_info(
            "agent_started",
            message="Data agent started.",
            data={
                "task_type": task_definition_data.get("task_type"),
                "dataset_name": data_profile.get("dataset_name"),
                "output_path": str(output_path) if output_path else None,
            },
        )

        prompt = self._build_prompt(
            task_definition=task_definition_data,
            data_profile=data_profile,
            inferred_schema=inferred_schema or {},
            quality_report=quality_report or {},
        )
        llm_call_id = self._next_llm_call_id()

        try:
            response = self.llm_client.generate(
                prompt,
                system_prompt=DATA_AGENT_SYSTEM_PROMPT,
            )
            self._log_llm_call(
                llm_call_id=llm_call_id,
                prompt=prompt,
                response=response,
                status="success",
            )
            parsed = parse_json_from_text(response)
            data_plan = DataProcessPlan.model_validate(parsed)
        except (ValueError, ValidationError, TypeError) as exc:
            if "response" not in locals():
                self._log_llm_call(
                    llm_call_id=llm_call_id,
                    prompt=prompt,
                    response=None,
                    status="failed",
                    error=build_error_data(exc),
                )
            wrapped = LLMOutputParseError(f"Failed to parse data_agent output: {exc}")
            self._log_error(
                "agent_failed",
                wrapped,
                message="Data agent failed to parse or validate LLM output.",
                data={"duration_seconds": timer.elapsed_seconds()},
            )
            raise wrapped from exc
        except Exception as exc:
            self._log_llm_call(
                llm_call_id=llm_call_id,
                prompt=prompt,
                response=locals().get("response"),
                status="failed",
                error=build_error_data(exc),
            )
            self._log_error(
                "agent_failed",
                exc,
                message="Data agent failed.",
                data={"duration_seconds": timer.elapsed_seconds()},
            )
            raise

        if output_path:
            write_json(output_path, data_plan.to_json_dict())

        self._log_info(
            "agent_finished",
            message="Data agent finished.",
            data={
                "plan_name": data_plan.plan_name,
                "status": data_plan.status,
                "task_type": data_plan.task_type,
                "target_column": data_plan.target_column,
                "feature_column_count": len(data_plan.feature_columns),
                "drop_column_count": len(data_plan.drop_columns),
                "output_artifact_count": len(data_plan.output_artifacts),
                "output_path": str(output_path) if output_path else None,
                "duration_seconds": timer.elapsed_seconds(),
            },
        )
        return data_plan

    def _build_prompt(
        self,
        *,
        task_definition: dict[str, Any],
        data_profile: dict[str, Any],
        inferred_schema: dict[str, Any],
        quality_report: dict[str, Any],
    ) -> str:
        prompt_template = read_text(self.prompt_path)
        context = {
            "task_definition": task_definition,
            "data_profile": data_profile,
            "inferred_schema": inferred_schema,
            "quality_report": quality_report,
        }
        return (
            f"{prompt_template.strip()}\n\n"
            "## Context JSON\n\n"
            "```json\n"
            f"{json.dumps(context, ensure_ascii=False, indent=2)}\n"
            "```\n\n"
            "Return one strict JSON object that matches DataProcessPlan."
        )

    def _next_llm_call_id(self) -> str:
        if not self.task_logger:
            return "llm_0001"
        return next_llm_call_id(self.task_logger.llm_calls_log_path)

    def _log_info(
        self,
        event: str,
        *,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        if self.task_logger:
            self.task_logger.info(
                event,
                agent=self.agent_name,
                message=message,
                data=data,
            )
        if self.run_logger:
            self.run_logger.info(
                event,
                agent=self.agent_name,
                message=message,
                data=data,
            )

    def _log_error(
        self,
        event: str,
        exc: BaseException,
        *,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        if self.task_logger:
            self.task_logger.error(
                event,
                exc,
                agent=self.agent_name,
                message=message,
                data=data,
            )
        if self.run_logger:
            self.run_logger.error(
                event,
                exc,
                agent=self.agent_name,
                message=message,
                data=data,
            )

    def _log_llm_call(
        self,
        *,
        llm_call_id: str,
        prompt: str,
        response: str | None,
        status: str,
        error: dict[str, Any] | None = None,
    ) -> None:
        if not self.task_logger:
            return

        self.task_logger.log_llm_call(
            llm_call_id=llm_call_id,
            agent=self.agent_name,
            provider=self.llm_client.provider,
            model=self.llm_client.model_name,
            system_prompt=DATA_AGENT_SYSTEM_PROMPT,
            prompt=prompt,
            response=response,
            status=status,
            error=error,
            metadata={
                "schema": "DataProcessPlan",
                "prompt_path": str(self.prompt_path),
            },
        )


def _to_json_dict(value: TaskDefinition | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, TaskDefinition):
        return value.to_json_dict()
    return value
