"""Minimal AutoNexus pipeline runner.

What this file does:
    Provides the first orchestration layer for AutoNexus. The current runner
    only executes the requirement understanding stage, creates the task
    directory, writes task metadata, and records the task state.

How it works:
    PipelineRunner receives a normalized UserRequest, creates tasks/task_xxx,
    builds a TaskLogger, runs RequirementAgent, writes task_definition.json and
    task_state.json, then returns a PipelineResult. Downstream agents can be
    added later without changing the external input interface.

How to call it:
    from src.pipeline import PipelineRunner
    from src.schemas import UserRequest

    runner = PipelineRunner()
    result = runner.run_requirement_stage(
        UserRequest(request_text="Predict churn from customer data.", source="cli")
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from src.agents.requirement_agent import RequirementAgent
from src.schemas.requirement import TaskDefinition
from src.schemas.user_request import UserRequest
from src.utils.io import write_json
from src.utils.log_events import EventTimer, build_error_data, current_timestamp
from src.utils.numbered_paths import create_task_directory
from src.utils.task_logger import TaskLogger


class RequirementAgentLike(Protocol):
    """Small protocol used so tests can inject a fake requirement agent."""

    def run(
        self,
        user_request: UserRequest,
        *,
        output_path: str | Path | None = None,
    ) -> TaskDefinition:
        """Run requirement understanding."""


RequirementAgentFactory = Callable[[TaskLogger], RequirementAgentLike]


@dataclass(frozen=True)
class PipelineResult:
    """Result returned after the current pipeline stage finishes."""

    task_id: str
    task_dir: Path
    status: str
    current_agent: str
    task_definition: TaskDefinition
    task_state_path: Path
    task_definition_path: Path
    user_request_path: Path

    @property
    def can_continue(self) -> bool:
        """Whether downstream modeling agents may run."""
        return self.task_definition.decision == "accepted"

    @property
    def user_facing_response(self) -> str:
        """Message that can be shown to the user."""
        return self.task_definition.user_facing_response


class PipelineRunner:
    """Orchestrate AutoNexus pipeline stages."""

    def __init__(
        self,
        *,
        tasks_dir: str | Path = "tasks",
        requirement_agent_factory: RequirementAgentFactory | None = None,
    ) -> None:
        self.tasks_dir = Path(tasks_dir)
        self.requirement_agent_factory = requirement_agent_factory

    def run_requirement_stage(self, user_request: UserRequest) -> PipelineResult:
        """
        Run the current minimal pipeline: input -> requirement_agent -> task state.

        The method stops after requirement_agent because downstream agents are
        not implemented yet. If the returned result.can_continue is True, later
        versions of the pipeline can continue with research_agent/data_agent.
        """
        timer = EventTimer.start()
        task_dir = create_task_directory(self.tasks_dir)
        task_id = task_dir.name
        logger = TaskLogger(task_dir, task_id=task_id)

        user_request_path = task_dir / "user_request.json"
        task_definition_path = task_dir / "task_definition.json"
        task_state_path = task_dir / "task_state.json"

        logger.info(
            "task_created",
            agent="pipeline_runner",
            message="Task directory created.",
            data={
                "task_dir": str(task_dir),
                "source": user_request.source,
                "source_path": user_request.source_path,
            },
        )
        write_json(user_request_path, user_request.to_json_dict())

        try:
            agent = self._build_requirement_agent(logger)
            task_definition = agent.run(
                user_request,
                output_path=task_definition_path,
            )
            status = self._status_from_task_definition(task_definition)
            state = self._build_task_state(
                task_id=task_id,
                status=status,
                current_agent="requirement_agent",
                task_definition=task_definition,
                user_request=user_request,
                duration_seconds=timer.elapsed_seconds(),
            )
            write_json(task_state_path, state)

            logger.info(
                "requirement_stage_finished",
                agent="pipeline_runner",
                message="Requirement stage finished.",
                data={
                    "status": status,
                    "decision": task_definition.decision,
                    "task_type": task_definition.task_type,
                    "should_model": task_definition.should_model,
                    "can_continue": task_definition.decision == "accepted",
                    "task_state_path": str(task_state_path),
                    "task_definition_path": str(task_definition_path),
                    "duration_seconds": timer.elapsed_seconds(),
                },
            )
        except Exception as exc:
            failed_state = self._build_failed_task_state(
                task_id=task_id,
                user_request=user_request,
                exc=exc,
                duration_seconds=timer.elapsed_seconds(),
            )
            write_json(task_state_path, failed_state)
            logger.error(
                "pipeline_failed",
                exc,
                agent="pipeline_runner",
                message="Pipeline failed during requirement stage.",
                data={
                    "task_state_path": str(task_state_path),
                    "duration_seconds": timer.elapsed_seconds(),
                },
            )
            raise

        return PipelineResult(
            task_id=task_id,
            task_dir=task_dir,
            status=status,
            current_agent="requirement_agent",
            task_definition=task_definition,
            task_state_path=task_state_path,
            task_definition_path=task_definition_path,
            user_request_path=user_request_path,
        )

    def run(self, user_request: UserRequest) -> PipelineResult:
        """Alias for the current minimal pipeline."""
        return self.run_requirement_stage(user_request)

    def _build_requirement_agent(self, logger: TaskLogger) -> RequirementAgentLike:
        if self.requirement_agent_factory:
            return self.requirement_agent_factory(logger)
        return RequirementAgent(task_logger=logger)

    def _status_from_task_definition(self, task_definition: TaskDefinition) -> str:
        if task_definition.decision == "accepted":
            return "ready_for_modeling"
        if task_definition.decision == "need_info":
            return "waiting_for_required_information"
        if task_definition.decision == "need_confirmation":
            return "waiting_for_optional_confirmation"
        return "rejected"

    def _build_task_state(
        self,
        *,
        task_id: str,
        status: str,
        current_agent: str,
        task_definition: TaskDefinition,
        user_request: UserRequest,
        duration_seconds: float,
    ) -> dict[str, Any]:
        now = current_timestamp()
        return {
            "task_id": task_id,
            "status": status,
            "current_agent": current_agent,
            "created_at": now,
            "updated_at": now,
            "duration_seconds": duration_seconds,
            "input": {
                "source": user_request.source,
                "source_path": user_request.source_path,
            },
            "requirement": {
                "task_name": task_definition.task_name,
                "task_type": task_definition.task_type,
                "decision": task_definition.decision,
                "should_model": task_definition.should_model,
                "critical_missing_information_count": len(
                    task_definition.missing_information.critical
                ),
                "optional_missing_information_count": len(
                    task_definition.missing_information.optional
                ),
            },
            "next_step": self._next_step_from_task_definition(task_definition),
            "paths": {
                "user_request": "user_request.json",
                "task_definition": "task_definition.json",
                "task_log": "logs/task.jsonl",
                "llm_calls_log": "logs/llm_calls.jsonl",
            },
        }

    def _build_failed_task_state(
        self,
        *,
        task_id: str,
        user_request: UserRequest,
        exc: BaseException,
        duration_seconds: float,
    ) -> dict[str, Any]:
        now = current_timestamp()
        return {
            "task_id": task_id,
            "status": "failed",
            "current_agent": "requirement_agent",
            "created_at": now,
            "updated_at": now,
            "duration_seconds": duration_seconds,
            "input": {
                "source": user_request.source,
                "source_path": user_request.source_path,
            },
            "error": build_error_data(exc),
            "next_step": "Inspect task logs and fix the requirement stage failure.",
            "paths": {
                "user_request": "user_request.json",
                "task_state": "task_state.json",
                "task_log": "logs/task.jsonl",
                "llm_calls_log": "logs/llm_calls.jsonl",
            },
        }

    def _next_step_from_task_definition(self, task_definition: TaskDefinition) -> str:
        if task_definition.decision == "accepted":
            return "Continue with research_agent or data_agent."
        if task_definition.decision == "need_info":
            return "Ask the user to provide critical missing information."
        if task_definition.decision == "need_confirmation":
            return "Ask the user to provide optional information or reply yes."
        return "Return the rejection message to the user."
