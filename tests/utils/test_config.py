from __future__ import annotations

import pytest

from src.utils.config import get_config_section, load_config, resolve_env_vars
from src.utils.io import write_yaml


def test_resolve_env_vars_recursively(monkeypatch):
    # 测试配置里的 ${ENV_NAME} 会在字典和列表中递归解析为环境变量。
    monkeypatch.setenv("OPENAI_API_KEY", "secret")

    resolved = resolve_env_vars(
        {
            "api_key": "${OPENAI_API_KEY}",
            "nested": ["${OPENAI_API_KEY}", "plain"],
        }
    )

    assert resolved == {"api_key": "secret", "nested": ["secret", "plain"]}


def test_load_config_reads_yaml_and_resolves_env_vars(tmp_path, monkeypatch):
    # 测试 load_config 会读取 YAML，并解析其中引用的环境变量。
    monkeypatch.setenv("MODEL_NAME", "gpt-5-nano")
    path = tmp_path / "settings.yaml"
    write_yaml(path, {"llm": {"model": "${MODEL_NAME}"}})

    assert load_config(path) == {"llm": {"model": "gpt-5-nano"}}


def test_get_config_section_validates_mapping():
    # 测试读取配置分区时，正常返回字典，并拒绝非字典分区。
    assert get_config_section({"llm": {"provider": "openai"}}, "llm") == {
        "provider": "openai"
    }

    with pytest.raises(ValueError, match="must be a mapping"):
        get_config_section({"llm": "openai"}, "llm")
