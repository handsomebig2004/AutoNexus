"""Common file IO utilities.

What this file does:
    Provides one place to read and write JSON, YAML, TXT, and Markdown files.
    This avoids repeating encoding, parent-directory creation, and parser setup
    across agents, tools, and pipeline code.

How it works:
    Text files are read and written with UTF-8 by default. JSON uses the
    standard library json module. YAML imports PyYAML only when YAML helpers are
    called. Write helpers create parent directories before writing.

How to call it:
    from src.utils.io import append_jsonl, read_json, write_json, read_yaml

    config = read_yaml("config/settings.yaml")
    write_json("tasks/task_0/runs/run_0/metadata/metrics.json", {"acc": 0.9})
    append_jsonl("tasks/task_0/logs/task.jsonl", {"event": "task_created"})
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_text(path: str | Path, *, encoding: str = "utf-8") -> str:
    """Read a text file."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    return file_path.read_text(encoding=encoding)


def write_text(
    path: str | Path,
    content: str,
    *,
    encoding: str = "utf-8",
) -> Path:
    """Write a text file, creating parent directories if needed."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding=encoding)
    return file_path


def read_markdown(path: str | Path, *, encoding: str = "utf-8") -> str:
    """Read a Markdown file as text."""
    return read_text(path, encoding=encoding)


def write_markdown(
    path: str | Path,
    content: str,
    *,
    encoding: str = "utf-8",
) -> Path:
    """Write a Markdown file as text, creating parent directories if needed."""
    return write_text(path, content, encoding=encoding)


def read_json(path: str | Path, *, encoding: str = "utf-8") -> Any:
    """Read a JSON file."""
    content = read_text(path, encoding=encoding)
    return json.loads(content)


def write_json(
    path: str | Path,
    data: Any,
    *,
    encoding: str = "utf-8",
    indent: int = 2,
    ensure_ascii: bool = False,
) -> Path:
    """Write data to a JSON file, creating parent directories if needed."""
    content = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)
    return write_text(path, content + "\n", encoding=encoding)


def append_jsonl(
    path: str | Path,
    record: dict[str, Any],
    *,
    encoding: str = "utf-8",
    ensure_ascii: bool = False,
) -> Path:
    """Append one JSON object as one line to a JSONL file."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=ensure_ascii)
    with file_path.open("a", encoding=encoding) as file:
        file.write(line + "\n")
    return file_path


def read_yaml(path: str | Path, *, encoding: str = "utf-8") -> Any:
    """Read a YAML file."""
    try:
        import yaml
    except ImportError as exc:
        raise ImportError(
            "The pyyaml package is required. Install it with: pip install pyyaml"
        ) from exc

    content = read_text(path, encoding=encoding)
    return yaml.safe_load(content)


def write_yaml(
    path: str | Path,
    data: Any,
    *,
    encoding: str = "utf-8",
    sort_keys: bool = False,
    allow_unicode: bool = True,
) -> Path:
    """Write data to a YAML file, creating parent directories if needed."""
    try:
        import yaml
    except ImportError as exc:
        raise ImportError(
            "The pyyaml package is required. Install it with: pip install pyyaml"
        ) from exc

    content = yaml.safe_dump(
        data,
        sort_keys=sort_keys,
        allow_unicode=allow_unicode,
    )
    return write_text(path, content, encoding=encoding)
