"""Task-level JSONL logger.

What this file does:
    Writes task-level summary events to tasks/task_xxx/logs/task.jsonl and full
    LLM call records to tasks/task_xxx/logs/llm_calls.jsonl.

How it works:
    TaskLogger wraps the structured event helpers from log_events.py and the
    JSONL writer from io.py. A file lock beside each JSONL file keeps concurrent
    writers from interleaving lines.

How to call it:
    from src.utils.task_logger import TaskLogger

    logger = TaskLogger("tasks/task_0")
    logger.info("task_created", message="Task created.")
    logger.log_llm_call(
        llm_call_id="llm_0001",
        agent="data_agent",
        provider="deepseek",
        model="deepseek-v4-flash",
        prompt="...",
        response="...",
    )
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from filelock import FileLock, Timeout

from src.utils.io import append_jsonl
from src.utils.log_events import build_error_event, build_log_event, current_timestamp


class TaskLogger:
    """Write task summary logs and full LLM call logs as JSONL."""

    def __init__(
        self,
        task_dir: str | Path,
        *,
        task_id: str | None = None,
        lock_timeout: float = 10,
    ) -> None:
        self.task_dir = Path(task_dir)
        self.task_id = task_id or self.task_dir.name
        self.logs_dir = self.task_dir / "logs"
        self.task_log_path = self.logs_dir / "task.jsonl"
        self.llm_calls_log_path = self.logs_dir / "llm_calls.jsonl"
        self.lock_timeout = lock_timeout

        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        event: str,
        *,
        level: str = "INFO",
        run_id: str | None = None,
        agent: str | None = None,
        message: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build and append one summary event to task.jsonl."""
        record = build_log_event(
            event=event,
            level=level,
            task_id=self.task_id,
            run_id=run_id,
            agent=agent,
            message=message,
            data=data,
        )
        self._append_locked(self.task_log_path, record)
        return record

    def info(
        self,
        event: str,
        *,
        run_id: str | None = None,
        agent: str | None = None,
        message: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append an INFO summary event."""
        return self.log_event(
            event,
            level="INFO",
            run_id=run_id,
            agent=agent,
            message=message,
            data=data,
        )

    def warning(
        self,
        event: str,
        *,
        run_id: str | None = None,
        agent: str | None = None,
        message: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append a WARNING summary event."""
        return self.log_event(
            event,
            level="WARNING",
            run_id=run_id,
            agent=agent,
            message=message,
            data=data,
        )

    def error(
        self,
        event: str,
        exc: BaseException,
        *,
        run_id: str | None = None,
        agent: str | None = None,
        message: str | None = None,
        include_traceback: bool = False,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append an ERROR summary event built from an exception."""
        record = build_error_event(
            event=event,
            exc=exc,
            task_id=self.task_id,
            run_id=run_id,
            agent=agent,
            message=message,
            include_traceback=include_traceback,
            data=data,
        )
        self._append_locked(self.task_log_path, record)
        return record

    def log_llm_call(
        self,
        *,
        llm_call_id: str,
        agent: str,
        provider: str,
        model: str,
        prompt: str,
        response: str | None = None,
        system_prompt: str | None = None,
        run_id: str | None = None,
        status: str = "success",
        error: dict[str, Any] | None = None,
        usage: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        write_summary: bool = True,
    ) -> dict[str, Any]:
        """Append one full LLM call record and optionally a task summary."""
        record = {
            "time": current_timestamp(),
            "llm_call_id": llm_call_id,
            "task_id": self.task_id,
            "run_id": run_id,
            "agent": agent,
            "provider": provider,
            "model": model,
            "status": status,
            "system_prompt": system_prompt,
            "prompt": prompt,
            "response": response,
            "error": error,
            "usage": usage or {},
            "metadata": metadata or {},
        }
        self._append_locked(self.llm_calls_log_path, record)

        if write_summary:
            self.log_llm_summary(
                llm_call_id=llm_call_id,
                agent=agent,
                provider=provider,
                model=model,
                status=status,
                run_id=run_id,
                usage=usage,
                message=f"LLM call {status}.",
            )

        return record

    def log_llm_summary(
        self,
        *,
        llm_call_id: str,
        agent: str,
        provider: str,
        model: str,
        status: str,
        run_id: str | None = None,
        usage: dict[str, Any] | None = None,
        message: str | None = None,
    ) -> dict[str, Any]:
        """Append a compact LLM call summary to task.jsonl."""
        level = "ERROR" if status == "failed" else "INFO"
        return self.log_event(
            "llm_call_finished" if status != "failed" else "llm_call_failed",
            level=level,
            run_id=run_id,
            agent=agent,
            message=message or f"LLM call {status}.",
            data={
                "llm_call_id": llm_call_id,
                "provider": provider,
                "model": model,
                "status": status,
                "usage": usage or {},
            },
        )

    def _append_locked(self, path: Path, record: dict[str, Any]) -> None:
        lock_path = path.with_suffix(path.suffix + ".lock")
        try:
            with FileLock(lock_path, timeout=self.lock_timeout):
                append_jsonl(path, record)
        except Timeout as exc:
            raise TimeoutError(f"Timed out while waiting for log lock: {lock_path}") from exc
