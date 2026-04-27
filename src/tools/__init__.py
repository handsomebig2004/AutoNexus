"""Reusable tool integrations for agents."""

__all__ = [
    "LoadedTable",
    "list_supported_table_files",
    "load_table",
    "load_table_from_config",
]


def __getattr__(name: str):
    if name in __all__:
        from .data_loader import (
            LoadedTable,
            list_supported_table_files,
            load_table,
            load_table_from_config,
        )

        exports = {
            "LoadedTable": LoadedTable,
            "list_supported_table_files": list_supported_table_files,
            "load_table": load_table,
            "load_table_from_config": load_table_from_config,
        }
        return exports[name]

    raise AttributeError(f"module 'src.tools' has no attribute {name!r}")
