"""Identifier generation utilities.

What this file does:
    Generates stable readable IDs such as llm_0001 for logs and pipeline
    artifacts.

How it works:
    format_numbered_id() formats a prefix and number with zero padding.
    next_numbered_id() scans existing IDs and returns the next one.
    next_jsonl_id() scans a JSONL file for a field such as llm_call_id and
    returns the next available ID.

How to call it:
    from src.utils.ids import next_jsonl_id

    llm_call_id = next_jsonl_id("tasks/task_0/logs/llm_calls.jsonl", "llm_call_id", "llm")
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable


def format_numbered_id(prefix: str, number: int, *, width: int = 4) -> str:
    """Format an ID like llm_0001."""
    if number < 0:
        raise ValueError("number cannot be negative.")
    if not prefix.strip():
        raise ValueError("prefix cannot be empty.")
    return f"{prefix.strip()}_{number:0{width}d}"


def next_numbered_id(
    existing_ids: Iterable[str],
    prefix: str,
    *,
    width: int = 4,
    start: int = 1,
) -> str:
    """Return the next ID after scanning existing IDs with the same prefix."""
    max_number = None
    pattern = re.compile(rf"^{re.escape(prefix)}_(\d+)$")

    for value in existing_ids:
        match = pattern.match(str(value))
        if not match:
            continue
        number = int(match.group(1))
        if max_number is None or number > max_number:
            max_number = number

    next_number = start if max_number is None else max_number + 1
    return format_numbered_id(prefix, next_number, width=width)


def next_jsonl_id(
    jsonl_path: str | Path,
    field_name: str,
    prefix: str,
    *,
    width: int = 4,
    start: int = 1,
    encoding: str = "utf-8",
) -> str:
    """Scan a JSONL file and return the next numbered ID for a field."""
    path = Path(jsonl_path)
    if not path.exists():
        return format_numbered_id(prefix, start, width=width)
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    existing_ids: list[str] = []
    with path.open("r", encoding=encoding) as file:
        for line in file:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            value = record.get(field_name)
            if value is not None:
                existing_ids.append(str(value))

    return next_numbered_id(
        existing_ids,
        prefix,
        width=width,
        start=start,
    )


def next_llm_call_id(
    llm_calls_log_path: str | Path,
    *,
    width: int = 4,
    start: int = 1,
) -> str:
    """Return the next llm_XXXX ID from an llm_calls.jsonl file."""
    return next_jsonl_id(
        llm_calls_log_path,
        field_name="llm_call_id",
        prefix="llm",
        width=width,
        start=start,
    )
