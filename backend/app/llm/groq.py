"""Groq LLM provider implementation."""

import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import get_settings
from app.llm.base import BaseLLM
from app.llm.exceptions import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderGenerationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    sanitize_error_message,
)
from app.llm.models import GenerationConfig, LLMResponse, LLMUsage
from app.llm.retry import execute_with_retry

logger = logging.getLogger(__name__)
settings = get_settings()


class GroqLLM(BaseLLM):
    """Hardened Groq API client using high-speed async HTTP."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model or settings.LLM_MODEL or settings.GROQ_MODEL or "llama-3.3-70b-versatile"
        self.timeout = timeout or getattr(settings, "LLM_TIMEOUT_SECONDS", 60.0)
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self.model

    def _prepare_messages(self, prompt: str, system_prompt: str | None) -> list[dict[str, str]]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _prepare_payload(
        self,
        prompt: str,
        system_prompt: str | None,
        config: GenerationConfig | None,
        stream: bool = False,
    ) -> dict[str, Any]:
        temp = config.temperature if config else settings.LLM_TEMPERATURE
        max_toks = config.max_output_tokens if config else settings.LLM_MAX_TOKENS
        top_p = config.top_p if config else None

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._prepare_messages(prompt, system_prompt),
            "temperature": temp,
            "max_tokens": max_toks,
            "stream": stream,
        }
        if top_p is not None:
            payload["top_p"] = top_p
        return payload

    def _normalize_http_error(
        self, status_code: int, response_text: str, headers: Any = None
    ) -> ProviderError:
        clean_text = sanitize_error_message(response_text)
        if status_code in (400, 401, 403):
            return ProviderAuthenticationError(
                f"Groq authentication failed ({status_code}): {clean_text}",
                provider=self.provider_name,
            )
        if status_code == 429:
            retry_after = None
            if headers:
                try:
                    val = headers.get("retry-after")
                    if val:
                        retry_after = float(val)
                except (ValueError, TypeError):
                    pass
            return ProviderRateLimitError(
                f"Groq rate limit exceeded: {clean_text}",
                provider=self.provider_name,
                retry_after=retry_after,
            )
        if status_code == 503:
            return ProviderUnavailableError(
                f"Groq service unavailable ({status_code}): {clean_text}",
                provider=self.provider_name,
            )
        if status_code == 504:
            return ProviderTimeoutError(
                f"Groq gateway timeout: {clean_text}",
                provider=self.provider_name,
            )
        return ProviderGenerationError(
            f"Groq request failed ({status_code}): {clean_text}",
            provider=self.provider_name,
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
        if not self.api_key:
            raise ProviderAuthenticationError(
                "Groq API key is missing. Set GROQ_API_KEY in environment.",
                provider=self.provider_name,
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = self._prepare_payload(prompt, system_prompt, config, stream=False)
        start_time = time.perf_counter()

        async def _call():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.base_url, json=payload, headers=headers)
                if response.status_code != 200:
                    raise self._normalize_http_error(
                        response.status_code, response.text, response.headers
                    )
                return response.json()

        data = await execute_with_retry(
            _call,
            provider=self.provider_name,
            max_retries=getattr(settings, "LLM_MAX_RETRIES", 2),
        )

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        choices = data.get("choices", [])
        if not choices:
            return LLMResponse(
                text="",
                provider=self.provider_name,
                model=self.model_name,
                latency_ms=round(latency_ms, 2),
            )

        text = choices[0].get("message", {}).get("content", "")
        finish_reason = choices[0].get("finish_reason")

        raw_usage = data.get("usage", {})
        usage = None
        if raw_usage:
            usage = LLMUsage(
                input_tokens=raw_usage.get("prompt_tokens"),
                output_tokens=raw_usage.get("completion_tokens"),
                total_tokens=raw_usage.get("total_tokens"),
            )

        return LLMResponse(
            text=text,
            provider=self.provider_name,
            model=self.model_name,
            usage=usage,
            finish_reason=finish_reason,
            latency_ms=round(latency_ms, 2),
        )

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        config: GenerationConfig | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        if not self.api_key:
            raise ProviderAuthenticationError(
                "Groq API key is missing. Set GROQ_API_KEY in environment.",
                provider=self.provider_name,
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = self._prepare_payload(prompt, system_prompt, config, stream=True)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST", self.base_url, json=payload, headers=headers
                ) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        raise self._normalize_http_error(
                            response.status_code, body.decode(), response.headers
                        )

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            raw_data = line[6:].strip()
                            if raw_data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(raw_data)
                                choices = chunk.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(
                f"Groq streaming timed out: {e}", provider=self.provider_name
            ) from e
        except httpx.RequestError as e:
            raise ProviderUnavailableError(
                f"Groq streaming connection error: {e}", provider=self.provider_name
            ) from e
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderGenerationError(
                f"Groq stream processing error: {e}", provider=self.provider_name
            ) from e
