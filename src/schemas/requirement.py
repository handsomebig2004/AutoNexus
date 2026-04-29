"""Requirement agent output schema.

What this file does:
    Defines the structured output that requirement_agent must produce after
    translating a natural-language user request into a modeling task.

How it works:
    Pydantic validates that task_type is one of the supported task categories
    and that decision controls whether the pipeline can continue. Only accepted
    tasks are modelable. need_info and rejected tasks are returned to the user.

How to call it:
    from src.schemas.requirement import TaskDefinition

    task_definition = TaskDefinition.model_validate(llm_json)
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


TaskType = Literal[
    "classification",
    "regression",
    "forecasting",
    "clustering",
    "unknown",
]

RequirementDecision = Literal[
    "accepted",
    "need_info",
    "rejected",
]

DataType = Literal[
    "tabular",
    "text",
    "image",
    "time_series",
    "multimodal",
    "unknown",
]

PredictionType = Literal[
    "class_label",
    "probability",
    "numeric_value",
    "future_value",
    "cluster_id",
    "unknown",
]


class InputMode(BaseModel):
    """Input information needed to model the task."""

    model_config = ConfigDict(extra="forbid")

    data_type: DataType = "unknown"
    required_inputs: list[str] = Field(default_factory=list)
    optional_inputs: list[str] = Field(default_factory=list)
    target_column: str | None = None
    id_columns: list[str] = Field(default_factory=list)
    time_column: str | None = None
    data_granularity: str | None = None
    known_data_sources: list[str] = Field(default_factory=list)


class OutputMode(BaseModel):
    """Expected model output information."""

    model_config = ConfigDict(extra="forbid")

    prediction_type: PredictionType = "unknown"
    target_description: str = ""
    output_format: str = ""


class Constraints(BaseModel):
    """Hard and soft constraints extracted from the user request."""

    model_config = ConfigDict(extra="forbid")

    must_have: list[str] = Field(default_factory=list)
    must_not: list[str] = Field(default_factory=list)
    resource_limits: list[str] = Field(default_factory=list)
    privacy_or_safety: list[str] = Field(default_factory=list)


class EvaluationPlan(BaseModel):
    """Metrics and validation strategy recommended for the task."""

    model_config = ConfigDict(extra="forbid")

    primary_metric: str = ""
    secondary_metrics: list[str] = Field(default_factory=list)
    validation_strategy: str = ""
    metric_reasoning: str = ""


class DownstreamNotes(BaseModel):
    """Hints passed to later agents."""

    model_config = ConfigDict(extra="forbid")

    for_research_agent: list[str] = Field(default_factory=list)
    for_data_agent: list[str] = Field(default_factory=list)
    for_train_agent: list[str] = Field(default_factory=list)
    for_evaluation_agent: list[str] = Field(default_factory=list)


class TaskDefinition(BaseModel):
    """Full requirement_agent output."""

    model_config = ConfigDict(extra="forbid")

    task_name: str
    task_type: TaskType
    decision: RequirementDecision
    should_model: bool
    problem_statement: str
    input_mode: InputMode
    output_mode: OutputMode
    constraints: Constraints = Field(default_factory=Constraints)
    evaluation: EvaluationPlan = Field(default_factory=EvaluationPlan)
    assumptions: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    user_facing_response: str = ""
    downstream_notes: DownstreamNotes = Field(default_factory=DownstreamNotes)
    raw_user_request: str = ""

    @field_validator("task_name", "problem_statement")
    @classmethod
    def _must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field cannot be empty.")
        return value.strip()

    @model_validator(mode="after")
    def _decision_controls_modeling(self) -> "TaskDefinition":
        if self.task_type == "unknown":
            self.decision = "rejected"

        if self.decision == "accepted":
            self.should_model = True
            if self.task_type == "unknown":
                raise ValueError("accepted tasks cannot have task_type='unknown'.")
            if self.missing_information:
                raise ValueError("accepted tasks cannot include missing_information.")
            return self

        self.should_model = False

        if self.decision == "need_info":
            if self.task_type == "unknown":
                raise ValueError("need_info tasks must still have a supported task_type.")
            if not self.missing_information:
                raise ValueError("need_info tasks must include missing_information.")
            if not self.user_facing_response.strip():
                self.user_facing_response = "当前需求可以建模，但缺少关键信息，请补充后再继续。"

        if self.decision == "rejected":
            self.task_type = "unknown"
            self.should_model = False
            if not self.user_facing_response.strip():
                self.user_facing_response = (
                    "当前需求不能明确归类为 classification、regression、"
                    "forecasting 或 clustering，因此暂不进入自动建模。"
                )

        return self

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary."""
        return self.model_dump(mode="json")
