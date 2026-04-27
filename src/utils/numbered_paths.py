from __future__ import annotations

import re
from pathlib import Path

from filelock import FileLock, Timeout


def find_max_numbered_path(parent_dir: str | Path, prefix: str) -> int | None:
    """Find the largest number in child directory names like task_135."""
    parent_path = Path(parent_dir)
    if not parent_path.exists():
        return None
    if not parent_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {parent_path}")

    pattern = re.compile(rf"^{re.escape(prefix)}_(\d+)$")
    max_number: int | None = None

    for child in parent_path.iterdir():
        if not child.is_dir():
            continue

        match = pattern.match(child.name)
        if not match:
            continue

        number = int(match.group(1))
        if max_number is None or number > max_number:
            max_number = number

    return max_number


def create_numbered_directory(
    parent_dir: str | Path,
    prefix: str,
    *,
    lock_timeout: float = 10,
) -> Path:
    """
    Create and return the next available path/prefix_xxx directory.

    Example: if parent_dir contains task_135, this creates and returns
    parent_dir/task_136. If no matching directory exists, it creates task_0.
    A file lock prevents concurrent callers from receiving the same path.
    """
    parent_path = Path(parent_dir)
    parent_path.mkdir(parents=True, exist_ok=True)

    lock_path = parent_path / f".{prefix}.lock"
    try:
        with FileLock(lock_path, timeout=lock_timeout):
            while True:
                max_number = find_max_numbered_path(parent_path, prefix)
                next_number = 0 if max_number is None else max_number + 1
                numbered_path = parent_path / f"{prefix}_{next_number}"

                try:
                    numbered_path.mkdir()
                    return numbered_path
                except FileExistsError:
                    continue
    except Timeout as exc:
        raise TimeoutError(
            f"Timed out while waiting for numbered directory lock: {lock_path}"
        ) from exc


def create_task_directory(
    tasks_dir: str | Path = "tasks",
    *,
    lock_timeout: float = 10,
) -> Path:
    """Create and return the next tasks_dir/task_xxx directory."""
    return create_numbered_directory(tasks_dir, "task", lock_timeout=lock_timeout)


def create_run_directory(
    runs_dir: str | Path,
    *,
    lock_timeout: float = 10,
) -> Path:
    """Create and return the next runs_dir/run_xxx directory."""
    return create_numbered_directory(runs_dir, "run", lock_timeout=lock_timeout)
