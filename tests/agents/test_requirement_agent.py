from __future__ import annotations

import json

import pytest

from src.agents.requirement_agent import RequirementAgent
from src.schemas import UserRequest
from src.utils.errors import LLMOutputParseError
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


def _llm_json(**overrides) -> str:
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
        "constraints": {
            "must_have": [],
            "must_not": [],
            "resource_limits": [],
            "privacy_or_safety": [],
        },
        "evaluation": {
            "primary_metric": "f1",
            "secondary_metrics": ["accuracy"],
            "validation_strategy": "train/validation/test split",
            "metric_reasoning": "F1 is useful for churn classification.",
        },
        "assumptions": [],
        "missing_information": {"critical": [], "optional": []},
        "user_facing_response": "Accepted.",
        "downstream_notes": {
            "for_research_agent": [],
            "for_data_agent": [],
            "for_train_agent": [],
            "for_evaluation_agent": [],
        },
        "raw_user_request": "This value should be overwritten by the agent.",
    }
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


def _prompt_path(tmp_path):
    path = tmp_path / "requirement_agent.md"
    path.write_text("You are a requirement parser.", encoding="utf-8")
    return path


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_requirement_agent_accepts_valid_llm_json_and_writes_output(tmp_path):
    # 测试 LLM 返回完整合法 JSON 时，agent 会生成 accepted 的 TaskDefinition 并写出文件。
    llm_client = FakeLLMClient(_llm_json())
    output_path = tmp_path / "task_definition.json"
    agent = RequirementAgent(
        llm_client=llm_client,
        prompt_path=_prompt_path(tmp_path),
    )

    task_definition = agent.run(
        UserRequest(
            request_text="I have customer features and churn labels.",
            source="cli",
        ),
        output_path=output_path,
    )

    assert task_definition.decision == "accepted"
    assert task_definition.should_model is True
    assert task_definition.raw_user_request == "I have customer features and churn labels."
    assert _read_json(output_path)["decision"] == "accepted"
    assert "I have customer features and churn labels." in llm_client.prompts[0]["prompt"]


def test_requirement_agent_logs_llm_call_and_summary(tmp_path):
    # 测试传入 TaskLogger 时，agent 会记录完整 LLM 调用和 task 级摘要日志。
    logger = TaskLogger(tmp_path / "task_0")
    agent = RequirementAgent(
        llm_client=FakeLLMClient(_llm_json(), provider="openai", model_name="gpt-5-nano"),
        prompt_path=_prompt_path(tmp_path),
        task_logger=logger,
    )

    agent.run(UserRequest(request_text="Predict churn.", source="stdin"))

    task_records = _read_jsonl(tmp_path / "task_0" / "logs" / "task.jsonl")
    llm_records = _read_jsonl(tmp_path / "task_0" / "logs" / "llm_calls.jsonl")
    assert [record["event"] for record in task_records] == [
        "agent_started",
        "llm_call_finished",
        "agent_finished",
    ]
    assert llm_records[0]["llm_call_id"] == "llm_0001"
    assert llm_records[0]["provider"] == "openai"
    assert llm_records[0]["model"] == "gpt-5-nano"


def test_requirement_agent_downgrades_unsafe_accepted_output_to_need_info(tmp_path):
    # 测试 LLM 错误放行但缺少关键字段时，确定性验证会降级为 need_info。
    response = _llm_json(
        input_mode={
            "data_type": "tabular",
            "required_inputs": ["customer features"],
            "target_column": None,
        }
    )
    agent = RequirementAgent(
        llm_client=FakeLLMClient(response),
        prompt_path=_prompt_path(tmp_path),
    )

    task_definition = agent.run(
        UserRequest(request_text="Build a churn classifier.", source="cli")
    )

    assert task_definition.decision == "need_info"
    assert task_definition.should_model is False
    assert task_definition.missing_information.critical


def test_requirement_agent_turns_optional_missing_information_into_confirmation(tmp_path):
    # 测试 LLM 输出 accepted 但带 optional 缺失信息时，会变成 need_confirmation。
    response = _llm_json(
        missing_information={
            "critical": [],
            "optional": ["Class distribution is unknown."],
        }
    )
    agent = RequirementAgent(
        llm_client=FakeLLMClient(response),
        prompt_path=_prompt_path(tmp_path),
    )

    task_definition = agent.run(
        UserRequest(request_text="Predict customer churn.", source="cli")
    )

    assert task_definition.decision == "need_confirmation"
    assert task_definition.should_model is False
    assert task_definition.missing_information.optional == [
        "Class distribution is unknown."
    ]


def test_requirement_agent_rejects_unknown_task_type(tmp_path):
    # 测试 unknown 类型会被 schema 规范为 rejected，并禁止进入建模。
    response = _llm_json(
        task_type="unknown",
        decision="rejected",
        should_model=False,
        input_mode={
            "data_type": "unknown",
            "required_inputs": [],
            "target_column": None,
        },
        output_mode={
            "prediction_type": "unknown",
            "target_description": "",
            "output_format": "",
        },
        evaluation={
            "primary_metric": "",
            "secondary_metrics": [],
            "validation_strategy": "",
            "metric_reasoning": "",
        },
        user_facing_response="Unsupported task.",
    )
    agent = RequirementAgent(
        llm_client=FakeLLMClient(response),
        prompt_path=_prompt_path(tmp_path),
    )

    task_definition = agent.run(
        UserRequest(request_text="Write a literature review.", source="cli")
    )

    assert task_definition.task_type == "unknown"
    assert task_definition.decision == "rejected"
    assert task_definition.should_model is False


def test_requirement_agent_wraps_invalid_llm_output_as_parse_error(tmp_path):
    # 测试 LLM 返回非 JSON 文本时，agent 会抛出 LLMOutputParseError。
    logger = TaskLogger(tmp_path / "task_0")
    agent = RequirementAgent(
        llm_client=FakeLLMClient("this is not json"),
        prompt_path=_prompt_path(tmp_path),
        task_logger=logger,
    )

    with pytest.raises(LLMOutputParseError):
        agent.run(UserRequest(request_text="Build a model.", source="cli"))

    task_records = _read_jsonl(tmp_path / "task_0" / "logs" / "task.jsonl")
    assert task_records[-1]["event"] == "agent_failed"
