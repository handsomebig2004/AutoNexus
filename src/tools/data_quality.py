"""Data quality checking tool for profiled tabular data.

What this file does:
    Checks a data_profiler report, optional inferred schema, and optional
    TaskDefinition for deterministic data quality risks before data_agent writes
    preprocessing code.

How it works:
    check_data_quality() inspects missing rates, constant columns, duplicate
    rows, target availability, class balance, feature availability, ID leakage
    risk, high-cardinality categoricals, and forecasting time index presence.
    It returns JSON-serializable issues with severity, blocking flag, evidence,
    and recommendations.

How to call it:
    from src.tools.data_profiler import profile_table
    from src.tools.schema_infer import infer_schema
    from src.tools.data_quality import check_data_quality

    profile = profile_table("tasks/task_0/data/raw/train.csv")
    schema = infer_schema(profile, task_definition=task_definition)
    quality = check_data_quality(profile, schema=schema, task_definition=task_definition)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.schemas.requirement import TaskDefinition


@dataclass(frozen=True)
class DataQualityReport:
    """Structured data quality report."""

    report: dict[str, Any]

    def to_json_dict(self) -> dict[str, Any]:
        """Return the JSON-serializable report dictionary."""
        return self.report


def check_data_quality(
    profile: dict[str, Any],
    *,
    schema: dict[str, Any] | None = None,
    task_definition: TaskDefinition | dict[str, Any] | None = None,
    high_missing_rate: float = 0.4,
    class_imbalance_rate: float = 0.9,
    min_rows_warning: int = 50,
) -> dict[str, Any]:
    """
    Check data quality risks from a data profile and optional schema.

    Parameters
    ----------
    profile:
        Output from src.tools.data_profiler.profile_table().
    schema:
        Optional output from src.tools.schema_infer.infer_schema().
    task_definition:
        Optional TaskDefinition or dict. Used to understand task_type and
        explicit target/time columns.
    high_missing_rate:
        Missing-rate threshold for high_missing_rate warnings.
    class_imbalance_rate:
        Top-class rate threshold for class imbalance warnings.
    min_rows_warning:
        Row-count threshold below which a warning is emitted.
    """
    task_info = _task_info(task_definition)
    task_type = schema.get("task_type") if schema else None
    task_type = task_type or task_info.get("task_type")

    columns = profile.get("columns", [])
    columns_by_name = {str(column.get("name")): column for column in columns}
    schema_columns = _schema_columns_by_name(schema)
    target_column = _target_column(schema, task_info)
    time_columns = list(schema.get("time_columns", []) if schema else [])
    feature_columns = list(schema.get("feature_columns", []) if schema else [])
    rows = int(profile.get("shape", {}).get("rows", 0) or 0)

    issues: list[dict[str, Any]] = []

    _check_dataset_size(issues, rows=rows, min_rows_warning=min_rows_warning)
    _check_duplicate_rows(issues, profile)
    _check_column_missingness(
        issues,
        columns=columns,
        high_missing_rate=high_missing_rate,
    )
    _check_constant_columns(issues, columns=columns, schema_columns=schema_columns)
    _check_schema_feature_availability(
        issues,
        feature_columns=feature_columns,
        schema=schema,
    )
    _check_target_quality(
        issues,
        task_type=task_type,
        target_column=target_column,
        columns_by_name=columns_by_name,
        class_imbalance_rate=class_imbalance_rate,
    )
    _check_forecasting_time_index(
        issues,
        task_type=task_type,
        time_columns=time_columns,
        columns_by_name=columns_by_name,
    )
    _check_schema_risks(
        issues,
        schema_columns=schema_columns,
        feature_columns=feature_columns,
    )

    summary = _build_summary(issues)
    return {
        "dataset_name": profile.get("dataset_name"),
        "task_type": task_type,
        "issues": issues,
        "summary": summary,
        "recommended_actions": [
            issue["recommendation"] for issue in issues if issue["blocking"]
        ]
        or [issue["recommendation"] for issue in issues if issue["severity"] == "warning"],
        "can_continue": summary["blocking_issue_count"] == 0,
    }


def _check_dataset_size(
    issues: list[dict[str, Any]],
    *,
    rows: int,
    min_rows_warning: int,
) -> None:
    if rows == 0:
        issues.append(
            _issue(
                "empty_dataset",
                "error",
                [],
                "Dataset has zero rows.",
                "Provide a non-empty dataset before modeling.",
                blocking=True,
                evidence={"rows": rows},
            )
        )
    elif rows < min_rows_warning:
        issues.append(
            _issue(
                "too_few_rows",
                "warning",
                [],
                f"Dataset has only {rows} rows.",
                "Review whether there is enough data for reliable modeling.",
                evidence={"rows": rows, "min_rows_warning": min_rows_warning},
            )
        )


def _check_duplicate_rows(issues: list[dict[str, Any]], profile: dict[str, Any]) -> None:
    duplicate_count = int(profile.get("duplicate_row_count", 0) or 0)
    rows = int(profile.get("shape", {}).get("rows", 0) or 0)
    if duplicate_count <= 0:
        return

    issues.append(
        _issue(
            "duplicate_rows",
            "warning",
            [],
            f"Dataset contains {duplicate_count} duplicate rows.",
            "Consider dropping duplicate rows during preprocessing.",
            evidence={
                "duplicate_row_count": duplicate_count,
                "duplicate_rate": _safe_ratio(duplicate_count, rows),
            },
        )
    )


def _check_column_missingness(
    issues: list[dict[str, Any]],
    *,
    columns: list[dict[str, Any]],
    high_missing_rate: float,
) -> None:
    for column in columns:
        name = str(column.get("name"))
        missing_rate = float(column.get("missing_rate", 0.0) or 0.0)
        non_null_count = int(column.get("non_null_count", 0) or 0)

        if non_null_count == 0:
            issues.append(
                _issue(
                    "all_missing_column",
                    "error",
                    [name],
                    f"Column {name} is entirely missing.",
                    "Drop the column or provide data for it before modeling.",
                    blocking=True,
                    evidence={"missing_rate": missing_rate},
                )
            )
        elif missing_rate >= high_missing_rate:
            issues.append(
                _issue(
                    "high_missing_rate",
                    "warning",
                    [name],
                    f"Column {name} has high missing rate.",
                    "Consider imputation, dropping the column, or asking the user to confirm its meaning.",
                    evidence={"missing_rate": missing_rate},
                )
            )


def _check_constant_columns(
    issues: list[dict[str, Any]],
    *,
    columns: list[dict[str, Any]],
    schema_columns: dict[str, dict[str, Any]],
) -> None:
    for column in columns:
        name = str(column.get("name"))
        unique_count = int(column.get("unique_count", 0) or 0)
        non_null_count = int(column.get("non_null_count", 0) or 0)
        role = schema_columns.get(name, {}).get("role")
        if role == "target":
            continue
        if non_null_count > 0 and unique_count <= 1:
            issues.append(
                _issue(
                    "constant_column",
                    "warning",
                    [name],
                    f"Column {name} has only one non-null value.",
                    "Drop constant columns during preprocessing.",
                    evidence={"unique_count": unique_count},
                )
            )


def _check_schema_feature_availability(
    issues: list[dict[str, Any]],
    *,
    feature_columns: list[str],
    schema: dict[str, Any] | None,
) -> None:
    if schema is None:
        return
    if not feature_columns:
        issues.append(
            _issue(
                "no_feature_columns",
                "error",
                [],
                "No usable feature columns were inferred.",
                "Review schema inference or provide feature columns before modeling.",
                blocking=True,
            )
        )


def _check_target_quality(
    issues: list[dict[str, Any]],
    *,
    task_type: str | None,
    target_column: str | None,
    columns_by_name: dict[str, dict[str, Any]],
    class_imbalance_rate: float,
) -> None:
    if task_type not in {"classification", "regression", "forecasting"}:
        return

    if not target_column:
        issues.append(
            _issue(
                "target_missing",
                "error",
                [],
                "No target column is available for a supervised task.",
                "Ask the user to provide or confirm the target column.",
                blocking=True,
            )
        )
        return

    target = columns_by_name.get(target_column)
    if target is None:
        issues.append(
            _issue(
                "target_not_found",
                "error",
                [target_column],
                f"Target column {target_column} is not present in the profile.",
                "Check the data file or requirement definition target_column.",
                blocking=True,
            )
        )
        return

    missing_rate = float(target.get("missing_rate", 0.0) or 0.0)
    unique_count = int(target.get("unique_count", 0) or 0)
    if missing_rate > 0:
        issues.append(
            _issue(
                "target_missing_values",
                "error",
                [target_column],
                f"Target column {target_column} contains missing values.",
                "Drop rows with missing target or ask the user to provide complete labels.",
                blocking=True,
                evidence={"missing_rate": missing_rate},
            )
        )

    if task_type == "classification":
        if unique_count < 2:
            issues.append(
                _issue(
                    "target_single_class",
                    "error",
                    [target_column],
                    f"Target column {target_column} has fewer than two classes.",
                    "Provide labels with at least two classes before classification.",
                    blocking=True,
                    evidence={"unique_count": unique_count},
                )
            )
        _check_class_imbalance(
            issues,
            target=target,
            target_column=target_column,
            class_imbalance_rate=class_imbalance_rate,
        )


def _check_class_imbalance(
    issues: list[dict[str, Any]],
    *,
    target: dict[str, Any],
    target_column: str,
    class_imbalance_rate: float,
) -> None:
    top_values = target.get("top_values", []) or []
    if not top_values:
        return
    top = top_values[0]
    top_rate = float(top.get("rate", 0.0) or 0.0)
    unique_count = int(target.get("unique_count", 0) or 0)
    if unique_count >= 2 and top_rate >= class_imbalance_rate:
        issues.append(
            _issue(
                "class_imbalance",
                "warning",
                [target_column],
                f"Target column {target_column} is highly imbalanced.",
                "Use stratified splitting and imbalance-aware metrics or resampling.",
                evidence={
                    "top_value": top.get("value"),
                    "top_rate": top_rate,
                    "unique_count": unique_count,
                },
            )
        )


def _check_forecasting_time_index(
    issues: list[dict[str, Any]],
    *,
    task_type: str | None,
    time_columns: list[str],
    columns_by_name: dict[str, dict[str, Any]],
) -> None:
    if task_type != "forecasting":
        return
    if not time_columns:
        issues.append(
            _issue(
                "time_index_missing",
                "error",
                [],
                "No time index column is available for forecasting.",
                "Ask the user to provide or confirm the time column.",
                blocking=True,
            )
        )
        return

    for column_name in time_columns:
        column = columns_by_name.get(column_name)
        if column and not column.get("datetime_summary"):
            issues.append(
                _issue(
                    "time_index_not_parseable",
                    "warning",
                    [column_name],
                    f"Time column {column_name} was not profiled as parseable datetime.",
                    "Parse and validate the time column during preprocessing.",
                    evidence={"pandas_type": column.get("pandas_type")},
                )
            )


def _check_schema_risks(
    issues: list[dict[str, Any]],
    *,
    schema_columns: dict[str, dict[str, Any]],
    feature_columns: list[str],
) -> None:
    for column_name, column in schema_columns.items():
        semantic_type = column.get("semantic_type")
        role = column.get("role")
        recommended_use = column.get("recommended_use")

        if semantic_type == "high_cardinality_categorical":
            issues.append(
                _issue(
                    "high_cardinality_categorical",
                    "warning",
                    [column_name],
                    f"Column {column_name} is a high-cardinality categorical feature.",
                    "Avoid naive one-hot encoding; consider hashing, target encoding with care, or dropping it.",
                    evidence={
                        "role": role,
                        "recommended_use": recommended_use,
                    },
                )
            )

        if role == "identifier" and column_name in feature_columns:
            issues.append(
                _issue(
                    "possible_id_leakage",
                    "warning",
                    [column_name],
                    f"Identifier column {column_name} is included as a feature.",
                    "Remove ID-like columns from model features unless explicitly justified.",
                    evidence={"semantic_type": semantic_type},
                )
            )


def _issue(
    issue_type: str,
    severity: str,
    columns: list[str],
    message: str,
    recommendation: str,
    *,
    blocking: bool = False,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "issue_type": issue_type,
        "severity": severity,
        "columns": columns,
        "message": message,
        "recommendation": recommendation,
        "blocking": blocking,
        "evidence": evidence or {},
    }


def _build_summary(issues: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "error_count": sum(1 for issue in issues if issue["severity"] == "error"),
        "warning_count": sum(1 for issue in issues if issue["severity"] == "warning"),
        "info_count": sum(1 for issue in issues if issue["severity"] == "info"),
        "blocking_issue_count": sum(1 for issue in issues if issue["blocking"]),
    }


def _schema_columns_by_name(schema: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not schema:
        return {}
    return {str(column.get("name")): column for column in schema.get("columns", [])}


def _target_column(
    schema: dict[str, Any] | None,
    task_info: dict[str, Any],
) -> str | None:
    if schema and schema.get("target_column"):
        return str(schema["target_column"])
    if task_info.get("target_column"):
        return str(task_info["target_column"])
    return None


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


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)
