from __future__ import annotations

import json

from src.utils.io import (
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


def test_text_and_markdown_helpers_create_parent_directories(tmp_path):
    # 测试 txt 和 md 写入工具会自动创建父目录，并且能原样读回内容。
    text_path = tmp_path / "nested" / "note.txt"
    markdown_path = tmp_path / "docs" / "readme.md"

    write_text(text_path, "hello")
    write_markdown(markdown_path, "# Title")

    assert read_text(text_path) == "hello"
    assert read_markdown(markdown_path) == "# Title"


def test_json_helpers_round_trip_unicode(tmp_path):
    # 测试 JSON 读写能保留中文内容，并且读回的数据结构一致。
    path = tmp_path / "metadata" / "task.json"
    data = {"name": "客户流失", "metrics": ["f1", "accuracy"]}

    write_json(path, data)

    assert read_json(path) == data
    assert "客户流失" in path.read_text(encoding="utf-8")


def test_yaml_helpers_round_trip(tmp_path):
    # 测试 YAML 读写能完成一次配置字典的往返保存和读取。
    path = tmp_path / "config" / "settings.yaml"
    data = {"llm": {"provider": "openai", "model": "gpt-5-nano"}}

    write_yaml(path, data)

    assert read_yaml(path) == data


def test_append_jsonl_writes_one_json_object_per_line(tmp_path):
    # 测试 JSONL 追加工具会把每条记录写成独立的一行 JSON。
    path = tmp_path / "logs" / "task.jsonl"

    append_jsonl(path, {"event": "task_created"})
    append_jsonl(path, {"event": "agent_finished", "data": {"ok": True}})

    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert records == [
        {"event": "task_created"},
        {"event": "agent_finished", "data": {"ok": True}},
    ]
