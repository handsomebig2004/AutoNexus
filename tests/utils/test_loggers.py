from __future__ import annotations

import json

from src.utils.run_logger import RunLogger
from src.utils.task_logger import TaskLogger


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_task_logger_writes_task_events(tmp_path):
    # 测试 TaskLogger 会把 task 级摘要事件写入 task.jsonl。
    logger = TaskLogger(tmp_path / "task_0")

    record = logger.info(
        "task_created",
        agent="requirement_agent",
        message="Task created.",
        data={"source": "cli"},
    )

    records = _read_jsonl(tmp_path / "task_0" / "logs" / "task.jsonl")
    assert record["event"] == "task_created"
    assert records[0]["task_id"] == "task_0"
    assert records[0]["data"] == {"source": "cli"}


def test_task_logger_writes_full_llm_call_and_summary(tmp_path):
    # 测试 TaskLogger 会写完整 LLM 调用日志，并同步写一条 task 摘要。
    logger = TaskLogger(tmp_path / "task_0")

    logger.log_llm_call(
        llm_call_id="llm_0001",
        agent="requirement_agent",
        provider="openai",
        model="gpt-5-nano",
        prompt="prompt",
        response="response",
        usage={"input_tokens": 1},
    )

    llm_records = _read_jsonl(tmp_path / "task_0" / "logs" / "llm_calls.jsonl")
    task_records = _read_jsonl(tmp_path / "task_0" / "logs" / "task.jsonl")
    assert llm_records[0]["prompt"] == "prompt"
    assert llm_records[0]["response"] == "response"
    assert task_records[0]["event"] == "llm_call_finished"
    assert task_records[0]["data"]["llm_call_id"] == "llm_0001"


def test_run_logger_infers_task_id_and_writes_helper_events(tmp_path):
    # 测试 RunLogger 能从路径推断 task_id，并写入代码、产物和指标事件。
    run_dir = tmp_path / "task_0" / "runs" / "run_0"
    logger = RunLogger(run_dir)

    logger.generated_code_written("preprocess", "src/run_0/preprocess.py")
    logger.artifact_written("model", "outputs/model.pkl")
    logger.metric_recorded({"f1": 0.8}, split="test")

    records = _read_jsonl(run_dir / "logs" / "run.jsonl")
    assert [record["event"] for record in records] == [
        "generated_code_written",
        "artifact_written",
        "metric_recorded",
    ]
    assert records[0]["task_id"] == "task_0"
    assert records[0]["run_id"] == "run_0"
    assert records[2]["data"]["metrics"] == {"f1": 0.8}
