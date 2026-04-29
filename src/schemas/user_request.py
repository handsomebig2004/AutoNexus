"""User request schema.

What this file does:
    Defines the normalized input object passed from external interfaces to
    agents or pipeline code.

How it works:
    UserRequest keeps the raw request text together with source metadata. CLI,
    file, stdin, and future web inputs should all be converted into this schema
    before reaching requirement_agent.

How to call it:
    from src.schemas.user_request import UserRequest

    request = UserRequest(request_text="预测客户是否流失", source="stdin")
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


InputSource = Literal["cli", "file", "stdin", "web"]


class UserRequest(BaseModel):
    """Normalized user input for the pipeline."""

    model_config = ConfigDict(extra="forbid")

    request_text: str
    source: InputSource
    source_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("request_text")
    @classmethod
    def _request_text_must_not_be_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("request_text cannot be empty.")
        return stripped

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary."""
        return self.model_dump(mode="json")
