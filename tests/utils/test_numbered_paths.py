from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from src.utils.numbered_paths import (
    create_numbered_directory,
    create_run_directory,
    create_task_directory,
    find_max_numbered_path,
)


def test_find_max_numbered_path_only_counts_matching_directories(tmp_path):
    # 测试只统计符合 prefix_数字 格式的目录，不统计文件或其他前缀。
    (tmp_path / "task_0").mkdir()
    (tmp_path / "task_9").mkdir()
    (tmp_path / "task_bad").mkdir()
    (tmp_path / "run_99").mkdir()
    (tmp_path / "task_50.txt").write_text("not a directory", encoding="utf-8")

    assert find_max_numbered_path(tmp_path, "task") == 9


def test_create_numbered_directory_creates_next_directory(tmp_path):
    # 测试创建编号目录时，会基于当前最大编号创建下一个目录。
    (tmp_path / "task_0").mkdir()
    (tmp_path / "task_2").mkdir()

    created = create_numbered_directory(tmp_path, "task")

    assert created == tmp_path / "task_3"
    assert created.is_dir()


def test_create_task_and_run_directory_helpers(tmp_path):
    # 测试 task 和 run 的快捷创建函数会使用约定好的前缀。
    task_dir = create_task_directory(tmp_path)
    run_dir = create_run_directory(task_dir / "runs")

    assert task_dir.name == "task_0"
    assert run_dir.name == "run_0"


def test_create_numbered_directory_is_safe_for_concurrent_callers(tmp_path):
    # 测试多个并发调用不会拿到重复的编号目录。
    with ThreadPoolExecutor(max_workers=4) as executor:
        paths = list(
            executor.map(
                lambda _: create_numbered_directory(tmp_path, "task"),
                range(8),
            )
        )

    names = sorted(path.name for path in paths)
    assert names == [f"task_{index}" for index in range(8)]
