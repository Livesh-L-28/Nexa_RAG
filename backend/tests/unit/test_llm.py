"""Comprehensive unit and property tests for Phase 12: LLM Provider Integration Hardening."""

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.llm.exceptions import (
    ProviderAuthenticationError,
    ProviderGenerationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    sanitize_error_message,
)
from app.llm.factory import get_llm
from app.llm.gemini import GeminiLLM
from app.llm.groq import GroqLLM
from app.llm.mock import MockLLM
from app.llm.models import GenerationConfig
from app.llm.retry import execute_with_retry

# ============================================================================
# 1. Factory Tests
# ============================================================================


def test_create_gemini_provider():
    """Verify factory initializes GeminiLLM with valid API key or Mock fallback."""
    # When api key provided
    llm = get_llm(provider="gemini", api_key="dummy_key")
    assert isinstance(llm, GeminiLLM)
    assert llm.provider_name == "gemini"

    # When require_keys=True and no key
    with pytest.raises(ProviderAuthenticationError):
        get_llm(provider="gemini", api_key="", require_keys=True)


def test_create_groq_provider():
    """Verify factory initializes GroqLLM with valid API key or Mock fallback."""
    llm = get_llm(provider="groq", api_key="gsk_dummy_key")
    assert isinstance(llm, GroqLLM)
    assert llm.provider_name == "groq"

    with pytest.raises(ProviderAuthenticationError):
        get_llm(provider="groq", api_key="", require_keys=True)


def test_create_mock_provider():
    """Verify factory initializes MockLLM correctly without credentials."""
    llm = get_llm(provider="mock")
    assert isinstance(llm, MockLLM)
    assert llm.provider_name == "mock"
    assert llm.model_name == "mock-llm-v1"


def test_unknown_provider():
    """Verify factory raises ValueError for unsupported provider names."""
    with pytest.raises(ValueError, match="Unsupported LLM provider 'openai'"):
        get_llm(provider="openai")

    with pytest.raises(ValueError, match="Unsupported LLM provider 'claude'"):
        get_llm(provider="claude")


# ============================================================================
# 2. Configuration Tests
# ============================================================================


def test_generation_config():
    """Verify custom GenerationConfig values are validated and frozen."""
    config = GenerationConfig(temperature=0.7, max_output_tokens=2048, top_p=0.95)
    assert config.temperature == 0.7
    assert config.max_output_tokens == 2048
    assert config.top_p == 0.95

    with pytest.raises(ValidationError):
        config.temperature = 0.5  # Frozen


def test_default_generation_config():
    """Verify default GenerationConfig parameters."""
    config = GenerationConfig()
    assert config.temperature == 0.2
    assert config.max_output_tokens == 1024
    assert config.top_p is None


def test_invalid_generation_config():
    """Verify invalid GenerationConfig parameters are rejected."""
    with pytest.raises(ValidationError):
        GenerationConfig(temperature=3.5)  # le=2.0

    with pytest.raises(ValidationError):
        GenerationConfig(max_output_tokens=0)  # ge=1

    with pytest.raises(ValidationError):
        GenerationConfig(top_p=1.5)  # le=1.0


# ============================================================================
# 3. Security Tests
# ============================================================================


def test_api_key_not_logged():
    """Verify API keys in query parameters and headers are sanitized."""
    raw_error = "Failed request to https://api.groq.com?key=AIzaSySecret123 with Bearer gsk_abc1234567890def"
    sanitized = sanitize_error_message(raw_error)

    assert "AIzaSySecret123" not in sanitized
    assert "gsk_abc1234567890def" not in sanitized
    assert "[REDACTED]" in sanitized or "[REDACTED_TOKEN]" in sanitized


def test_api_key_not_returned():
    """Verify ProviderError does not expose raw keys in message or str output."""
    err = ProviderAuthenticationError(
        message="Failed auth on key=super_secret_key_val",
        provider="gemini",
    )
    assert "super_secret_key_val" not in str(err)
    assert "super_secret_key_val" not in err.message
    assert "[REDACTED]" in str(err)


# ============================================================================
# 4. Error Normalization Tests
# ============================================================================


def test_authentication_error():
    """Verify ProviderAuthenticationError sets 401 status and formatted code."""
    err = ProviderAuthenticationError("Invalid API key", provider="groq")
    assert err.status_code == 401
    assert err.provider == "groq"
    assert "[GROQ]" in str(err)


def test_rate_limit_error():
    """Verify ProviderRateLimitError records retry_after and status 429."""
    err = ProviderRateLimitError("Quota exceeded", provider="gemini", retry_after=15.0)
    assert err.status_code == 429
    assert err.retry_after == 15.0
    assert err.provider == "gemini"


def test_timeout_error():
    """Verify ProviderTimeoutError sets 504 status code."""
    err = ProviderTimeoutError("Gateway timed out", provider="groq")
    assert err.status_code == 504
    assert err.provider == "groq"


def test_provider_unavailable():
    """Verify ProviderUnavailableError sets 503 status code."""
    err = ProviderUnavailableError("503 Service Unavailable", provider="gemini")
    assert err.status_code == 503
    assert err.provider == "gemini"


def test_generation_error():
    """Verify ProviderGenerationError sets 502 status code."""
    err = ProviderGenerationError("Malformed JSON candidate", provider="groq")
    assert err.status_code == 502
    assert err.provider == "groq"


# ============================================================================
# 5. Retry Policy Tests
# ============================================================================


@pytest.mark.asyncio
async def test_transient_failure_retries():
    """Verify transient timeout errors are retried up to max_retries before succeeding."""
    call_count = 0

    async def _failing_then_success():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ProviderTimeoutError("Temporary timeout", provider="mock")
        return "Success on retry"

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await execute_with_retry(
            _failing_then_success,
            provider="mock",
            max_retries=2,
            base_backoff_seconds=0.01,
        )
    assert result == "Success on retry"
    assert call_count == 2


@pytest.mark.asyncio
async def test_auth_failure_not_retried():
    """Verify authentication errors are never retried."""
    call_count = 0

    async def _auth_failure():
        nonlocal call_count
        call_count += 1
        raise ProviderAuthenticationError("Bad key", provider="mock")

    with pytest.raises(ProviderAuthenticationError):
        await execute_with_retry(_auth_failure, provider="mock", max_retries=3)

    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_limit():
    """Verify retries stop after max_retries on persistent transient failure."""
    call_count = 0

    async def _always_timeout():
        nonlocal call_count
        call_count += 1
        raise ProviderTimeoutError("Persistent timeout", provider="mock")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(ProviderTimeoutError):
            await execute_with_retry(
                _always_timeout,
                provider="mock",
                max_retries=2,
                base_backoff_seconds=0.01,
            )

    assert call_count == 3  # initial + 2 retries


# ============================================================================
# 6. Mock Provider Tests
# ============================================================================


@pytest.mark.asyncio
async def test_mock_generation():
    """Verify MockLLM returns grounded simulated responses."""
    llm = MockLLM()
    prompt = "What is NexaRAG? [Source 1]\n[Source 2]"
    answer = await llm.generate(prompt)

    assert "Based on the provided documents" in answer
    assert "[Source 1]" in answer
    assert "[Source 2]" in answer


@pytest.mark.asyncio
async def test_mock_streaming():
    """Verify MockLLM streams tokens progressively."""
    llm = MockLLM()
    tokens = []
    async for token in llm.generate_stream("Summarize system architecture."):
        tokens.append(token)

    full = "".join(tokens)
    assert len(tokens) >= 5
    assert "Based on the available context" in full or "Based on the provided documents" in full


# ============================================================================
# 7. Streaming Tests
# ============================================================================


@pytest.mark.asyncio
async def test_streaming_tokens():
    """Verify stream correctly delivers discrete token chunks."""
    llm = MockLLM(response_delay=0.0)
    received = []
    async for chunk in llm.generate_stream("Tell me about indexing."):
        received.append(chunk)

    assert len(received) > 0
    assert all(isinstance(c, str) for c in received)


@pytest.mark.asyncio
async def test_streaming_completion():
    """Verify stream finishes cleanly and reconstitutes complete sentence."""
    llm = MockLLM(response_delay=0.0)
    chunks = [c async for c in llm.generate_stream("Test prompt")]
    reconstituted = "".join(chunks)
    assert len(reconstituted.strip()) > 0
    assert reconstituted.endswith(".")


@pytest.mark.asyncio
async def test_streaming_provider_error():
    """Verify simulated streaming provider error is caught and normalized."""
    llm = MockLLM(simulated_error="rate_limit")

    with pytest.raises(ProviderRateLimitError) as exc_info:
        async for _ in llm.generate_stream("Stream under rate limit"):
            pass

    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after == 2.0


# ============================================================================
# 8. Metadata Tests
# ============================================================================


@pytest.mark.asyncio
async def test_provider_metadata():
    """Verify LLMResponse accurately exposes provider name."""
    llm = MockLLM()
    resp = await llm.generate_response("Test prompt")
    assert resp.provider == "mock"
    assert llm.provider_name == "mock"


@pytest.mark.asyncio
async def test_model_metadata():
    """Verify LLMResponse exposes configured model identifier."""
    llm = MockLLM(model="mock-custom-v2")
    resp = await llm.generate_response("Test prompt")
    assert resp.model == "mock-custom-v2"
    assert llm.model_name == "mock-custom-v2"


@pytest.mark.asyncio
async def test_usage_metadata():
    """Verify LLMResponse contains valid token usage accounting."""
    llm = MockLLM()
    resp = await llm.generate_response("Short prompt for testing tokens.")
    assert resp.usage is not None
    assert resp.usage.input_tokens > 0
    assert resp.usage.output_tokens > 0
    assert resp.usage.total_tokens == resp.usage.input_tokens + resp.usage.output_tokens
    assert resp.latency_ms >= 0.0
