"""Text extraction helpers for LLM outputs.

What this file does:
    Provides small helpers for cleaning LLM responses and extracting JSON or
    fenced code blocks from text.

How it works:
    extract_json_text() first looks for a fenced ```json block. If none exists,
    it falls back to finding the first balanced JSON object or array in the
    text. parse_json_from_text() then parses that JSON string with json.loads().

How to call it:
    from src.utils.text import parse_json_from_text

    data = parse_json_from_text(llm_response)
"""

from __future__ import annotations

import json
import re
from typing import Any


FENCED_BLOCK_PATTERN = re.compile(
    r"```(?P<language>[A-Za-z0-9_-]*)\s*\n(?P<content>.*?)```",
    re.DOTALL,
)


def strip_code_fence(text: str) -> str:
    """Remove one surrounding Markdown code fence if the whole text is fenced."""
    stripped = text.strip()
    match = FENCED_BLOCK_PATTERN.fullmatch(stripped)
    if not match:
        return stripped
    return match.group("content").strip()


def extract_fenced_blocks(text: str, language: str | None = None) -> list[str]:
    """Extract Markdown fenced code blocks, optionally filtered by language."""
    blocks: list[str] = []
    expected_language = language.lower() if language else None

    for match in FENCED_BLOCK_PATTERN.finditer(text):
        block_language = match.group("language").lower()
        if expected_language and block_language != expected_language:
            continue
        blocks.append(match.group("content").strip())

    return blocks


def extract_json_text(text: str) -> str:
    """Extract the first JSON object or array from an LLM response."""
    for block in extract_fenced_blocks(text, "json"):
        if block:
            return block

    stripped = strip_code_fence(text)
    if stripped.startswith("{") or stripped.startswith("["):
        return _extract_balanced_json(stripped)

    return _extract_balanced_json(text)


def parse_json_from_text(text: str) -> Any:
    """Extract and parse JSON from an LLM response."""
    json_text = extract_json_text(text)
    return json.loads(json_text)


def _extract_balanced_json(text: str) -> str:
    start = _find_json_start(text)
    if start is None:
        raise ValueError("No JSON object or array found in text.")

    opening = text[start]
    closing = "}" if opening == "{" else "]"
    depth = 0
    in_string = False
    escape = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return text[start : index + 1].strip()

    raise ValueError("JSON object or array is not balanced.")


def _find_json_start(text: str) -> int | None:
    object_index = text.find("{")
    array_index = text.find("[")

    candidates = [index for index in [object_index, array_index] if index != -1]
    if not candidates:
        return None
    return min(candidates)
