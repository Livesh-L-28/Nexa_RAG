"""Deterministic Mock LLM for offline development, testing, and CI."""

import asyncio
import re
import time
from collections.abc import AsyncIterator
from typing import Any

from app.llm.base import BaseLLM
from app.llm.exceptions import (
    ProviderAuthenticationError,
    ProviderGenerationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.llm.models import GenerationConfig, LLMResponse, LLMUsage


class MockLLM(BaseLLM):
    """Deterministic Mock LLM provider that simulates grounded responses and citations."""

    def __init__(
        self,
        model: str = "mock-llm-v1",
        response_delay: float = 0.001,
        simulated_error: str | None = None,
    ):
        self._model = model
        self.response_delay = response_delay
        self.simulated_error = simulated_error

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model

    def _check_simulated_error(self) -> None:
        """Trigger simulated error for testing error normalization and retry handling."""
        if not self.simulated_error:
            return
        err = self.simulated_error.lower()
        if err == "auth":
            raise ProviderAuthenticationError(
                "Invalid API key simulated.", provider=self.provider_name
            )
        if err == "rate_limit":
            raise ProviderRateLimitError(
                "Rate limit exceeded simulated.", provider=self.provider_name, retry_after=2.0
            )
        if err == "timeout":
            raise ProviderTimeoutError("Request timed out simulated.", provider=self.provider_name)
        if err == "unavailable":
            raise ProviderUnavailableError(
                "Service temporarily unavailable simulated.", provider=self.provider_name
            )
        if err == "generation":
            raise ProviderGenerationError(
                "Malformed response simulated.", provider=self.provider_name
            )

    def _create_mock_response(self, prompt: str) -> str:
        """Create a realistic grounded response based on prompt context."""
        sources = re.findall(r"\[Source (\d+)\]", prompt)
        if sources:
            unique_sources = sorted(list(set(sources)), key=lambda x: int(x))
            citation_refs = " ".join([f"[Source {s}]" for s in unique_sources[:2]])
            return (
                f"Based on the provided documents, the information directly addresses your query. "
                f"Specifically, the key findings and details indicate that the system functions as expected {citation_refs}. "
                f"Additional context confirms these observations."
            )
        return (
            "Based on the available context, the requested information was analyzed. "
            "No specific conflicting data was found in the indexed documents."
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        config: GenerationConfig | None = None,
        **kwargs: Any,
    ) -> str:
        res = await self.generate_response(
            prompt, system_prompt=system_prompt, config=config, **kwargs
        )
        return res.text

    async def generate_response(
        self,
        prompt: str,
        system_prompt: str | None = None,
        config: GenerationConfig | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        start_time = time.perf_counter()
        self._check_simulated_error()

        if self.response_delay > 0:
            await asyncio.sleep(self.response_delay)

        text = self._create_mock_response(prompt)
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        # Simulate usage
        in_tokens = max(1, len(prompt.split()))
        out_tokens = max(1, len(text.split()))

        return LLMResponse(
            text=text,
            provider=self.provider_name,
            model=self.model_name,
            usage=LLMUsage(
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                total_tokens=in_tokens + out_tokens,
            ),
            finish_reason="stop",
            latency_ms=round(latency_ms, 2),
        )

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        config: GenerationConfig | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        self._check_simulated_error()

        full_text = self._create_mock_response(prompt)
        words = full_text.split(" ")
        for i, word in enumerate(words):
            token = word if i == len(words) - 1 else word + " "
            if self.response_delay > 0:
                await asyncio.sleep(self.response_delay)
            yield token
