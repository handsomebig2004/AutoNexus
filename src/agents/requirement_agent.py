"""Requirement understanding agent.

What this file does:
    Converts a normalized UserRequest into a validated TaskDefinition.

How it works:
    RequirementAgent reads the fixed prompt, calls LLMClient, extracts JSON from
    the response, validates it with TaskDefinition, writes the result if an
    output path is provided, and records task/LLM logs when a TaskLogger is
    supplied.

How to call it:
    from src.agents.requirement_agent import RequirementAgent

    agent = RequirementAgent()
    task_definition = agent.run(user_request)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.schemas.requirement import TaskDefinition
from src.schemas.user_request import UserRequest
from src.tools.llm_client import LLMClient
from src.utils.errors import LLMOutputParseError
from src.utils.ids import next_llm_call_id
from src.utils.io import read_text, write_json
from src.utils.log_events import EventTimer, build_error_data
from src.utils.task_logger import TaskLogger
from src.utils.text import parse_json_from_text


class RequirementAgent:
    """LLM-backed gatekeeper for deciding whether a task can enter modeling."""

    agent_name = "requirement_agent"

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        prompt_path: str | Path = "src/prompts/requirement_agent.md",
        task_logger: TaskLogger | None = None,
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.prompt_path = Path(prompt_path)
        self.task_logger = task_logger

    def run(
        self,
        user_request: UserRequest,
        *,
        output_path: str | Path | None = None,
    ) -> TaskDefinition:
        """Run requirement understanding and return a validated TaskDefinition."""
        timer = EventTimer.start()
        self._log_info(
            "agent_started",
            message="Requirement agent started.",
            data={
                "source": user_request.source,
                "source_path": user_request.source_path,
            },
        )

        prompt = self._build_prompt(user_request)
        llm_call_id = self._next_llm_call_id()

        try:
            response = self.llm_client.generate(
                prompt,
                system_prompt="You are AutoNexus requirement_agent. Return strict JSON only.",
            )
            self._log_llm_call(
                llm_call_id=llm_call_id,
                prompt=prompt,
                response=response,
                status="success",
            )

            parsed = parse_json_from_text(response)
            if isinstance(parsed, dict):
                parsed["raw_user_request"] = user_request.request_text
            task_definition = TaskDefinition.model_validate(parsed)
        except (ValueError, ValidationError, TypeError) as exc:
            if "response" not in locals():
                self._log_llm_call(
                    llm_call_id=llm_call_id,
                    prompt=prompt,
                    response=None,
                    status="failed",
                    error=build_error_data(exc),
                )
            wrapped = LLMOutputParseError(
                f"Failed to parse requirement_agent output: {exc}"
            )
            self._log_error(
                "agent_failed",
                wrapped,
                message="Requirement agent failed to parse or validate LLM output.",
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
                message="Requirement agent failed.",
                data={"duration_seconds": timer.elapsed_seconds()},
            )
            raise

        if output_path:
            write_json(output_path, task_definition.to_json_dict())

        self._log_info(
            "agent_finished",
            message="Requirement agent finished.",
            data={
                "decision": task_definition.decision,
                "task_type": task_definition.task_type,
                "should_model": task_definition.should_model,
                "missing_information_count": len(task_definition.missing_information),
                "output_path": str(output_path) if output_path else None,
                "duration_seconds": timer.elapsed_seconds(),
            },
        )
        return task_definition

    def _build_prompt(self, user_request: UserRequest) -> str:
        prompt_template = read_text(self.prompt_path)
        return (
            f"{prompt_template.strip()}\n\n"
            "## 用户需求\n\n"
            f"{user_request.request_text}\n\n"
            "请基于以上用户需求输出严格 JSON。"
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
            system_prompt="You are AutoNexus requirement_agent. Return strict JSON only.",
            prompt=prompt,
            response=response,
            status=status,
            error=error,
            metadata={
                "schema": "TaskDefinition",
                "prompt_path": str(self.prompt_path),
            },
        )
