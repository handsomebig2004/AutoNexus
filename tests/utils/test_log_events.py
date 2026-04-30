from __future__ import annotations

import time

import pytest

from src.utils.log_events import (
    EventTimer,
    build_error_data,
    build_error_event,
    build_log_event,
    current_timestamp,
)


def test_current_timestamp_is_timezone_aware_iso_string():
    # 测试当前时间戳是带 Asia/Shanghai 时区的 ISO 字符串。
    timestamp = current_timestamp()

    assert "T" in timestamp
    assert timestamp.endswith("+08:00")


def test_build_log_event_normalizes_level_and_fields():
    # 测试普通日志事件会规范化日志级别，并保留 task、agent 和 data 字段。
    event = build_log_event(
        "agent_finished",
        level="warning",
        task_id="task_0",
        agent="requirement_agent",
        data={"ok": True},
    )

    assert event["level"] == "WARNING"
    assert event["event"] == "agent_finished"
    assert event["task_id"] == "task_0"
    assert event["data"] == {"ok": True}


def test_build_log_event_rejects_invalid_level_and_empty_event():
    # 测试非法日志级别和空事件名会被拒绝。
    with pytest.raises(ValueError, match="Invalid log level"):
        build_log_event("event", level="NOPE")

    with pytest.raises(ValueError, match="event cannot be empty"):
        build_log_event(" ")


def test_build_error_helpers_include_error_type_and_extra_data():
    # 测试错误日志数据会包含异常类型、异常消息和额外上下文。
    exc = RuntimeError("boom")

    data = build_error_data(exc, extra={"stage": "train"})
    event = build_error_event("run_failed", exc, task_id="task_0")

    assert data["error_type"] == "RuntimeError"
    assert data["error_message"] == "boom"
    assert data["stage"] == "train"
    assert event["level"] == "ERROR"
    assert event["data"]["error_type"] == "RuntimeError"


def test_event_timer_reports_elapsed_seconds():
    # 测试 EventTimer 可以返回非负的耗时秒数。
    timer = EventTimer.start()
    time.sleep(0.001)

    assert timer.elapsed_seconds() >= 0
