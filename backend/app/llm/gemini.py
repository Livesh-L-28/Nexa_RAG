"""Google Gemini LLM provider implementation."""

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


class GeminiLLM(BaseLLM):
    """Hardened Gemini API client using Google Generative Language REST API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.LLM_MODEL or settings.GEMINI_MODEL or "gemini-2.0-flash"
        self.timeout = timeout or getattr(settings, "LLM_TIMEOUT_SECONDS", 60.0)
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self.model

    def _prepare_payload(
        self,
        prompt: str,
        system_prompt: str | None,
        config: GenerationConfig | None,
    ) -> dict[str, Any]:
        temp = config.temperature if config else settings.LLM_TEMPERATURE
        max_toks = config.max_output_tokens if config else settings.LLM_MAX_TOKENS
        top_p = config.top_p if config else None

        gen_config: dict[str, Any] = {
            "temperature": temp,
            "maxOutputTokens": max_toks,
        }
        if top_p is not None:
            gen_config["topP"] = top_p

        payload: dict[str, Any] = {
            "contents": [
                {
                    "parts": [{"text": prompt}],
                    "role": "user",
                }
            ],
            "generationConfig": gen_config,
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        return payload

    def _normalize_http_error(self, status_code: int, response_text: str) -> ProviderError:
        clean_text = sanitize_error_message(response_text)
        if status_code in (400, 401, 403):
            return ProviderAuthenticationError(
                f"Gemini authentication failed ({status_code}): {clean_text}",
                provider=self.provider_name,
            )
        if status_code == 429:
            return ProviderRateLimitError(
                f"Gemini rate limit or quota exceeded: {clean_text}",
                provider=self.provider_name,
            )
        if status_code == 503:
            return ProviderUnavailableError(
                f"Gemini service unavailable ({status_code}): {clean_text}",
                provider=self.provider_name,
            )
        if status_code == 504:
            return ProviderTimeoutError(
                f"Gemini gateway timeout: {clean_text}",
                provider=self.provider_name,
            )
        return ProviderGenerationError(
            f"Gemini request failed ({status_code}): {clean_text}",
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
                "Gemini API key is missing. Set GEMINI_API_KEY in environment.",
                provider=self.provider_name,
            )

        url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
        payload = self._prepare_payload(prompt, system_prompt, config)
        start_time = time.perf_counter()

        async def _call():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                if response.status_code != 200:
                    raise self._normalize_http_error(response.status_code, response.text)
                return response.json()

        data = await execute_with_retry(
            _call,
            provider=self.provider_name,
            max_retries=getattr(settings, "LLM_MAX_RETRIES", 2),
        )

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        candidates = data.get("candidates", [])
        if not candidates:
            return LLMResponse(
                text="",
                provider=self.provider_name,
                model=self.model_name,
                latency_ms=round(latency_ms, 2),
            )

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts)
        finish_reason = candidates[0].get("finishReason")

        usage_meta = data.get("usageMetadata", {})
        usage = None
        if usage_meta:
            usage = LLMUsage(
                input_tokens=usage_meta.get("promptTokenCount"),
                output_tokens=usage_meta.get("candidatesTokenCount"),
                total_tokens=usage_meta.get("totalTokenCount"),
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
                "Gemini API key is missing. Set GEMINI_API_KEY in environment.",
                provider=self.provider_name,
            )

        url = f"{self.base_url}/{self.model}:streamGenerateContent?alt=sse&key={self.api_key}"
        payload = self._prepare_payload(prompt, system_prompt, config)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        raise self._normalize_http_error(response.status_code, body.decode())

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            raw_data = line[6:].strip()
                            try:
                                chunk = json.loads(raw_data)
                                candidates = chunk.get("candidates", [])
                                if candidates:
                                    parts = candidates[0].get("content", {}).get("parts", [])
                                    for part in parts:
                                        text = part.get("text", "")
                                        if text:
                                            yield text
                            except json.JSONDecodeError:
                                continue
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(
                f"Gemini streaming timed out: {e}", provider=self.provider_name
            ) from e
        except httpx.RequestError as e:
            raise ProviderUnavailableError(
                f"Gemini streaming connection error: {e}", provider=self.provider_name
            ) from e
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderGenerationError(
                f"Gemini stream processing error: {e}", provider=self.provider_name
            ) from e
