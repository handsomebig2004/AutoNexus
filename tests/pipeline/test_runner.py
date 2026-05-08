from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.pipeline import PipelineRunner
from src.schemas import UserRequest
from src.schemas.requirement import TaskDefinition


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


class FakeRequirementAgent:
    def __init__(self, task_definition):
        self.task_definition = task_definition

    def run(self, user_request, *, output_path=None):
        if output_path:
            Path(output_path).write_text(
                json.dumps(
                    self.task_definition.to_json_dict(),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        return self.task_definition


class FailingRequirementAgent:
    def run(self, user_request, *, output_path=None):
        raise RuntimeError("requirement failed")


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_pipeline_runner_creates_task_files_for_accepted_requirement(tmp_path):
    # 测试 runner 会创建 task 目录，保存输入、需求定义和状态快照。
    task_definition = _task_definition()
    runner = PipelineRunner(
        tasks_dir=tmp_path,
        requirement_agent_factory=lambda logger: FakeRequirementAgent(task_definition),
    )

    result = runner.run_requirement_stage(
        UserRequest(request_text="Predict customer churn.", source="cli")
    )

    assert result.task_id == "task_0"
    assert result.status == "ready_for_modeling"
    assert result.can_continue is True
    assert result.user_request_path.exists()
    assert result.task_definition_path.exists()
    assert result.task_state_path.exists()

    state = _read_json(result.task_state_path)
    assert state["status"] == "ready_for_modeling"
    assert state["requirement"]["decision"] == "accepted"
    assert state["next_step"] == "Continue with research_agent or data_agent."


def test_pipeline_runner_pauses_when_requirement_needs_info(tmp_path):
    # 测试 requirement_agent 返回 need_info 时，runner 会暂停并写等待补充信息状态。
    task_definition = _task_definition(
        decision="need_info",
        should_model=False,
        missing_information={
            "critical": ["Please provide target column."],
            "optional": [],
        },
        user_facing_response="Please provide target column.",
    )
    runner = PipelineRunner(
        tasks_dir=tmp_path,
        requirement_agent_factory=lambda logger: FakeRequirementAgent(task_definition),
    )

    result = runner.run(
        UserRequest(request_text="Build a churn model.", source="stdin")
    )

    state = _read_json(result.task_state_path)
    assert result.can_continue is False
    assert result.status == "waiting_for_required_information"
    assert state["requirement"]["critical_missing_information_count"] == 1


def test_pipeline_runner_writes_failed_state_when_requirement_stage_crashes(tmp_path):
    # 测试 requirement 阶段异常时，runner 会写 failed 状态并继续抛出异常。
    runner = PipelineRunner(
        tasks_dir=tmp_path,
        requirement_agent_factory=lambda logger: FailingRequirementAgent(),
    )

    with pytest.raises(RuntimeError, match="requirement failed"):
        runner.run_requirement_stage(
            UserRequest(request_text="Build a model.", source="cli")
        )

    state = _read_json(tmp_path / "task_0" / "task_state.json")
    assert state["status"] == "failed"
    assert state["error"]["error_type"] == "RuntimeError"
