"""Reusable tool package exports.

What this file does:
    Exposes convenient imports for tool functions used by agents.

How it works:
    Uses __getattr__ for lazy loading so importing src.tools does not
    immediately import heavier optional dependencies such as pandas.

How to call it:
    from src.tools import load_table

    loaded = load_table("tasks/task_0/data/raw/train.csv")
"""

__all__ = [
    "DataProfile",
    "DataQualityReport",
    "InferredSchema",
    "LoadedTable",
    "check_data_quality",
    "infer_schema",
    "list_supported_table_files",
    "load_table",
    "load_table_from_config",
    "profile_table",
    "profile_table_from_path",
]


def __getattr__(name: str):
    if name in __all__:
        from .data_quality import DataQualityReport, check_data_quality
        from .data_profiler import DataProfile, profile_table, profile_table_from_path
        from .data_loader import (
            LoadedTable,
            list_supported_table_files,
            load_table,
            load_table_from_config,
        )
        from .schema_infer import InferredSchema, infer_schema

        exports = {
            "DataProfile": DataProfile,
            "DataQualityReport": DataQualityReport,
            "InferredSchema": InferredSchema,
            "LoadedTable": LoadedTable,
            "check_data_quality": check_data_quality,
            "infer_schema": infer_schema,
            "list_supported_table_files": list_supported_table_files,
            "load_table": load_table,
            "load_table_from_config": load_table_from_config,
            "profile_table": profile_table,
            "profile_table_from_path": profile_table_from_path,
        }
        return exports[name]

    raise AttributeError(f"module 'src.tools' has no attribute {name!r}")
