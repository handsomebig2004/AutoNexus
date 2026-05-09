"""Data agent preprocessing plan schema.

What this file does:
    Defines the structured plan that data_agent should produce before asking an
    LLM to write preprocessing code. The plan describes how data should be
    cleaned, split, transformed, and saved.

How it works:
    Pydantic validates that the plan has a supported status, task type, input
    files, column roles, preprocessing strategies, split strategy, and expected
    output artifacts. A plan can be executable, need_info, or rejected.

How to call it:
    from src.schemas.data_plan import DataProcessPlan

    plan = DataProcessPlan.model_validate(llm_json)
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.schemas.requirement import TaskType


PlanStatus = Literal["executable", "need_info", "rejected"]
MissingStrategy = Literal[
    "none",
    "drop_rows",
    "drop_column",
    "mean",
    "median",
    "mode",
    "constant",
    "ffill",
    "bfill",
    "custom",
]
CategoricalEncoding = Literal[
    "none",
    "one_hot",
    "ordinal",
    "target",
    "frequency",
    "hashing",
    "drop",
    "custom",
]
NumericScaling = Literal["none", "standard", "minmax", "robust", "log", "custom"]
TextProcessing = Literal["none", "tfidf", "embedding", "drop", "custom"]
DatetimeProcessing = Literal[
    "none",
    "extract_parts",
    "cyclical",
    "sort_index",
    "resample",
    "drop",
    "custom",
]
SplitStrategyType = Literal[
    "none",
    "random",
    "stratified",
    "time_based",
    "predefined",
    "custom",
]
ArtifactType = Literal[
    "train_data",
    "validation_data",
    "test_data",
    "full_processed_data",
    "feature_report",
    "preprocessor",
    "metadata",
    "other",
]


class ColumnAction(BaseModel):
    """How one or more columns should be handled."""

    model_config = ConfigDict(extra="forbid")

    columns: list[str] = Field(default_factory=list)
    action: str
    reason: str = ""
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("columns")
    @classmethod
    def _columns_must_not_be_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("columns cannot be empty.")
        return [_strip_non_empty(item, "columns") for item in value]

    @field_validator("action")
    @classmethod
    def _action_must_not_be_empty(cls, value: str) -> str:
        return _strip_non_empty(value, "action")


class MissingValuePlan(BaseModel):
    """Missing value handling for a group of columns."""

    model_config = ConfigDict(extra="forbid")

    columns: list[str] = Field(default_factory=list)
    strategy: MissingStrategy
    fill_value: Any = None
    reason: str = ""

    @field_validator("columns")
    @classmethod
    def _columns_must_not_be_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("columns cannot be empty.")
        return [_strip_non_empty(item, "columns") for item in value]

    @model_validator(mode="after")
    def _constant_requires_fill_value(self) -> "MissingValuePlan":
        if self.strategy == "constant" and self.fill_value is None:
            raise ValueError("constant missing strategy requires fill_value.")
        return self


class CategoricalEncodingPlan(BaseModel):
    """Categorical feature encoding for a group of columns."""

    model_config = ConfigDict(extra="forbid")

    columns: list[str] = Field(default_factory=list)
    encoding: CategoricalEncoding
    handle_unknown: str = "ignore"
    reason: str = ""
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("columns")
    @classmethod
    def _columns_must_not_be_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("columns cannot be empty.")
        return [_strip_non_empty(item, "columns") for item in value]


class NumericScalingPlan(BaseModel):
    """Numeric feature scaling for a group of columns."""

    model_config = ConfigDict(extra="forbid")

    columns: list[str] = Field(default_factory=list)
    scaling: NumericScaling
    reason: str = ""
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("columns")
    @classmethod
    def _columns_must_not_be_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("columns cannot be empty.")
        return [_strip_non_empty(item, "columns") for item in value]


class TextProcessingPlan(BaseModel):
    """Text feature processing for a group of columns."""

    model_config = ConfigDict(extra="forbid")

    columns: list[str] = Field(default_factory=list)
    method: TextProcessing
    reason: str = ""
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("columns")
    @classmethod
    def _columns_must_not_be_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("columns cannot be empty.")
        return [_strip_non_empty(item, "columns") for item in value]


class DatetimeProcessingPlan(BaseModel):
    """Datetime feature processing for a group of columns."""

    model_config = ConfigDict(extra="forbid")

    columns: list[str] = Field(default_factory=list)
    method: DatetimeProcessing
    reason: str = ""
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("columns")
    @classmethod
    def _columns_must_not_be_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("columns cannot be empty.")
        return [_strip_non_empty(item, "columns") for item in value]


class SplitStrategy(BaseModel):
    """How processed data should be split."""

    model_config = ConfigDict(extra="forbid")

    strategy: SplitStrategyType
    train_size: float | None = None
    validation_size: float | None = None
    test_size: float | None = None
    random_state: int | None = 42
    stratify_column: str | None = None
    time_column: str | None = None
    reason: str = ""

    @model_validator(mode="after")
    def _validate_split_fields(self) -> "SplitStrategy":
        sizes = [
            size
            for size in [self.train_size, self.validation_size, self.test_size]
            if size is not None
        ]
        for size in sizes:
            if size <= 0 or size >= 1:
                raise ValueError("split sizes must be between 0 and 1.")
        if sizes and sum(sizes) > 1.0:
            raise ValueError("split sizes cannot sum to more than 1.")
        if self.strategy == "stratified" and not self.stratify_column:
            raise ValueError("stratified split requires stratify_column.")
        if self.strategy == "time_based" and not self.time_column:
            raise ValueError("time_based split requires time_column.")
        return self


class OutputArtifact(BaseModel):
    """Expected output artifact produced by preprocessing."""

    model_config = ConfigDict(extra="forbid")

    artifact_type: ArtifactType
    path: str
    description: str = ""
    required: bool = True

    @field_validator("path")
    @classmethod
    def _path_must_not_be_empty(cls, value: str) -> str:
        return _strip_non_empty(value, "path")


class DataProcessPlan(BaseModel):
    """Full data_agent preprocessing plan."""

    model_config = ConfigDict(extra="forbid")

    plan_name: str
    status: PlanStatus
    task_type: TaskType
    input_files: list[str] = Field(default_factory=list)
    target_column: str | None = None
    time_column: str | None = None
    id_columns: list[str] = Field(default_factory=list)
    feature_columns: list[str] = Field(default_factory=list)
    drop_columns: list[str] = Field(default_factory=list)
    missing_value_plan: list[MissingValuePlan] = Field(default_factory=list)
    categorical_encoding_plan: list[CategoricalEncodingPlan] = Field(default_factory=list)
    numeric_scaling_plan: list[NumericScalingPlan] = Field(default_factory=list)
    text_processing_plan: list[TextProcessingPlan] = Field(default_factory=list)
    datetime_processing_plan: list[DatetimeProcessingPlan] = Field(default_factory=list)
    split_strategy: SplitStrategy = Field(
        default_factory=lambda: SplitStrategy(strategy="none")
    )
    column_actions: list[ColumnAction] = Field(default_factory=list)
    output_artifacts: list[OutputArtifact] = Field(default_factory=list)
    quality_issues_to_handle: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    user_facing_response: str = ""
    downstream_notes: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("plan_name")
    @classmethod
    def _plan_name_must_not_be_empty(cls, value: str) -> str:
        return _strip_non_empty(value, "plan_name")

    @field_validator("input_files", "id_columns", "feature_columns", "drop_columns")
    @classmethod
    def _strip_string_lists(cls, value: list[str]) -> list[str]:
        return [_strip_non_empty(item, "list item") for item in value]

    @model_validator(mode="after")
    def _status_controls_required_fields(self) -> "DataProcessPlan":
        if self.status == "executable":
            if not self.input_files:
                raise ValueError("executable data plan requires input_files.")
            if self.task_type in {"classification", "regression", "forecasting"}:
                if not self.target_column:
                    raise ValueError(
                        f"{self.task_type} data plan requires target_column."
                    )
            if self.task_type == "forecasting" and not self.time_column:
                raise ValueError("forecasting data plan requires time_column.")
            if not self.feature_columns:
                raise ValueError("executable data plan requires feature_columns.")
            if not self.output_artifacts:
                raise ValueError("executable data plan requires output_artifacts.")
            return self

        if self.status == "need_info":
            if not self.user_facing_response.strip():
                raise ValueError("need_info data plan requires user_facing_response.")

        if self.status == "rejected":
            if not self.user_facing_response.strip():
                raise ValueError("rejected data plan requires user_facing_response.")

        return self

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary."""
        return self.model_dump(mode="json")


def _strip_non_empty(value: str, field_name: str) -> str:
    stripped = str(value).strip()
    if not stripped:
        raise ValueError(f"{field_name} cannot be empty.")
    return stripped
