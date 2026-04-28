"""Shared utility package exports.

What this file does:
    Re-exports the most commonly used utility functions so callers can import
    them from src.utils instead of remembering each module path.

How it works:
    Imports stable, lightweight helpers from config.py and numbered_paths.py,
    then lists the public names in __all__.

How to call it:
    from src.utils import load_config, create_task_directory
"""

from .config import get_config_section, load_config, resolve_env_vars
from .io import (
    append_jsonl,
    read_json,
    read_markdown,
    read_text,
    read_yaml,
    write_json,
    write_markdown,
    write_text,
    write_yaml,
)
from .log_events import (
    EventTimer,
    build_error_data,
    build_error_event,
    build_log_event,
    current_timestamp,
)
from .numbered_paths import (
    create_numbered_directory,
    create_run_directory,
    create_task_directory,
    find_max_numbered_path,
)
from .run_logger import RunLogger
from .task_logger import TaskLogger

__all__ = [
    "append_jsonl",
    "create_numbered_directory",
    "create_run_directory",
    "create_task_directory",
    "current_timestamp",
    "EventTimer",
    "find_max_numbered_path",
    "build_error_data",
    "build_error_event",
    "build_log_event",
    "get_config_section",
    "load_config",
    "read_json",
    "read_markdown",
    "read_text",
    "read_yaml",
    "resolve_env_vars",
    "RunLogger",
    "TaskLogger",
    "write_json",
    "write_markdown",
    "write_text",
    "write_yaml",
]
