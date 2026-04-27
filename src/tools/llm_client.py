"""LLM API client tool.

What this file does:
    Provides one unified class, LLMClient, for calling external LLM providers
    used by agents. It currently supports OpenAI and DeepSeek.

How it works:
    LLMClient reads config/settings.yaml through src.utils.config, selects the
    provider, resolves the model name, builds an OpenAI-compatible SDK client,
    and exposes generate(prompt). OpenAI uses the Responses API; DeepSeek uses
    the OpenAI-compatible chat completions API. If a model rejects temperature,
    the request is retried once without temperature.

How to call it:
    from src.tools.llm_client import LLMClient

    client = LLMClient()
    text = client.generate("用一句话说明你是否能正常工作。")
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.utils.config import get_config_section, load_config


class LLMClient:
    """Unified LLM client for OpenAI and DeepSeek-backed agents."""

    def __init__(self, config_path: str | Path = "config/settings.yaml") -> None:
        self.config_path = Path(config_path)
        self.config = load_config(self.config_path)

        llm_config = get_config_section(self.config, "llm")
        self.provider = str(llm_config.get("provider", "openai")).lower()
        self.model_name = self._resolve_model_name(llm_config.get("model_name"))
        self.temperature = llm_config.get("temperature", 0.2)
        self.max_output_tokens = llm_config.get("max_output_tokens", 2000)
        self.system_prompt = llm_config.get(
            "system_prompt",
            "You are a helpful AI assistant.",
        )

        self.client = self._build_client()

    def _resolve_model_name(self, model_name: Any) -> str:
        if model_name is not None and str(model_name).strip():
            return str(model_name).strip()

        default_models = {
            "openai": "gpt-5-nano",
            "deepseek": "deepseek-v4-flash",
        }
        try:
            return default_models[self.provider]
        except KeyError as exc:
            raise ValueError(f"Unsupported provider: {self.provider}") from exc

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

    def _build_client(self) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "The openai package is required. Install it with: pip install openai"
            ) from exc

        api_config = get_config_section(self.config, "api")

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
        temperature: float | None,
        max_output_tokens: int,
    ) -> str:
        request_params = {
            "model": self.model_name,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "max_output_tokens": max_output_tokens,
        }
        response = self._create_response_with_optional_temperature(
            create_fn=self.client.responses.create,
            request_params=request_params,
            temperature=temperature,
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
        temperature: float | None,
        max_output_tokens: int,
    ) -> str:
        request_params = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_output_tokens,
            "stream": False,
        }
        response = self._create_response_with_optional_temperature(
            create_fn=self.client.chat.completions.create,
            request_params=request_params,
            temperature=temperature,
        )

        try:
            content = response.choices[0].message.content
            return content.strip()
        except (AttributeError, IndexError, TypeError) as exc:
            raise RuntimeError("Failed to parse DeepSeek response text.") from exc

    def _create_response_with_optional_temperature(
        self,
        create_fn: Any,
        request_params: dict[str, Any],
        temperature: float | None,
    ) -> Any:
        if temperature is None:
            return create_fn(**request_params)

        try:
            return create_fn(**request_params, temperature=temperature)
        except Exception as exc:
            if self._is_unsupported_temperature_error(exc):
                return create_fn(**request_params)
            raise

    def _is_unsupported_temperature_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        unsupported_markers = [
            "unsupported parameter",
            "not supported",
            "does not support",
            "unknown parameter",
            "unrecognized request argument",
            "only the default",
        ]
        return "temperature" in message and any(
            marker in message for marker in unsupported_markers
        )
