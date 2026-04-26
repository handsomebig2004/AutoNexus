"""Reusable tool integrations for agents."""

__all__ = [
    "LoadedTable",
    "list_supported_table_files",
    "load_table",
]


def __getattr__(name: str):
    if name in __all__:
        from .data_loader import LoadedTable, list_supported_table_files, load_table

        exports = {
            "LoadedTable": LoadedTable,
            "list_supported_table_files": list_supported_table_files,
            "load_table": load_table,
        }
        return exports[name]

    raise AttributeError(f"module 'src.tools' has no attribute {name!r}")
