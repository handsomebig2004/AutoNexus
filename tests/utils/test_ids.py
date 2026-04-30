from __future__ import annotations

from src.utils.ids import (
    format_numbered_id,
    next_jsonl_id,
    next_llm_call_id,
    next_numbered_id,
)
from src.utils.io import append_jsonl


def test_format_numbered_id_pads_number():
    # 测试编号格式化会按指定宽度补零。
    assert format_numbered_id("llm", 7) == "llm_0007"
    assert format_numbered_id("run", 12, width=3) == "run_012"


def test_next_numbered_id_ignores_other_prefixes_and_malformed_values():
    # 测试扫描已有 ID 时，会忽略其他前缀和格式错误的值。
    existing = ["llm_0001", "run_9999", "llm_bad", "llm_0010"]

    assert next_numbered_id(existing, "llm") == "llm_0011"


def test_next_jsonl_id_scans_valid_records_and_skips_invalid_lines(tmp_path):
    # 测试从 JSONL 里生成下一个 ID 时，会跳过坏 JSON 和无关字段。
    path = tmp_path / "llm_calls.jsonl"
    path.write_text("{bad json}\n", encoding="utf-8")
    append_jsonl(path, {"llm_call_id": "llm_0003"})
    append_jsonl(path, {"other": "llm_9999"})
    append_jsonl(path, {"llm_call_id": "llm_0008"})

    assert next_jsonl_id(path, "llm_call_id", "llm") == "llm_0009"


def test_next_llm_call_id_returns_start_when_file_is_missing(tmp_path):
    # 测试 llm_calls.jsonl 不存在时，会返回起始 LLM 调用编号。
    assert next_llm_call_id(tmp_path / "missing.jsonl") == "llm_0001"
