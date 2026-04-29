"""Project-specific error types.

What this file does:
    Defines the exception hierarchy used by agents, tools, generated-code
    runners, and the pipeline. These classes make failures easy to classify.

How it works:
    Each error is a lightweight subclass of AutoNexusError. The classes do not
    retry, log, or repair anything themselves; callers raise these errors and
    the pipeline decides how to handle them.

How to call it:
    from src.utils.errors import LLMOutputParseError

    raise LLMOutputParseError("Requirement agent returned invalid JSON.")
"""

class AutoNexusError(Exception):
    """Base error for the AutoNMD pipeline."""


class ConfigError(AutoNexusError):
    """Invalid or missing configuration."""


class LLMError(AutoNexusError):
    """Base error for LLM provider failures."""


class LLMConnectionError(LLMError):
    """Failed to connect to the LLM provider."""


class LLMResponseError(LLMError):
    """The LLM returned an invalid or unusable response."""


class LLMOutputParseError(LLMResponseError):
    """Failed to parse LLM output into the expected schema."""


class DataLoadError(AutoNexusError):
    """Failed to load input data."""


class DataValidationError(AutoNexusError):
    """Input data failed validation."""


class RequirementValidationError(AutoNexusError):
    """Requirement agent output failed business-rule validation."""


class GeneratedCodeError(AutoNexusError):
    """Base error for generated code problems."""


class GeneratedCodeValidationError(GeneratedCodeError):
    """Generated code failed static validation."""


class GeneratedCodeExecutionError(GeneratedCodeError):
    """Generated code crashed or timed out during execution."""


class PipelineError(AutoNexusError):
    """Pipeline orchestration failed."""
