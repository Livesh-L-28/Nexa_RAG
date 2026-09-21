"""Controlled transient failure retry policy with exponential backoff."""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

import httpx

from app.llm.exceptions import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderGenerationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

TRANSIENT_EXCEPTIONS = (
    ProviderTimeoutError,
    ProviderUnavailableError,
    httpx.TimeoutException,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
)

NON_RETRYABLE_EXCEPTIONS = (
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderGenerationError,
)


async def execute_with_retry(
    func: Callable[[], Coroutine[Any, Any, T]],
    provider: str,
    max_retries: int = 2,
    base_backoff_seconds: float = 0.5,
    max_backoff_seconds: float = 3.0,
) -> T:
    """Execute async operation with bounded exponential backoff on transient errors."""
    attempts = 0
    while True:
        try:
            return await func()
        except NON_RETRYABLE_EXCEPTIONS as e:
            # Fatal error, do not retry
            logger.warning(f"Non-retryable error in {provider}: {e}")
            raise
        except TRANSIENT_EXCEPTIONS as e:
            attempts += 1
            if attempts > max_retries:
                logger.error(
                    f"Max retries ({max_retries}) exceeded for {provider} on transient error: {e}"
                )
                if isinstance(e, ProviderError):
                    raise
                if isinstance(e, (httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout)):
                    raise ProviderTimeoutError(f"Request timed out: {e}", provider=provider) from e
                raise ProviderUnavailableError(f"Network error: {e}", provider=provider) from e

            delay = min(max_backoff_seconds, base_backoff_seconds * (2 ** (attempts - 1)))
            logger.info(
                f"Transient error in {provider}: {e}. Retrying attempt {attempts}/{max_retries} in {delay:.2f}s..."
            )
            await asyncio.sleep(delay)
        except Exception as e:
            # Check if this wraps a non-retryable exception
            if isinstance(e, ProviderError):
                raise
            raise ProviderGenerationError(f"Unexpected error: {e}", provider=provider) from e
