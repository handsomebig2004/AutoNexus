from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


class LLMClient:
    """Unified LLM client for OpenAI and DeepSeek-backed agents."""

    def __init__(self, config_path: str | Path = "config/settings.yaml") -> None:
        self.config_path = Path(config_path)
        self.config = self._load_config(self.config_path)

        llm_config = self.config.get("llm", {})
        self.provider = str(llm_config.get("provider", "openai")).lower()
        self.model_name = llm_config.get("model_name", "gpt-4.1-mini")
        self.temperature = llm_config.get("temperature", 0.2)
        self.max_output_tokens = llm_config.get("max_output_tokens", 2000)
        self.system_prompt = llm_config.get(
            "system_prompt",
            "You are a helpful AI assistant.",
        )

        self.client = self._build_client()

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> str:
        """Send a prompt to the configured provider and return plain text."""
        if not prompt.strip():
            raise ValueError("prompt cannot be empty.")

        system_prompt = system_prompt or self.system_prompt
        temperature = self.temperature if temperature is None else temperature
        max_output_tokens = (
            self.max_output_tokens
            if max_output_tokens is None
            else max_output_tokens
        )

        if self.provider == "openai":
            return self._generate_openai(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )

        if self.provider == "deepseek":
            return self._generate_deepseek(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )

        raise ValueError(f"Unsupported provider: {self.provider}")

    def _load_config(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with path.open("r", encoding="utf-8") as file:
            raw_config = yaml.safe_load(file) or {}

        return self._resolve_env_vars(raw_config)

    def _resolve_env_vars(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._resolve_env_vars(item) for key, item in value.items()}

        if isinstance(value, list):
            return [self._resolve_env_vars(item) for item in value]

        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_name = value[2:-1]
            return os.getenv(env_name, "")

        return value

    def _build_client(self) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "The openai package is required. Install it with: pip install openai"
            ) from exc

        api_config = self.config.get("api", {})

        if self.provider == "openai":
            api_key = api_config.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("Missing OpenAI API key: set OPENAI_API_KEY.")
            return OpenAI(api_key=api_key)

        if self.provider == "deepseek":
            api_key = api_config.get("deepseek_api_key") or os.getenv("DEEPSEEK_API_KEY")
            if not api_key:
                raise ValueError("Missing DeepSeek API key: set DEEPSEEK_API_KEY.")
            return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

        raise ValueError(f"Unsupported provider: {self.provider}")

    def _generate_openai(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_output_tokens: int,
    ) -> str:
        response = self.client.responses.create(
            model=self.model_name,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        if getattr(response, "output_text", None):
            return response.output_text.strip()

        try:
            return response.output[0].content[0].text.strip()
        except (AttributeError, IndexError, TypeError) as exc:
            raise RuntimeError("Failed to parse OpenAI response text.") from exc

    def _generate_deepseek(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_output_tokens: int,
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_output_tokens,
            stream=False,
        )

        try:
            content = response.choices[0].message.content
            return content.strip()
        except (AttributeError, IndexError, TypeError) as exc:
            raise RuntimeError("Failed to parse DeepSeek response text.") from exc
