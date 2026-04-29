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
from .ids import (
    format_numbered_id,
    next_jsonl_id,
    next_llm_call_id,
    next_numbered_id,
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
from .requirement_validation import (
    RequirementGateValidation,
    normalize_requirement_gate,
    validate_requirement_for_modeling,
)
from .run_logger import RunLogger
from .task_logger import TaskLogger
from .text import (
    extract_fenced_blocks,
    extract_json_text,
    parse_json_from_text,
    strip_code_fence,
)

__all__ = [
    "append_jsonl",
    "create_numbered_directory",
    "create_run_directory",
    "create_task_directory",
    "current_timestamp",
    "EventTimer",
    "extract_fenced_blocks",
    "extract_json_text",
    "find_max_numbered_path",
    "format_numbered_id",
    "build_error_data",
    "build_error_event",
    "build_log_event",
    "get_config_section",
    "load_config",
    "next_jsonl_id",
    "next_llm_call_id",
    "next_numbered_id",
    "normalize_requirement_gate",
    "parse_json_from_text",
    "read_json",
    "read_markdown",
    "read_text",
    "read_yaml",
    "resolve_env_vars",
    "RequirementGateValidation",
    "RunLogger",
    "strip_code_fence",
    "TaskLogger",
    "validate_requirement_for_modeling",
    "write_json",
    "write_markdown",
    "write_text",
    "write_yaml",
]
