"""Tabular data profiling tool.

What this file does:
    Builds a deterministic, JSON-serializable overview of a tabular dataset.
    The profile is meant to be passed to data_agent before asking an LLM to
    write preprocessing code.

How it works:
    profile_table() accepts a pandas DataFrame, a file path, or a LoadedTable.
    It reports dataset shape, memory usage, duplicate rows, and per-column
    statistics such as dtype, missing rate, unique count, sample values,
    numeric summary, datetime summary, and top value counts.

How to call it:
    from src.tools.data_profiler import profile_table

    profile = profile_table("tasks/task_0/data/raw/train.csv")
    profile["shape"]
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.tools.data_loader import LoadedTable, load_table


@dataclass(frozen=True)
class DataProfile:
    """Structured dataset profile returned by profile_table()."""

    profile: dict[str, Any]

    def to_json_dict(self) -> dict[str, Any]:
        """Return the JSON-serializable profile dictionary."""
        return self.profile


def profile_table(
    data: pd.DataFrame | LoadedTable | str | Path,
    *,
    dataset_name: str | None = None,
    max_sample_values: int = 5,
    max_top_values: int = 10,
    max_columns: int | None = None,
    include_value_counts: bool = True,
    **load_kwargs: Any,
) -> dict[str, Any]:
    """
    Build a JSON-serializable profile for a tabular dataset.

    Parameters
    ----------
    data:
        pandas DataFrame, LoadedTable, or supported tabular file path.
    dataset_name:
        Optional display name. If omitted, file paths use their file name.
    max_sample_values:
        Maximum non-null sample values stored for each column.
    max_top_values:
        Maximum top value counts stored for each column.
    max_columns:
        Optional cap on the number of columns profiled in detail.
    include_value_counts:
        Whether to include top value counts for each column.
    **load_kwargs:
        Extra keyword arguments passed to load_table() when data is a path.
    """
    dataframe, metadata = _coerce_dataframe(data, **load_kwargs)
    name = dataset_name or metadata.get("file_name") or "dataframe"

    columns_to_profile = list(dataframe.columns)
    truncated_columns: list[str] = []
    if max_columns is not None and len(columns_to_profile) > max_columns:
        truncated_columns = [str(column) for column in columns_to_profile[max_columns:]]
        columns_to_profile = columns_to_profile[:max_columns]

    profile = {
        "dataset_name": name,
        "source": metadata,
        "shape": {
            "rows": int(dataframe.shape[0]),
            "columns": int(dataframe.shape[1]),
            "profiled_columns": int(len(columns_to_profile)),
            "truncated_columns": truncated_columns,
        },
        "columns": [
            _profile_column(
                dataframe[column],
                max_sample_values=max_sample_values,
                max_top_values=max_top_values,
                include_value_counts=include_value_counts,
            )
            for column in columns_to_profile
        ],
        "duplicate_row_count": int(dataframe.duplicated().sum()),
        "memory_usage_bytes": int(dataframe.memory_usage(deep=True).sum()),
    }
    return _json_safe(profile)


def profile_table_from_path(
    path: str | Path,
    *,
    dataset_name: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Load a table from path and profile it."""
    return profile_table(path, dataset_name=dataset_name, **kwargs)


def _coerce_dataframe(
    data: pd.DataFrame | LoadedTable | str | Path,
    **load_kwargs: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if isinstance(data, pd.DataFrame):
        return data, {"source_type": "dataframe"}

    if isinstance(data, LoadedTable):
        metadata = dict(data.metadata)
        metadata["source_type"] = "loaded_table"
        return data.dataframe, metadata

    if isinstance(data, (str, Path)):
        loaded = load_table(data, **load_kwargs)
        metadata = dict(loaded.metadata)
        metadata["source_type"] = "path"
        return loaded.dataframe, metadata

    raise TypeError(
        "data must be a pandas DataFrame, LoadedTable, string path, or Path."
    )


def _profile_column(
    series: pd.Series,
    *,
    max_sample_values: int,
    max_top_values: int,
    include_value_counts: bool,
) -> dict[str, Any]:
    non_null = series.dropna()
    row_count = len(series)
    missing_count = int(series.isna().sum())
    unique_count = int(series.nunique(dropna=True))

    column_profile: dict[str, Any] = {
        "name": str(series.name),
        "dtype": str(series.dtype),
        "pandas_type": _infer_pandas_type(series),
        "non_null_count": int(non_null.shape[0]),
        "missing_count": missing_count,
        "missing_rate": _safe_ratio(missing_count, row_count),
        "unique_count": unique_count,
        "unique_rate": _safe_ratio(unique_count, int(non_null.shape[0])),
        "sample_values": _sample_values(non_null, max_sample_values),
    }

    if include_value_counts:
        column_profile["top_values"] = _top_values(non_null, max_top_values)

    if pd.api.types.is_numeric_dtype(series):
        column_profile["numeric_summary"] = _numeric_summary(non_null)

    datetime_series = _as_datetime_if_possible(series)
    if datetime_series is not None:
        column_profile["datetime_summary"] = _datetime_summary(datetime_series)

    return column_profile


def _infer_pandas_type(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    if pd.api.types.is_float_dtype(series):
        return "float"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if isinstance(series.dtype, pd.CategoricalDtype):
        return "categorical"
    if pd.api.types.is_string_dtype(series):
        return "string"
    return "object"


def _numeric_summary(non_null: pd.Series) -> dict[str, Any]:
    if non_null.empty:
        return {
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "std": None,
        }

    numeric = pd.to_numeric(non_null, errors="coerce").dropna()
    if numeric.empty:
        return {
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "std": None,
        }

    return {
        "min": _json_safe(numeric.min()),
        "max": _json_safe(numeric.max()),
        "mean": _json_safe(numeric.mean()),
        "median": _json_safe(numeric.median()),
        "std": _json_safe(numeric.std(ddof=1)) if len(numeric) > 1 else 0.0,
    }


def _as_datetime_if_possible(series: pd.Series) -> pd.Series | None:
    if pd.api.types.is_datetime64_any_dtype(series):
        return series.dropna()

    if not (
        pd.api.types.is_object_dtype(series)
        or pd.api.types.is_string_dtype(series)
    ):
        return None

    non_null = series.dropna()
    if non_null.empty:
        return None

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        parsed = pd.to_datetime(non_null, errors="coerce")
    parse_rate = parsed.notna().mean()
    if parse_rate < 0.8:
        return None
    return parsed.dropna()


def _datetime_summary(non_null_datetime: pd.Series) -> dict[str, Any]:
    if non_null_datetime.empty:
        return {
            "min": None,
            "max": None,
        }

    return {
        "min": _json_safe(non_null_datetime.min()),
        "max": _json_safe(non_null_datetime.max()),
    }


def _sample_values(non_null: pd.Series, max_sample_values: int) -> list[Any]:
    if max_sample_values <= 0:
        return []
    return [
        _json_safe(value)
        for value in non_null.drop_duplicates().head(max_sample_values).tolist()
    ]


def _top_values(non_null: pd.Series, max_top_values: int) -> list[dict[str, Any]]:
    if max_top_values <= 0 or non_null.empty:
        return []

    counts = non_null.value_counts(dropna=True).head(max_top_values)
    total = int(non_null.shape[0])
    return [
        {
            "value": _json_safe(value),
            "count": int(count),
            "rate": _safe_ratio(int(count), total),
        }
        for value, count in counts.items()
    ]


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if pd.isna(value) if not isinstance(value, (list, dict, tuple)) else False:
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except (ValueError, TypeError):
            pass
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value
