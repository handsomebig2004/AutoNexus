from __future__ import annotations

import pytest

from src.utils.text import (
    extract_fenced_blocks,
    extract_json_text,
    parse_json_from_text,
    strip_code_fence,
)


def test_strip_code_fence_removes_single_surrounding_fence():
    # 测试当整段文本被 Markdown 代码块包住时，可以去掉外层代码围栏。
    assert strip_code_fence("```python\nprint('ok')\n```") == "print('ok')"


def test_extract_fenced_blocks_can_filter_by_language():
    # 测试可以提取多个代码块，并且能按语言筛选指定代码块。
    text = "```python\nprint(1)\n```\n```json\n{\"a\": 1}\n```"

    assert extract_fenced_blocks(text, "json") == ['{"a": 1}']
    assert extract_fenced_blocks(text) == ["print(1)", '{"a": 1}']


def test_extract_json_text_prefers_json_fenced_block():
    # 测试 LLM 回复里存在 json 代码块时，会优先提取该代码块内容。
    text = "Before\n```json\n{\"task\": \"classification\"}\n```\nAfter"

    assert extract_json_text(text) == '{"task": "classification"}'


def test_parse_json_from_text_handles_surrounding_explanation():
    # 测试 JSON 前后带解释文本时，仍然能提取并解析 JSON。
    data = parse_json_from_text('LLM says: {"a": [1, 2], "b": "x"} done.')

    assert data == {"a": [1, 2], "b": "x"}


def test_parse_json_from_text_raises_for_missing_json():
    # 测试文本里完全没有 JSON 时，会抛出清晰的错误。
    with pytest.raises(ValueError, match="No JSON"):
        parse_json_from_text("there is no structured output here")
