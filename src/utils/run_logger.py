"""Run-level JSONL logger.

What this file does:
    Writes structured summary events for one specific run to
    tasks/task_xxx/runs/run_xxx/logs/run.jsonl.

How it works:
    RunLogger wraps build_log_event()/build_error_event() and append_jsonl().
    Each record always includes task_id and run_id. A file lock beside
    run.jsonl keeps concurrent writers from interleaving lines.

How to call it:
    from src.utils.run_logger import RunLogger

    logger = RunLogger("tasks/task_0/runs/run_0", task_id="task_0")
    logger.info("run_started", message="Run started.")
    logger.generated_code_written("preprocess", "generated/preprocess.py")
    logger.metric_recorded({"accuracy": 0.91, "f1": 0.89})
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from filelock import FileLock, Timeout

from src.utils.io import append_jsonl
from src.utils.log_events import build_error_event, build_log_event


class RunLogger:
    """Write one run's structured summary events as JSONL."""

    def __init__(
        self,
        run_dir: str | Path,
        *,
        task_id: str | None = None,
        run_id: str | None = None,
        lock_timeout: float = 10,
    ) -> None:
        self.run_dir = Path(run_dir)
        self.run_id = run_id or self.run_dir.name
        self.task_id = task_id or self._infer_task_id(self.run_dir)
        self.logs_dir = self.run_dir / "logs"
        self.run_log_path = self.logs_dir / "run.jsonl"
        self.lock_timeout = lock_timeout

        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        event: str,
        *,
        level: str = "INFO",
        agent: str | None = None,
        message: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build and append one event to run.jsonl."""
        record = build_log_event(
            event=event,
            level=level,
            task_id=self.task_id,
            run_id=self.run_id,
            agent=agent,
            message=message,
            data=data,
        )
        self._append_locked(record)
        return record

    def info(
        self,
        event: str,
        *,
        agent: str | None = None,
        message: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append an INFO run event."""
        return self.log_event(
            event,
            level="INFO",
            agent=agent,
            message=message,
            data=data,
        )

    def warning(
        self,
        event: str,
        *,
        agent: str | None = None,
        message: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append a WARNING run event."""
        return self.log_event(
            event,
            level="WARNING",
            agent=agent,
            message=message,
            data=data,
        )

    def error(
        self,
        event: str,
        exc: BaseException,
        *,
        agent: str | None = None,
        message: str | None = None,
        include_traceback: bool = False,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append an ERROR run event built from an exception."""
        record = build_error_event(
            event=event,
            exc=exc,
            task_id=self.task_id,
            run_id=self.run_id,
            agent=agent,
            message=message,
            include_traceback=include_traceback,
            data=data,
        )
        self._append_locked(record)
        return record

    def generated_code_written(
        self,
        code_type: str,
        path: str | Path,
        *,
        agent: str | None = None,
        sha256: str | None = None,
        message: str | None = None,
    ) -> dict[str, Any]:
        """Log a generated code artifact such as preprocess.py or train.py."""
        return self.info(
            "generated_code_written",
            agent=agent,
            message=message or f"Generated {code_type} code written.",
            data={
                "code_type": code_type,
                "path": str(path),
                "sha256": sha256,
            },
        )

    def artifact_written(
        self,
        artifact_type: str,
        path: str | Path,
        *,
        agent: str | None = None,
        metadata: dict[str, Any] | None = None,
        message: str | None = None,
    ) -> dict[str, Any]:
        """Log an output artifact such as model, metrics, report, or figure."""
        return self.info(
            "artifact_written",
            agent=agent,
            message=message or f"{artifact_type} artifact written.",
            data={
                "artifact_type": artifact_type,
                "path": str(path),
                "metadata": metadata or {},
            },
        )

    def metric_recorded(
        self,
        metrics: dict[str, Any],
        *,
        split: str | None = None,
        agent: str | None = None,
        message: str | None = None,
    ) -> dict[str, Any]:
        """Log one set of metrics for this run."""
        return self.info(
            "metric_recorded",
            agent=agent,
            message=message or "Metrics recorded.",
            data={
                "split": split,
                "metrics": metrics,
            },
        )

    def _append_locked(self, record: dict[str, Any]) -> None:
        lock_path = self.run_log_path.with_suffix(self.run_log_path.suffix + ".lock")
        try:
            with FileLock(lock_path, timeout=self.lock_timeout):
                append_jsonl(self.run_log_path, record)
        except Timeout as exc:
            raise TimeoutError(f"Timed out while waiting for log lock: {lock_path}") from exc

    def _infer_task_id(self, run_dir: Path) -> str | None:
        parts = run_dir.parts
        if len(parts) >= 3 and parts[-2] == "runs":
            return parts[-3]
        return None
