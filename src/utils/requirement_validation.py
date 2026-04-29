"""Requirement gate validation utilities.

What this file does:
    Checks whether requirement_agent output is safe to pass into downstream
    modeling agents.

How it works:
    Pydantic validates the shape of TaskDefinition. This file validates the
    business gate: supported task type, accepted decision, no critical or
    optional missing information, and enough input/output/evaluation detail to
    continue.

How to call it:
    from src.utils.requirement_validation import normalize_requirement_gate

    task_definition, validation = normalize_requirement_gate(task_definition)
    if not validation.can_model:
        return task_definition.user_facing_response

    # If decision is need_confirmation and the user replies yes:
    task_definition = confirm_optional_information(task_definition)
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

    _validate_gate_decision(task_definition, errors, warnings)
    _validate_input_mode(task_definition, errors, warnings)
    _validate_output_mode(task_definition, errors)
    _validate_evaluation(task_definition, errors, warnings)

    result = RequirementGateValidation(
        can_model=not errors and not warnings,
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
    Validate a TaskDefinition and downgrade unsafe accepted tasks.

    If the LLM says accepted but the deterministic gate finds missing critical
    information, this function turns the output into need_info so downstream
    agents cannot accidentally start modeling. If only optional information is
    missing, it turns the output into need_confirmation.
    """
    validation = validate_requirement_for_modeling(task_definition)
    if validation.can_model or task_definition.decision != "accepted":
        return task_definition, validation

    data = task_definition.to_json_dict()
    data["should_model"] = False
    if validation.errors:
        data["decision"] = "need_info"
        data["missing_information"]["critical"] = _merge_unique(
            task_definition.missing_information.critical,
            validation.errors,
        )
        data["user_facing_response"] = _build_need_info_response(validation.errors)
    else:
        data["decision"] = "need_confirmation"
        data["missing_information"]["optional"] = _merge_unique(
            task_definition.missing_information.optional,
            validation.warnings,
        )
        data["user_facing_response"] = _build_need_confirmation_response(
            data["missing_information"]["optional"]
        )

    normalized = TaskDefinition.model_validate(data)
    return normalized, validation


def confirm_optional_information(task_definition: TaskDefinition) -> TaskDefinition:
    """
    Confirm that the user wants to continue despite optional missing information.

    This is used after the user replies yes to a need_confirmation response. It
    does not call requirement_agent again.
    """
    if task_definition.decision != "need_confirmation":
        raise RequirementValidationError(
            "Only need_confirmation tasks can be confirmed this way."
        )
    if task_definition.missing_information.critical:
        raise RequirementValidationError(
            "Cannot confirm a task with critical missing information."
        )

    optional_items = task_definition.missing_information.optional
    data = task_definition.to_json_dict()
    data["decision"] = "accepted"
    data["should_model"] = True
    data["missing_information"] = {"critical": [], "optional": []}
    if optional_items:
        data["assumptions"] = [
            *task_definition.assumptions,
            "用户确认在缺少以下可选信息时继续建模: " + "；".join(optional_items),
        ]
    data["user_facing_response"] = "已确认在缺少可选信息的情况下继续进入后续建模。"
    return TaskDefinition.model_validate(data)


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


def _build_need_confirmation_response(optional_items: list[str]) -> str:
    items = "\n".join(
        f"{index}. {item}" for index, item in enumerate(optional_items, 1)
    )
    return (
        "当前需求的关键信息已经足够，可以进入建模；但仍缺少一些可选信息，"
        "补充后可能提升建模质量。请补充以下信息，或回复 yes 直接继续：\n"
        f"{items}"
    )


def _validate_gate_decision(
    task_definition: TaskDefinition,
    errors: list[str],
    warnings: list[str],
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

    if task_definition.missing_information.critical:
        errors.append(
            "missing_information.critical must be empty to enter modeling."
        )

    if task_definition.missing_information.optional:
        warnings.append(
            "missing_information.optional must be confirmed before modeling."
        )


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
