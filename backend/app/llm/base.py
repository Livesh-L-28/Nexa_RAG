"""Abstract Base Class for provider-independent LLM integrations."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from app.llm.models import GenerationConfig, LLMResponse


class BaseLLM(ABC):
    """Abstract interface for LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g. 'gemini', 'groq', 'mock')."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Configured model identifier."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        config: GenerationConfig | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate a complete text response given a prompt and optional system prompt."""

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        system_prompt: str | None = None,
        config: GenerationConfig | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a normalized LLMResponse with text, model, usage, and latency."""

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        config: GenerationConfig | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Yield text tokens asynchronously as they are generated."""
