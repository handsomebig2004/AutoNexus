from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def load_config(config_path: str | Path = "config/settings.yaml") -> dict[str, Any]:
    """Load a YAML config file and resolve ${ENV_VAR} style values."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    try:
        import yaml
    except ImportError as exc:
        raise ImportError(
            "The pyyaml package is required. Install it with: pip install pyyaml"
        ) from exc

    with path.open("r", encoding="utf-8") as file:
        raw_config = yaml.safe_load(file) or {}

    if not isinstance(raw_config, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {path}")

    return resolve_env_vars(raw_config)


def resolve_env_vars(value: Any) -> Any:
    """Recursively resolve values like ${OPENAI_API_KEY} from environment vars."""
    if isinstance(value, dict):
        return {key: resolve_env_vars(item) for key, item in value.items()}

    if isinstance(value, list):
        return [resolve_env_vars(item) for item in value]

    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_name = value[2:-1]
        return os.getenv(env_name, "")

    return value


def get_config_section(
    config: dict[str, Any],
    section: str,
    *,
    default: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a named config section and validate that it is a mapping."""
    section_config = config.get(section, default or {})
    if not isinstance(section_config, dict):
        raise ValueError(f"Config section '{section}' must be a mapping.")
    return section_config
