"""Factory for creating LLM provider instances with validation and lazy initialization."""

import logging
from typing import Any

from app.core.config import get_settings
from app.llm.base import BaseLLM
from app.llm.exceptions import ProviderAuthenticationError
from app.llm.gemini import GeminiLLM
from app.llm.groq import GroqLLM
from app.llm.mock import MockLLM

logger = logging.getLogger(__name__)


def get_llm(
    provider: str | None = None,
    require_keys: bool = False,
    **kwargs: Any,
) -> BaseLLM:
    """Return an LLM instance based on provider name or environment settings.

    Args:
        provider: Provider name ('gemini', 'groq', 'mock'). If None, uses LLM_PROVIDER from settings.
        require_keys: If True, raises ProviderAuthenticationError when keys are missing.
                      If False, logs warning and safely falls back to MockLLM for local development/CI.
        **kwargs: Provider-specific overrides (model, timeout, etc.)

    Raises:
        ValueError: If provider is not in ('gemini', 'groq', 'mock').
        ProviderAuthenticationError: If require_keys=True and required credentials are missing.
    """
    settings = get_settings()
    selected = (provider or settings.LLM_PROVIDER).lower()

    if selected == "gemini":
        api_key = kwargs.get("api_key") or settings.GEMINI_API_KEY
        if not api_key:
            if require_keys:
                raise ProviderAuthenticationError(
                    "GEMINI_API_KEY is required but not configured.",
                    provider="gemini",
                )
            logger.warning("GEMINI_API_KEY not configured. Falling back to MockLLM.")
            return MockLLM(**kwargs)
        return GeminiLLM(**kwargs)

    if selected == "groq":
        api_key = kwargs.get("api_key") or settings.GROQ_API_KEY
        if not api_key:
            if require_keys:
                raise ProviderAuthenticationError(
                    "GROQ_API_KEY is required but not configured.",
                    provider="groq",
                )
            logger.warning("GROQ_API_KEY not configured. Falling back to MockLLM.")
            return MockLLM(**kwargs)
        return GroqLLM(**kwargs)

    if selected == "mock":
        return MockLLM(**kwargs)

    raise ValueError(
        f"Unsupported LLM provider '{selected}'. Supported providers: 'gemini', 'groq', 'mock'."
    )
