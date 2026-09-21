"""Application-level normalized exceptions for LLM provider operations."""

import re
from typing import Any

from app.core.exceptions import LLMException


def sanitize_error_message(message: str) -> str:
    """Strip API keys, tokens, and secrets from error strings."""
    # Redact query param keys, e.g. key=AIza...
    msg = re.sub(r"(?i)(key|api[_-]?key)=([^\s&]+)", r"\1=[REDACTED]", message)
    # Redact Authorization headers or Bearer tokens
    msg = re.sub(r"(?i)(bearer\s+|gsk_)[a-zA-Z0-9_\-\.]{10,}", r"[REDACTED_TOKEN]", msg)
    # Redact sk-... keys
    msg = re.sub(r"(sk-[a-zA-Z0-9_\-]{10,})", r"[REDACTED_KEY]", msg)
    return msg


class ProviderError(LLMException):
    """Base exception for all normalized LLM provider failures."""

    def __init__(
        self,
        message: str,
        provider: str,
        details: dict[str, Any] | None = None,
        status_code: int = 502,
    ):
        clean_message = sanitize_error_message(message)
        super().__init__(message=f"[{provider.upper()}] {clean_message}")
        self.provider = provider
        self.raw_message = clean_message
        self.details = details or {}
        self.status_code = status_code


class ProviderAuthenticationError(ProviderError):
    """Provider API key is invalid, missing, or unauthorized."""

    def __init__(
        self,
        message: str,
        provider: str,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            details=details,
            status_code=401,
        )


class ProviderRateLimitError(ProviderError):
    """Provider rate limit or quota exceeded."""

    def __init__(
        self,
        message: str,
        provider: str,
        retry_after: float | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            details=details,
            status_code=429,
        )
        self.retry_after = retry_after


class ProviderTimeoutError(ProviderError):
    """Provider request timed out."""

    def __init__(
        self,
        message: str,
        provider: str,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            details=details,
            status_code=504,
        )


class ProviderUnavailableError(ProviderError):
    """Provider service is unavailable, overloaded, or unreachable."""

    def __init__(
        self,
        message: str,
        provider: str,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            details=details,
            status_code=503,
        )


class ProviderGenerationError(ProviderError):
    """Provider returned malformed data or failed during generation."""

    def __init__(
        self,
        message: str,
        provider: str,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            details=details,
            status_code=502,
        )
