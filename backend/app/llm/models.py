"""Strongly-typed contracts and configuration models for LLM integrations."""

from pydantic import BaseModel, ConfigDict, Field


class GenerationConfig(BaseModel):
    """Provider-neutral generation parameters for LLM synthesis."""

    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=1024, ge=1, le=8192)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)

    model_config = ConfigDict(frozen=True)


class LLMUsage(BaseModel):
    """Token consumption statistics reported by the provider."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    model_config = ConfigDict(frozen=True)


class LLMResponse(BaseModel):
    """Unified application-level response container from an LLM provider."""

    text: str
    provider: str
    model: str
    usage: LLMUsage | None = None
    finish_reason: str | None = None
    latency_ms: float = 0.0

    model_config = ConfigDict(frozen=True)
