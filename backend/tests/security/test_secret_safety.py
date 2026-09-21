"""Secret Protection, Logging Redaction & Error Safety Tests (Invariants S16, Steps 21, 22, 23, 28).

Verifies that:
1. No production secrets or credentials are hardcoded in source files.
2. Structured logs redact sensitive keys (passwords, tokens, API keys, authorization headers, prompts).
3. Production API error responses do not leak database connection strings, stack traces, or credentials.
4. LLM provider exceptions return controlled HTTP 502/500 errors without corrupting state.
"""

import json
import logging
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.core.exceptions import LLMProviderError
from app.core.logging import JSONFormatter
from app.observability.logger import sanitize_payload


def test_no_hardcoded_secrets_in_tracked_source():
    """Scan tracked Python source code to verify no live API keys or passwords are hardcoded."""
    backend_root = Path(__file__).parent.parent.parent
    app_dir = backend_root / "app"

    # Regex patterns for accidental live keys
    suspicious_patterns = [
        re.compile(r"""AIzaSy[0-9A-Za-z_-]{33}"""),  # Google Gemini API key format
        re.compile(r"""gsk_[0-9A-Za-z]{48,}"""),  # Groq API key format
        re.compile(r"""ghp_[0-9A-Za-z]{36}"""),  # GitHub PAT
        re.compile(r"""(?:password|passwd|pwd)\s*=\s*['"][^'"]{8,}['"]""", re.IGNORECASE),
    ]

    # Whitelist of mock/dev tokens allowed in code
    whitelist = {
        "password123",
        "admin12345",
        "password456",
        "nexarag-insecure-dev-secret-key-change-in-production-min32chars",
        "test_super_secret_jwt_key_at_least_32_chars_long",
    }

    violations = []
    for py_file in app_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        for pat in suspicious_patterns:
            matches = pat.findall(text)
            for m in matches:
                # Check if in whitelist
                if not any(wl in m for wl in whitelist):
                    violations.append(f"{py_file.name}: {m}")

    assert len(violations) == 0, f"Potential hardcoded secrets detected: {violations}"


def test_json_formatter_redacts_sensitive_fields():
    """JSONFormatter must replace sensitive keys with [REDACTED]."""
    formatter = JSONFormatter()

    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="User authentication event",
        args=(),
        exc_info=None,
    )
    record.extra_data = {
        "user_email": "user@example.com",
        "password": "super_secret_plain_password",
        "token": "bearer_jwt_token_value",
        "api_key": "gemini_secret_api_key",
        "authorization": "Bearer eyJhbGciOi...",
        "raw_prompt": "Confidential prompt text",
        "normal_metric": 42,
    }

    formatted = formatter.format(record)
    data = json.loads(formatted)
    extra = data["data"]

    assert extra["password"] == "[REDACTED]"
    assert extra["token"] == "[REDACTED]"
    assert extra["api_key"] == "[REDACTED]"
    assert extra["authorization"] == "[REDACTED]"
    assert extra["raw_prompt"] == "[REDACTED]"
    assert extra["normal_metric"] == 42
    assert "super_secret_plain_password" not in formatted


def test_observability_logger_redacts_sensitive_payload():
    """ObservabilityLogger.sanitize_payload must recursively redact sensitive tokens."""
    payload = {
        "user_id": "12345",
        "auth_details": {
            "bearer_token": "secret_token_123",
            "api_key": "live_groq_key",
        },
        "items": [
            {"chunk_content": "Confidential nuclear blueprint", "score": 0.95},
            {"memory_content": "User secret financial balance", "score": 0.88},
        ],
    }

    sanitized = sanitize_payload(payload)
    assert sanitized["auth_details"]["bearer_token"] == "[REDACTED]"
    assert sanitized["auth_details"]["api_key"] == "[REDACTED]"
    assert sanitized["items"][0]["chunk_content"] == "[REDACTED]"
    assert sanitized["items"][1]["memory_content"] == "[REDACTED]"
    assert sanitized["items"][0]["score"] == 0.95


@pytest.mark.asyncio
async def test_error_response_masks_internal_details():
    """500 internal server errors must return a sanitized error message and never leak tracebacks."""
    from starlette.requests import Request

    from app.main import unhandled_exception_handler

    req = Request(
        scope={"type": "http", "method": "GET", "path": "/api/v1/chat/sessions", "headers": []}
    )
    exc = RuntimeError(
        "psycopg2.OperationalError: password authentication failed for user 'postgres'"
    )
    response = await unhandled_exception_handler(req, exc)
    assert response.status_code == 500
    body_text = response.body.decode()
    error_json = json.loads(body_text)
    assert error_json["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "An unexpected error occurred" in error_json["error"]["message"]
    # Must NOT leak database connection or password details
    assert "password" not in body_text.lower()
    assert "operationalerror" not in body_text.lower()
    assert "postgres" not in body_text.lower()
    assert "traceback" not in body_text.lower()


@pytest.mark.asyncio
async def test_llm_provider_failure_returns_controlled_error(client: AsyncClient, user_token: str):
    """When an LLM provider encounters a timeout or connection failure, API returns controlled 502/AppException."""
    with patch(
        "app.rag.pipeline.RAGPipeline.query",
        side_effect=LLMProviderError("Provider upstream timeout after 60s"),
    ):
        response = await client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"query": "Test query triggering failure"},
        )
        assert response.status_code == 502
        data = response.json()
        assert data["error"]["code"] == "LLM_PROVIDER_ERROR"
        assert "upstream timeout" in data["error"]["message"].lower()
