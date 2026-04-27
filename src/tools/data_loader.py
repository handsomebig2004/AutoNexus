from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.utils.config import get_config_section, load_config


SUPPORTED_TABLE_EXTENSIONS = {
    ".csv",
    ".tsv",
    ".txt",
    ".xlsx",
    ".xls",
    ".json",
    ".jsonl",
    ".ndjson",
    ".parquet",
    ".pkl",
    ".pickle",
}


@dataclass(frozen=True)
class LoadedTable:
    """Loaded tabular data plus lightweight metadata for downstream agents."""

    dataframe: pd.DataFrame
    metadata: dict[str, Any]


def load_table(
    path: str | Path,
    *,
    encoding: str = "utf-8",
    sheet_name: str | int | None = 0,
    **read_kwargs: Any,
) -> LoadedTable:
    """
    Load a common tabular data file into a pandas DataFrame.

    Parameters
    ----------
    path:
        File path. Supported formats: csv, tsv, txt, xlsx, xls, json, jsonl,
        ndjson, parquet, pkl, pickle.
    encoding:
        Text file encoding used by csv/tsv/txt/json/jsonl.
    sheet_name:
        Excel sheet name or index. Defaults to the first sheet.
    **read_kwargs:
        Extra keyword arguments passed to the matching pandas reader.
    """
    data_path = Path(path)
    _validate_path(data_path)

    suffix = data_path.suffix.lower()

    if suffix == ".csv":
        dataframe = pd.read_csv(data_path, encoding=encoding, **read_kwargs)
    elif suffix in {".tsv", ".txt"}:
        dataframe = pd.read_csv(
            data_path,
            sep=read_kwargs.pop("sep", "\t"),
            encoding=encoding,
            **read_kwargs,
        )
    elif suffix in {".xlsx", ".xls"}:
        dataframe = pd.read_excel(data_path, sheet_name=sheet_name, **read_kwargs)
    elif suffix == ".json":
        dataframe = pd.read_json(data_path, encoding=encoding, **read_kwargs)
    elif suffix in {".jsonl", ".ndjson"}:
        dataframe = pd.read_json(
            data_path,
            lines=True,
            encoding=encoding,
            **read_kwargs,
        )
    elif suffix == ".parquet":
        dataframe = pd.read_parquet(data_path, **read_kwargs)
    elif suffix in {".pkl", ".pickle"}:
        dataframe = pd.read_pickle(data_path, **read_kwargs)
    else:
        raise ValueError(
            f"Unsupported data file extension: {suffix}. "
            f"Supported extensions: {sorted(SUPPORTED_TABLE_EXTENSIONS)}"
        )

    metadata = build_table_metadata(data_path, dataframe)
    return LoadedTable(dataframe=dataframe, metadata=metadata)


def load_table_from_config(
    config_path: str | Path = "config/settings.yaml",
    *,
    section: str = "data",
    path_key: str = "path",
    **read_kwargs: Any,
) -> LoadedTable:
    """
    Load a table using a path stored in a YAML config section.

    Example
    -------
    data:
      path: tasks/task_001/data/raw/train.csv
      encoding: utf-8
    """
    config = load_config(config_path)
    data_config = get_config_section(config, section)

    data_path = data_config.get(path_key)
    if not data_path:
        raise ValueError(
            f"Missing data path in config section '{section}' with key '{path_key}'."
        )

    loader_kwargs = {
        key: value
        for key, value in data_config.items()
        if key not in {path_key, "path", "raw_path"}
    }
    loader_kwargs.update(read_kwargs)
    return load_table(data_path, **loader_kwargs)


def build_table_metadata(path: str | Path, dataframe: pd.DataFrame) -> dict[str, Any]:
    """Build a small metadata dictionary that is safe to pass into prompts."""
    data_path = Path(path)
    memory_usage_bytes = int(dataframe.memory_usage(deep=True).sum())

    return {
        "path": str(data_path),
        "file_name": data_path.name,
        "file_extension": data_path.suffix.lower(),
        "file_size_bytes": data_path.stat().st_size if data_path.exists() else None,
        "shape": {
            "rows": int(dataframe.shape[0]),
            "columns": int(dataframe.shape[1]),
        },
        "columns": dataframe.columns.astype(str).tolist(),
        "dtypes": {str(column): str(dtype) for column, dtype in dataframe.dtypes.items()},
        "memory_usage_bytes": memory_usage_bytes,
    }


def list_supported_table_files(directory: str | Path, recursive: bool = False) -> list[Path]:
    """List supported tabular files in a directory."""
    directory_path = Path(directory)
    if not directory_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory_path}")
    if not directory_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory_path}")

    pattern = "**/*" if recursive else "*"
    files = [
        path
        for path in directory_path.glob(pattern)
        if path.is_file() and path.suffix.lower() in SUPPORTED_TABLE_EXTENSIONS
    ]
    return sorted(files)


def _validate_path(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Data path is not a file: {path}")
    if path.suffix.lower() not in SUPPORTED_TABLE_EXTENSIONS:
        raise ValueError(
            f"Unsupported data file extension: {path.suffix.lower()}. "
            f"Supported extensions: {sorted(SUPPORTED_TABLE_EXTENSIONS)}"
        )
