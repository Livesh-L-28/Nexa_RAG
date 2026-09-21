"""API tests for chat querying, session management, and cross-user isolation."""

import uuid

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.database.models import User


@pytest.mark.asyncio
async def test_chat_query_creates_session_and_answers(client: AsyncClient, user_token: str):
    payload = {
        "query": "What are the core features of NexaRAG?",
        "top_k": 3,
    }
    response = await client.post(
        "/api/v1/chat",
        json=payload,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "session_id" in data
    assert "metadata" in data
    assert data["metadata"]["total_latency_ms"] >= 0.0

    session_id = data["session_id"]

    # Retrieve session details
    session_res = await client.get(
        f"/api/v1/chat/sessions/{session_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert session_res.status_code == 200
    detail = session_res.json()
    assert len(detail["messages"]) >= 2  # user message and assistant message


@pytest.mark.asyncio
async def test_cross_user_isolation(client: AsyncClient, user_token: str, db_session):
    # 1. User A creates a session
    payload = {"query": "User A private query"}
    res_a = await client.post(
        "/api/v1/chat",
        json=payload,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    session_id = res_a.json()["session_id"]

    # 2. Create User B
    user_b = User(
        id=uuid.uuid4(),
        email="user_b@nexarag.ai",
        password_hash="hash",
        role="USER",
        is_active=True,
    )
    db_session.add(user_b)
    await db_session.commit()
    token_b = create_access_token(subject=str(user_b.id), role=user_b.role)

    # 3. User B tries to access User A's session
    forbidden_res = await client.get(
        f"/api/v1/chat/sessions/{session_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert forbidden_res.status_code in (403, 404)
