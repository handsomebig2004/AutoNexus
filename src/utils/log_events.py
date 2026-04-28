"""Structured log event helpers.

What this file does:
    Builds the common metadata that should appear in task and run logs, such as
    timestamps, log level, event name, task_id, run_id, agent, message, and
    structured data.

How it works:
    build_log_event() returns a plain dictionary that can be written as JSONL by
    a later logger utility. current_timestamp() uses timezone-aware ISO-8601
    strings. EventTimer is a small helper for measuring agent or run duration.

How to call it:
    from src.utils.log_events import EventTimer, build_log_event

    timer = EventTimer.start()
    event = build_log_event(
        event="agent_finished",
        task_id="task_0",
        agent="requirement_agent",
        data={"duration_seconds": timer.elapsed_seconds()},
    )
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_TIMEZONE = "Asia/Shanghai"
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def current_timestamp(timezone: str = DEFAULT_TIMEZONE) -> str:
    """Return a timezone-aware ISO-8601 timestamp."""
    return datetime.now(ZoneInfo(timezone)).isoformat(timespec="seconds")


def build_log_event(
    event: str,
    *,
    level: str = "INFO",
    task_id: str | None = None,
    run_id: str | None = None,
    agent: str | None = None,
    message: str | None = None,
    data: dict[str, Any] | None = None,
    timezone: str = DEFAULT_TIMEZONE,
) -> dict[str, Any]:
    """Build a standard structured log event dictionary."""
    normalized_level = level.upper()
    if normalized_level not in VALID_LOG_LEVELS:
        raise ValueError(f"Invalid log level: {level}")
    if not event.strip():
        raise ValueError("event cannot be empty.")

    return {
        "time": current_timestamp(timezone),
        "level": normalized_level,
        "event": event.strip(),
        "task_id": task_id,
        "run_id": run_id,
        "agent": agent,
        "message": message or "",
        "data": data or {},
    }


def build_error_data(
    exc: BaseException,
    *,
    include_traceback: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build structured error data suitable for the log event data field."""
    error_data: dict[str, Any] = {
        "error_type": exc.__class__.__name__,
        "error_message": str(exc),
    }

    if include_traceback:
        error_data["traceback"] = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )

    if extra:
        error_data.update(extra)

    return error_data


def build_error_event(
    event: str,
    exc: BaseException,
    *,
    task_id: str | None = None,
    run_id: str | None = None,
    agent: str | None = None,
    message: str | None = None,
    include_traceback: bool = False,
    data: dict[str, Any] | None = None,
    timezone: str = DEFAULT_TIMEZONE,
) -> dict[str, Any]:
    """Build a standard ERROR log event from an exception."""
    return build_log_event(
        event=event,
        level="ERROR",
        task_id=task_id,
        run_id=run_id,
        agent=agent,
        message=message or str(exc),
        data=build_error_data(
            exc,
            include_traceback=include_traceback,
            extra=data,
        ),
        timezone=timezone,
    )


@dataclass(frozen=True)
class EventTimer:
    """Small monotonic timer for measuring durations in log events."""

    start_time: float

    @classmethod
    def start(cls) -> "EventTimer":
        """Start a timer."""
        return cls(start_time=time.perf_counter())

    def elapsed_seconds(self, *, digits: int = 3) -> float:
        """Return elapsed seconds rounded to a stable number of digits."""
        return round(time.perf_counter() - self.start_time, digits)
