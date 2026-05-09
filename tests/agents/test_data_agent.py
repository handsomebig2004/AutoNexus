from __future__ import annotations

import json

import pytest

from src.agents.data_agent import DATA_AGENT_SYSTEM_PROMPT, DataAgent
from src.schemas.requirement import TaskDefinition
from src.utils.errors import LLMOutputParseError
from src.utils.run_logger import RunLogger
from src.utils.task_logger import TaskLogger


class FakeLLMClient:
    def __init__(self, response: str, *, provider: str = "fake", model_name: str = "fake-model"):
        self.response = response
        self.provider = provider
        self.model_name = model_name
        self.prompts: list[dict[str, str | None]] = []

    def generate(self, prompt: str, system_prompt: str | None = None):
        self.prompts.append(
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
            }
        )
        return self.response


def _task_definition(**overrides):
    data = {
        "task_name": "Customer churn prediction",
        "task_type": "classification",
        "decision": "accepted",
        "should_model": True,
        "problem_statement": "Predict whether a customer will churn.",
        "input_mode": {
            "data_type": "tabular",
            "required_inputs": ["customer features", "churn label"],
            "target_column": "churn",
        },
        "output_mode": {
            "prediction_type": "class_label",
            "target_description": "Customer churn label",
            "output_format": "One class label per customer.",
        },
        "evaluation": {
            "primary_metric": "f1",
            "validation_strategy": "train/validation/test split",
        },
        "missing_information": {"critical": [], "optional": []},
        "user_facing_response": "Accepted.",
    }
    data.update(overrides)
    return TaskDefinition.model_validate(data)


def _data_profile():
    return {
        "dataset_name": "train.csv",
        "source": {"path": "tasks/task_0/data/raw/train.csv"},
        "shape": {"rows": 100, "columns": 4},
        "columns": [
            {"name": "customer_id", "pandas_type": "string", "missing_rate": 0},
            {"name": "age", "pandas_type": "integer", "missing_rate": 0.1},
            {"name": "gender", "pandas_type": "string", "missing_rate": 0},
            {"name": "churn", "pandas_type": "integer", "missing_rate": 0},
        ],
    }


def _inferred_schema():
    return {
        "dataset_name": "train.csv",
        "task_type": "classification",
        "feature_columns": ["age", "gender"],
        "target_column": "churn",
        "target_candidates": [],
        "id_columns": ["customer_id"],
        "time_columns": [],
        "drop_columns": ["customer_id"],
        "warnings": [],
    }


def _quality_report(can_continue=True):
    return {
        "dataset_name": "train.csv",
        "task_type": "classification",
        "issues": [],
        "summary": {
            "error_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "blocking_issue_count": 0 if can_continue else 1,
        },
        "recommended_actions": [],
        "can_continue": can_continue,
    }


def _plan_json(**overrides):
    data = {
        "plan_name": "Customer churn preprocessing",
        "status": "executable",
        "task_type": "classification",
        "input_files": ["tasks/task_0/data/raw/train.csv"],
        "target_column": "churn",
        "time_column": None,
        "id_columns": ["customer_id"],
        "feature_columns": ["age", "gender"],
        "drop_columns": ["customer_id"],
        "missing_value_plan": [
            {
                "columns": ["age"],
                "strategy": "median",
                "fill_value": None,
                "reason": "Age has missing values.",
            }
        ],
        "categorical_encoding_plan": [
            {
                "columns": ["gender"],
                "encoding": "one_hot",
                "handle_unknown": "ignore",
                "reason": "Gender is low cardinality.",
                "params": {},
            }
        ],
        "numeric_scaling_plan": [
            {
                "columns": ["age"],
                "scaling": "standard",
                "reason": "Use a general numeric scaling default.",
                "params": {},
            }
        ],
        "text_processing_plan": [],
        "datetime_processing_plan": [],
        "split_strategy": {
            "strategy": "stratified",
            "train_size": 0.7,
            "validation_size": 0.1,
            "test_size": 0.2,
            "random_state": 42,
            "stratify_column": "churn",
            "time_column": None,
            "reason": "Classification task should preserve label distribution.",
        },
        "column_actions": [
            {
                "columns": ["customer_id"],
                "action": "drop",
                "reason": "Identifier column should not be used as feature.",
                "params": {},
            }
        ],
        "output_artifacts": [
            {
                "artifact_type": "train_data",
                "path": "data/processed/train.csv",
                "description": "processed training data",
                "required": True,
            },
            {
                "artifact_type": "feature_report",
                "path": "metadata/feature_report.json",
                "description": "feature metadata for train_agent",
                "required": True,
            },
        ],
        "quality_issues_to_handle": [],
        "assumptions": [],
        "warnings": [],
        "user_facing_response": "Data preprocessing plan is ready.",
        "downstream_notes": {"for_train_agent": ["Use metadata/feature_report.json."]},
    }
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


def _prompt_path(tmp_path):
    path = tmp_path / "data_agent.md"
    path.write_text("You are a data planning agent.", encoding="utf-8")
    return path


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_data_agent_outputs_valid_data_process_plan_and_writes_file(tmp_path):
    # 测试 LLM 返回合法计划时，data_agent 会校验为 DataProcessPlan 并写出文件。
    llm_client = FakeLLMClient(_plan_json())
    output_path = tmp_path / "data_plan.json"
    agent = DataAgent(llm_client=llm_client, prompt_path=_prompt_path(tmp_path))

    plan = agent.run(
        task_definition=_task_definition(),
        data_profile=_data_profile(),
        inferred_schema=_inferred_schema(),
        quality_report=_quality_report(),
        output_path=output_path,
    )

    assert plan.status == "executable"
    assert plan.target_column == "churn"
    assert plan.feature_columns == ["age", "gender"]
    assert _read_json(output_path)["plan_name"] == "Customer churn preprocessing"
    assert llm_client.prompts[0]["system_prompt"] == DATA_AGENT_SYSTEM_PROMPT
    assert '"data_profile"' in llm_client.prompts[0]["prompt"]


def test_data_agent_accepts_need_info_plan_for_blocking_quality_report(tmp_path):
    # 测试质量报告阻塞时，data_agent 可以返回 need_info 计划给用户补充信息。
    response = _plan_json(
        status="need_info",
        input_files=[],
        target_column=None,
        feature_columns=[],
        output_artifacts=[],
        user_facing_response="Target column has missing values; please confirm handling.",
    )
    agent = DataAgent(
        llm_client=FakeLLMClient(response),
        prompt_path=_prompt_path(tmp_path),
    )

    plan = agent.run(
        task_definition=_task_definition(),
        data_profile=_data_profile(),
        inferred_schema=_inferred_schema(),
        quality_report=_quality_report(can_continue=False),
    )

    assert plan.status == "need_info"
    assert "Target column" in plan.user_facing_response


def test_data_agent_logs_task_and_run_events(tmp_path):
    # 测试传入 TaskLogger 和 RunLogger 时，会写 task/run 摘要和完整 LLM 调用日志。
    task_logger = TaskLogger(tmp_path / "task_0")
    run_logger = RunLogger(tmp_path / "task_0" / "runs" / "run_0")
    agent = DataAgent(
        llm_client=FakeLLMClient(_plan_json(), provider="openai", model_name="gpt-5-nano"),
        prompt_path=_prompt_path(tmp_path),
        task_logger=task_logger,
        run_logger=run_logger,
    )

    agent.run(
        task_definition=_task_definition(),
        data_profile=_data_profile(),
        inferred_schema=_inferred_schema(),
        quality_report=_quality_report(),
    )

    task_records = _read_jsonl(tmp_path / "task_0" / "logs" / "task.jsonl")
    llm_records = _read_jsonl(tmp_path / "task_0" / "logs" / "llm_calls.jsonl")
    run_records = _read_jsonl(tmp_path / "task_0" / "runs" / "run_0" / "logs" / "run.jsonl")
    assert [record["event"] for record in task_records] == [
        "agent_started",
        "llm_call_finished",
        "agent_finished",
    ]
    assert [record["event"] for record in run_records] == [
        "agent_started",
        "agent_finished",
    ]
    assert llm_records[0]["agent"] == "data_agent"
    assert llm_records[0]["metadata"]["schema"] == "DataProcessPlan"


def test_data_agent_wraps_invalid_llm_output_as_parse_error(tmp_path):
    # 测试 LLM 返回非 JSON 文本时，data_agent 会抛出 LLMOutputParseError。
    task_logger = TaskLogger(tmp_path / "task_0")
    agent = DataAgent(
        llm_client=FakeLLMClient("not json"),
        prompt_path=_prompt_path(tmp_path),
        task_logger=task_logger,
    )

    with pytest.raises(LLMOutputParseError):
        agent.run(
            task_definition=_task_definition(),
            data_profile=_data_profile(),
            inferred_schema=_inferred_schema(),
            quality_report=_quality_report(),
        )

    task_records = _read_jsonl(tmp_path / "task_0" / "logs" / "task.jsonl")
    assert task_records[-1]["event"] == "agent_failed"
