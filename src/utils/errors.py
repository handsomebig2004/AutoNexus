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


class GeneratedCodeError(AutoNexusError):
    """Base error for generated code problems."""


class GeneratedCodeValidationError(GeneratedCodeError):
    """Generated code failed static validation."""


class GeneratedCodeExecutionError(GeneratedCodeError):
    """Generated code crashed or timed out during execution."""


class PipelineError(AutoNexusError):
    """Pipeline orchestration failed."""
