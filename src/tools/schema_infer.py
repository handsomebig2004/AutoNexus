"""Schema inference tool for profiled tabular data.

What this file does:
    Infers column semantic types and modeling roles from a data_profiler report.
    The result helps data_agent decide which columns are features, targets,
    identifiers, time indexes, or columns to ignore.

How it works:
    infer_schema() accepts the dictionary returned by profile_table() and an
    optional TaskDefinition. Explicit target/time columns from TaskDefinition
    take priority. Other columns are inferred with deterministic heuristics
    based on names, pandas types, unique rates, missing rates, datetime summary,
    and sample values.

How to call it:
    from src.tools.data_profiler import profile_table
    from src.tools.schema_infer import infer_schema

    profile = profile_table("tasks/task_0/data/raw/train.csv")
    schema = infer_schema(profile, task_definition=task_definition)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from src.schemas.requirement import TaskDefinition


ID_NAME_PATTERN = re.compile(
    r"(^id$|_id$|^id_|identifier|uuid|guid|key$|code$|number$|no$)",
    re.IGNORECASE,
)
TIME_NAME_PATTERN = re.compile(
    r"(date|time|timestamp|datetime|dt$|month|year|day)",
    re.IGNORECASE,
)
TARGET_NAME_PATTERN = re.compile(
    r"(target|label|class|y$|churn|default|fraud|outcome|result|score|price|sales)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class InferredSchema:
    """Structured schema inference result."""

    schema: dict[str, Any]

    def to_json_dict(self) -> dict[str, Any]:
        """Return the JSON-serializable schema dictionary."""
        return self.schema


def infer_schema(
    profile: dict[str, Any],
    *,
    task_definition: TaskDefinition | dict[str, Any] | None = None,
    target_column: str | None = None,
    time_column: str | None = None,
    high_cardinality_threshold: float = 0.8,
    categorical_unique_threshold: int = 20,
) -> dict[str, Any]:
    """
    Infer column roles and semantic types from a data profile.

    Parameters
    ----------
    profile:
        Output from src.tools.data_profiler.profile_table().
    task_definition:
        Optional TaskDefinition or dict. Explicit input_mode.target_column and
        input_mode.time_column values override heuristic inference.
    target_column:
        Optional explicit target column override.
    time_column:
        Optional explicit time column override.
    high_cardinality_threshold:
        Unique-rate threshold used to detect ID-like columns.
    categorical_unique_threshold:
        Maximum unique values for low-cardinality categorical columns.
    """
    task_info = _task_info(task_definition)
    explicit_target = target_column or task_info.get("target_column")
    explicit_time = time_column or task_info.get("time_column")
    task_type = task_info.get("task_type")

    columns = profile.get("columns", [])
    rows = int(profile.get("shape", {}).get("rows", 0) or 0)

    inferred_columns: list[dict[str, Any]] = []
    for column in columns:
        inferred_columns.append(
            _infer_column(
                column,
                rows=rows,
                task_type=task_type,
                explicit_target=explicit_target,
                explicit_time=explicit_time,
                high_cardinality_threshold=high_cardinality_threshold,
                categorical_unique_threshold=categorical_unique_threshold,
            )
        )

    target_columns = [
        column["name"] for column in inferred_columns if column["role"] == "target"
    ]
    time_columns = [
        column["name"] for column in inferred_columns if column["role"] == "time_index"
    ]
    id_columns = [
        column["name"] for column in inferred_columns if column["role"] == "identifier"
    ]
    drop_columns = [
        column["name"] for column in inferred_columns if column["recommended_use"] == "drop"
    ]
    feature_columns = [
        column["name"] for column in inferred_columns if column["role"] == "feature"
    ]
    target_candidates = [
        column["name"]
        for column in inferred_columns
        if column["role"] == "target_candidate"
    ]

    warnings = _build_warnings(
        task_type=task_type,
        explicit_target=explicit_target,
        explicit_time=explicit_time,
        target_columns=target_columns,
        time_columns=time_columns,
        target_candidates=target_candidates,
        profile_columns=[str(column.get("name")) for column in columns],
    )

    return {
        "dataset_name": profile.get("dataset_name"),
        "task_type": task_type,
        "columns": inferred_columns,
        "feature_columns": feature_columns,
        "target_column": target_columns[0] if target_columns else None,
        "target_candidates": target_candidates,
        "id_columns": id_columns,
        "time_columns": time_columns,
        "drop_columns": drop_columns,
        "warnings": warnings,
    }


def _infer_column(
    column: dict[str, Any],
    *,
    rows: int,
    task_type: str | None,
    explicit_target: str | None,
    explicit_time: str | None,
    high_cardinality_threshold: float,
    categorical_unique_threshold: int,
) -> dict[str, Any]:
    name = str(column.get("name", ""))
    normalized_name = name.lower()
    pandas_type = str(column.get("pandas_type", "object"))
    unique_count = int(column.get("unique_count", 0) or 0)
    unique_rate = float(column.get("unique_rate", 0.0) or 0.0)
    missing_rate = float(column.get("missing_rate", 0.0) or 0.0)
    sample_values = column.get("sample_values", []) or []
    has_datetime_summary = bool(column.get("datetime_summary"))

    reasons: list[str] = []

    if explicit_target and _same_column(name, explicit_target):
        semantic_type = _semantic_type_from_profile(
            pandas_type,
            unique_count,
            sample_values,
            has_datetime_summary,
            categorical_unique_threshold,
        )
        return _column_result(
            name=name,
            semantic_type=semantic_type,
            role="target",
            recommended_use="target",
            confidence=1.0,
            reasons=["matches explicit target_column"],
            missing_rate=missing_rate,
        )

    if explicit_time and _same_column(name, explicit_time):
        return _column_result(
            name=name,
            semantic_type="datetime",
            role="time_index",
            recommended_use="time_index",
            confidence=1.0,
            reasons=["matches explicit time_column"],
            missing_rate=missing_rate,
        )

    if has_datetime_summary or pandas_type == "datetime":
        reasons.append("column has datetime summary or datetime dtype")
        role = "time_index" if task_type == "forecasting" else "feature"
        recommended_use = "time_index" if role == "time_index" else "use"
        return _column_result(
            name=name,
            semantic_type="datetime",
            role=role,
            recommended_use=recommended_use,
            confidence=0.9,
            reasons=reasons,
            missing_rate=missing_rate,
        )

    if _is_id_like(
        normalized_name,
        pandas_type=pandas_type,
        unique_rate=unique_rate,
        unique_count=unique_count,
        rows=rows,
        threshold=high_cardinality_threshold,
    ):
        reasons.append("column name or high unique rate indicates identifier")
        return _column_result(
            name=name,
            semantic_type="id",
            role="identifier",
            recommended_use="drop",
            confidence=0.9,
            reasons=reasons,
            missing_rate=missing_rate,
        )

    semantic_type = _semantic_type_from_profile(
        pandas_type,
        unique_count,
        sample_values,
        has_datetime_summary,
        categorical_unique_threshold,
    )
    reasons.append(f"inferred from pandas_type={pandas_type}")

    if (
        task_type in {"classification", "regression", "forecasting"}
        and TARGET_NAME_PATTERN.search(normalized_name)
    ):
        reasons.append("column name looks like a possible target")
        return _column_result(
            name=name,
            semantic_type=semantic_type,
            role="target_candidate",
            recommended_use="review",
            confidence=0.65,
            reasons=reasons,
            missing_rate=missing_rate,
        )

    recommended_use = "use"
    confidence = 0.8
    if semantic_type == "unknown":
        recommended_use = "review"
        confidence = 0.4
        reasons.append("semantic type is uncertain")
    elif semantic_type == "text":
        recommended_use = "use_text"
        confidence = 0.7
        reasons.append("string samples look like free text")
    elif semantic_type == "high_cardinality_categorical":
        recommended_use = "review"
        confidence = 0.65
        reasons.append("categorical column has high cardinality")

    return _column_result(
        name=name,
        semantic_type=semantic_type,
        role="feature",
        recommended_use=recommended_use,
        confidence=confidence,
        reasons=reasons,
        missing_rate=missing_rate,
    )


def _semantic_type_from_profile(
    pandas_type: str,
    unique_count: int,
    sample_values: list[Any],
    has_datetime_summary: bool,
    categorical_unique_threshold: int,
) -> str:
    if has_datetime_summary or pandas_type == "datetime":
        return "datetime"
    if pandas_type == "boolean":
        return "boolean"
    if pandas_type in {"integer", "float", "numeric"}:
        if _looks_binary(sample_values):
            return "boolean"
        return "numeric"
    if pandas_type in {"string", "object", "categorical"}:
        if _looks_like_text(sample_values):
            return "text"
        if unique_count > categorical_unique_threshold:
            return "high_cardinality_categorical"
        return "categorical"
    return "unknown"


def _column_result(
    *,
    name: str,
    semantic_type: str,
    role: str,
    recommended_use: str,
    confidence: float,
    reasons: list[str],
    missing_rate: float,
) -> dict[str, Any]:
    if missing_rate > 0:
        reasons = [*reasons, f"missing_rate={missing_rate}"]
    return {
        "name": name,
        "semantic_type": semantic_type,
        "role": role,
        "recommended_use": recommended_use,
        "confidence": round(confidence, 3),
        "reasons": reasons,
    }


def _is_id_like(
    normalized_name: str,
    *,
    pandas_type: str,
    unique_rate: float,
    unique_count: int,
    rows: int,
    threshold: float,
) -> bool:
    if ID_NAME_PATTERN.search(normalized_name):
        return True
    if (
        pandas_type in {"string", "object"}
        and rows >= 10
        and unique_count == rows
        and unique_rate >= threshold
    ):
        return True
    return False


def _looks_binary(sample_values: list[Any]) -> bool:
    if not sample_values:
        return False
    normalized = {str(value).strip().lower() for value in sample_values}
    binary_sets = [
        {"0", "1"},
        {"true", "false"},
        {"yes", "no"},
        {"y", "n"},
    ]
    return any(normalized.issubset(values) for values in binary_sets)


def _looks_like_text(sample_values: list[Any]) -> bool:
    strings = [value for value in sample_values if isinstance(value, str)]
    if not strings:
        return False
    average_length = sum(len(value) for value in strings) / len(strings)
    contains_spaces = sum(" " in value.strip() for value in strings)
    return average_length >= 40 or contains_spaces >= max(1, len(strings) // 2)


def _same_column(left: str, right: str) -> bool:
    return left.strip().lower() == right.strip().lower()


def _task_info(
    task_definition: TaskDefinition | dict[str, Any] | None,
) -> dict[str, Any]:
    if task_definition is None:
        return {}

    if isinstance(task_definition, TaskDefinition):
        return {
            "task_type": task_definition.task_type,
            "target_column": task_definition.input_mode.target_column,
            "time_column": task_definition.input_mode.time_column,
        }

    input_mode = task_definition.get("input_mode", {}) or {}
    return {
        "task_type": task_definition.get("task_type"),
        "target_column": input_mode.get("target_column"),
        "time_column": input_mode.get("time_column"),
    }


def _build_warnings(
    *,
    task_type: str | None,
    explicit_target: str | None,
    explicit_time: str | None,
    target_columns: list[str],
    time_columns: list[str],
    target_candidates: list[str],
    profile_columns: list[str],
) -> list[str]:
    warnings: list[str] = []

    if explicit_target and not any(_same_column(column, explicit_target) for column in profile_columns):
        warnings.append(f"explicit target_column not found in profile: {explicit_target}")

    if explicit_time and not any(_same_column(column, explicit_time) for column in profile_columns):
        warnings.append(f"explicit time_column not found in profile: {explicit_time}")

    if task_type in {"classification", "regression"} and not target_columns:
        if target_candidates:
            warnings.append(
                "no explicit target column matched; review target_candidates."
            )
        else:
            warnings.append("no target column inferred for supervised task.")

    if task_type == "forecasting" and not time_columns:
        warnings.append("no time_index column inferred for forecasting task.")

    if task_type == "clustering" and target_columns:
        warnings.append("clustering tasks usually should not have a target column.")

    return warnings
