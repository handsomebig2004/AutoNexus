"""Requirement gate validation utilities.

What this file does:
    Checks whether requirement_agent output is safe to pass into downstream
    modeling agents.

How it works:
    Pydantic validates the shape of TaskDefinition. This file validates the
    business gate: supported task type, accepted decision, no missing blocking
    information, and enough input/output/evaluation detail to continue.

How to call it:
    from src.utils.requirement_validation import normalize_requirement_gate

    task_definition, validation = normalize_requirement_gate(task_definition)
    if not validation.can_model:
        return task_definition.user_facing_response
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.schemas.requirement import TaskDefinition
from src.utils.errors import RequirementValidationError


SUPPORTED_MODELING_TASK_TYPES = {
    "classification",
    "regression",
    "forecasting",
    "clustering",
}


@dataclass(frozen=True)
class RequirementGateValidation:
    """Result of requirement gate validation."""

    can_model: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_requirement_for_modeling(
    task_definition: TaskDefinition,
    *,
    raise_on_error: bool = False,
) -> RequirementGateValidation:
    """Validate whether a TaskDefinition can safely enter modeling."""
    errors: list[str] = []
    warnings: list[str] = []

    _validate_gate_decision(task_definition, errors)
    _validate_input_mode(task_definition, errors, warnings)
    _validate_output_mode(task_definition, errors)
    _validate_evaluation(task_definition, errors, warnings)

    result = RequirementGateValidation(
        can_model=not errors,
        errors=errors,
        warnings=warnings,
    )
    if raise_on_error and errors:
        raise RequirementValidationError("; ".join(errors))
    return result


def normalize_requirement_gate(
    task_definition: TaskDefinition,
) -> tuple[TaskDefinition, RequirementGateValidation]:
    """
    Validate a TaskDefinition and downgrade unsafe accepted tasks to need_info.

    If the LLM says accepted but the deterministic gate finds missing critical
    information, this function turns the output into need_info so downstream
    agents cannot accidentally start modeling.
    """
    validation = validate_requirement_for_modeling(task_definition)
    if validation.can_model or task_definition.decision != "accepted":
        return task_definition, validation

    data = task_definition.to_json_dict()
    data["decision"] = "need_info"
    data["should_model"] = False
    data["missing_information"] = _merge_unique(
        task_definition.missing_information,
        validation.errors,
    )
    data["user_facing_response"] = _build_need_info_response(validation.errors)

    normalized = TaskDefinition.model_validate(data)
    return normalized, validation


def _merge_unique(first: list[str], second: list[str]) -> list[str]:
    seen = set()
    merged: list[str] = []
    for item in [*first, *second]:
        if item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged


def _build_need_info_response(errors: list[str]) -> str:
    items = "\n".join(f"{index}. {error}" for index, error in enumerate(errors, 1))
    return (
        "当前需求属于支持的建模类型，但缺少进入自动建模所需的关键信息，"
        "暂不继续建模。请补充：\n"
        f"{items}"
    )


def _validate_gate_decision(
    task_definition: TaskDefinition,
    errors: list[str],
) -> None:
    if task_definition.task_type not in SUPPORTED_MODELING_TASK_TYPES:
        errors.append(
            "task_type must be one of classification, regression, forecasting, "
            "or clustering to enter modeling."
        )

    if task_definition.decision != "accepted":
        errors.append("decision must be accepted to enter modeling.")

    if not task_definition.should_model:
        errors.append("should_model must be true to enter modeling.")

    if task_definition.missing_information:
        errors.append("missing_information must be empty to enter modeling.")


def _validate_input_mode(
    task_definition: TaskDefinition,
    errors: list[str],
    warnings: list[str],
) -> None:
    input_mode = task_definition.input_mode

    if input_mode.data_type == "unknown":
        errors.append("input_mode.data_type cannot be unknown for accepted tasks.")

    if not input_mode.required_inputs:
        errors.append("input_mode.required_inputs must not be empty.")

    if task_definition.task_type in {"classification", "regression"}:
        if not input_mode.target_column:
            errors.append(
                f"{task_definition.task_type} tasks must specify input_mode.target_column."
            )

    if task_definition.task_type == "forecasting":
        if not input_mode.target_column:
            errors.append("forecasting tasks must specify input_mode.target_column.")
        if not input_mode.time_column:
            errors.append("forecasting tasks must specify input_mode.time_column.")
        if not input_mode.data_granularity:
            warnings.append(
                "forecasting tasks should specify input_mode.data_granularity."
            )

    if task_definition.task_type == "clustering" and input_mode.target_column:
        warnings.append("clustering tasks usually should not specify a target_column.")


def _validate_output_mode(
    task_definition: TaskDefinition,
    errors: list[str],
) -> None:
    output_mode = task_definition.output_mode

    if output_mode.prediction_type == "unknown":
        errors.append("output_mode.prediction_type cannot be unknown for accepted tasks.")
    if not output_mode.target_description.strip():
        errors.append("output_mode.target_description must not be empty.")
    if not output_mode.output_format.strip():
        errors.append("output_mode.output_format must not be empty.")


def _validate_evaluation(
    task_definition: TaskDefinition,
    errors: list[str],
    warnings: list[str],
) -> None:
    evaluation = task_definition.evaluation

    if not evaluation.primary_metric.strip():
        errors.append("evaluation.primary_metric must not be empty for accepted tasks.")
    if not evaluation.validation_strategy.strip():
        warnings.append("evaluation.validation_strategy should not be empty.")
