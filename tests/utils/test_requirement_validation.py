from __future__ import annotations

import pytest

from src.schemas.requirement import TaskDefinition
from src.utils.errors import RequirementValidationError
from src.utils.requirement_validation import (
    confirm_optional_information,
    normalize_requirement_gate,
    validate_requirement_for_modeling,
)


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


def test_validate_requirement_for_modeling_accepts_complete_task():
    # 测试信息完整的分类任务可以通过建模闸门验证。
    result = validate_requirement_for_modeling(_task_definition())

    assert result.can_model is True
    assert result.errors == []
    assert result.warnings == []


def test_normalize_requirement_gate_downgrades_accepted_task_with_missing_target():
    # 测试 LLM 误判为 accepted 但缺少 target_column 时，会降级为 need_info。
    task = _task_definition(
        input_mode={
            "data_type": "tabular",
            "required_inputs": ["customer features"],
            "target_column": None,
        }
    )

    normalized, validation = normalize_requirement_gate(task)

    assert validation.can_model is False
    assert normalized.decision == "need_info"
    assert normalized.should_model is False
    assert normalized.missing_information.critical


def test_normalize_requirement_gate_downgrades_optional_warnings_to_confirmation():
    # 测试只有可选信息缺失时，会降级为 need_confirmation 等待用户确认。
    task = _task_definition(
        task_type="forecasting",
        input_mode={
            "data_type": "time_series",
            "required_inputs": ["daily sales"],
            "target_column": "sales",
            "time_column": "date",
            "data_granularity": None,
        },
        output_mode={
            "prediction_type": "future_value",
            "target_description": "Future sales",
            "output_format": "Sales forecast per future date.",
        },
    )

    normalized, validation = normalize_requirement_gate(task)

    assert validation.errors == []
    assert validation.warnings
    assert normalized.decision == "need_confirmation"
    assert normalized.should_model is False
    assert normalized.missing_information.optional


def test_confirm_optional_information_accepts_need_confirmation_task():
    # 测试用户确认 optional 缺失后，可以把 need_confirmation 转为 accepted。
    task = _task_definition(
        decision="need_confirmation",
        should_model=False,
        missing_information={
            "critical": [],
            "optional": ["Class distribution is unknown."],
        },
    )

    confirmed = confirm_optional_information(task)

    assert confirmed.decision == "accepted"
    assert confirmed.should_model is True
    assert confirmed.missing_information.critical == []
    assert confirmed.missing_information.optional == []
    assert confirmed.assumptions


def test_confirm_optional_information_rejects_non_confirmation_task():
    # 测试非 need_confirmation 的任务不能走 optional 确认通道。
    with pytest.raises(RequirementValidationError):
        confirm_optional_information(_task_definition())
