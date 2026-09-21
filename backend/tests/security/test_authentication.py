"""Authentication security tests (Invariant S1).

Verifies that unauthenticated, malformed, expired, or invalid JWT requests
are consistently rejected with HTTP 401 across all protected endpoints.
"""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from jose import jwt

from app.core.config import get_settings
from app.core.security import create_access_token
from app.database.models import User

settings = get_settings()


@pytest.mark.asyncio
async def test_valid_jwt_access_me(client: AsyncClient, test_user: User, user_token: str):
    """Valid JWT should successfully grant access to /me endpoint."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_user.id)
    assert data["email"] == test_user.email


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint,method,payload",
    [
        ("/api/v1/auth/me", "GET", None),
        ("/api/v1/documents", "GET", None),
        ("/api/v1/chat/sessions", "GET", None),
        ("/api/v1/chat", "POST", {"query": "Hello NexaRAG"}),
    ],
)
async def test_missing_jwt_rejected(
    client: AsyncClient, endpoint: str, method: str, payload: dict | None
):
    """Protected endpoints must reject requests lacking Authorization header with 401."""
    if method == "GET":
        response = await client.get(endpoint)
    else:
        response = await client.post(endpoint, json=payload)

    assert response.status_code == 401
    error_data = response.json()
    assert error_data["error"]["code"] in ("UNAUTHORIZED", "AUTHENTICATION_FAILED")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "auth_header",
    [
        "Bearer",
        "Bearer ",
        "Bearer not.a.valid.jwt",
        "Bearer gibberish_token_payload",
        "Basic dXNlcjpwYXNz",
        "Token some_random_token",
        "Bearer 1234567890",
    ],
)
async def test_malformed_jwt_rejected(client: AsyncClient, auth_header: str):
    """Malformed tokens or incorrect authorization schemes must return HTTP 401."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": auth_header},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_expired_jwt_rejected(client: AsyncClient, test_user: User):
    """Expired JWT tokens must be rejected with HTTP 401."""
    expired_token = create_access_token(
        subject=str(test_user.id),
        role=test_user.role,
        expires_delta=timedelta(seconds=-60),  # expired 1 minute ago
    )
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert "expired" in response.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_wrong_secret_signature_jwt_rejected(client: AsyncClient, test_user: User):
    """JWT signed with a forged or different secret must be rejected with HTTP 401."""
    forged_token = jwt.encode(
        {"sub": str(test_user.id), "role": test_user.role},
        "entirely_different_untrusted_signing_secret_key",
        algorithm="HS256",
    )
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {forged_token}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_non_existent_user_jwt_rejected(client: AsyncClient):
    """JWT referencing a non-existent user UUID must return HTTP 401."""
    import uuid

    fake_id = str(uuid.uuid4())
    orphan_token = create_access_token(subject=fake_id, role="USER")
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {orphan_token}"},
    )
    assert response.status_code == 401
    assert "not found" in response.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_disabled_user_jwt_rejected(client: AsyncClient, test_user: User, db_session):
    """JWT belonging to a disabled user account (is_active=False) must return HTTP 401."""
    test_user.is_active = False
    await db_session.commit()

    token = create_access_token(subject=str(test_user.id), role=test_user.role)
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert "disabled" in response.json()["error"]["message"].lower()
