"""Chat Session & Conversation Context Isolation Tests (Invariants S4, S5, S14).

Verifies that chat sessions, message histories, and SSE streaming channels
strictly enforce user ownership and prevent cross-session context injection.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.database.models import User
from app.database.repositories.chat_repo import ChatRepository


@pytest.fixture
async def session_isolation_setup(db_session: AsyncSession):
    """Setup User A and User B with private chat sessions and messages."""
    user_a = User(
        id=uuid.uuid4(),
        email="chat_user_a@nexarag.ai",
        password_hash=hash_password("pwA"),
        role="USER",
        is_active=True,
    )
    user_b = User(
        id=uuid.uuid4(),
        email="chat_user_b@nexarag.ai",
        password_hash=hash_password("pwB"),
        role="USER",
        is_active=True,
    )
    db_session.add_all([user_a, user_b])
    await db_session.flush()

    chat_repo = ChatRepository(db_session)

    # Session A
    session_a = await chat_repo.create_session(user_id=user_a.id, title="User A Confidential Chat")
    await chat_repo.add_message(
        session_id=session_a.id, role="user", content="How do I launch rocket Alpha?"
    )
    await chat_repo.add_message(
        session_id=session_a.id,
        role="assistant",
        content="Rocket Alpha launch code is 98765.",
    )

    # Session B
    session_b = await chat_repo.create_session(user_id=user_b.id, title="User B Public Inquiries")
    await chat_repo.add_message(
        session_id=session_b.id, role="user", content="What is the weather today?"
    )
    await chat_repo.add_message(
        session_id=session_b.id, role="assistant", content="The weather is sunny."
    )

    await db_session.commit()

    token_a = create_access_token(subject=str(user_a.id), role=user_a.role)
    token_b = create_access_token(subject=str(user_b.id), role=user_b.role)

    return {
        "user_a": user_a,
        "token_a": token_a,
        "session_a": session_a,
        "user_b": user_b,
        "token_b": token_b,
        "session_b": session_b,
    }


@pytest.mark.asyncio
async def test_session_listing_strictly_scoped(client: AsyncClient, session_isolation_setup):
    """GET /chat/sessions returns only sessions owned by the authenticated user."""
    data = session_isolation_setup

    # User A listing
    res_a = await client.get(
        "/api/v1/chat/sessions",
        headers={"Authorization": f"Bearer {data['token_a']}"},
    )
    assert res_a.status_code == 200
    sessions_a = res_a.json()
    ids_a = [s["id"] for s in sessions_a]
    assert str(data["session_a"].id) in ids_a
    assert str(data["session_b"].id) not in ids_a

    # User B listing
    res_b = await client.get(
        "/api/v1/chat/sessions",
        headers={"Authorization": f"Bearer {data['token_b']}"},
    )
    assert res_b.status_code == 200
    sessions_b = res_b.json()
    ids_b = [s["id"] for s in sessions_b]
    assert str(data["session_b"].id) in ids_b
    assert str(data["session_a"].id) not in ids_b


@pytest.mark.asyncio
async def test_user_b_cannot_read_messages_of_session_a(
    client: AsyncClient, session_isolation_setup
):
    """User B requesting GET /chat/sessions/{session_a_id} must receive HTTP 403 Forbidden.

    Private messages ('Rocket Alpha launch code is 98765') must not be exposed.
    """
    data = session_isolation_setup

    res = await client.get(
        f"/api/v1/chat/sessions/{data['session_a'].id}",
        headers={"Authorization": f"Bearer {data['token_b']}"},
    )
    assert res.status_code == 403
    assert "98765" not in res.text


@pytest.mark.asyncio
async def test_user_b_cannot_continue_session_a(client: AsyncClient, session_isolation_setup):
    """User B attempting to submit a query to session_a must receive HTTP 403 Forbidden."""
    data = session_isolation_setup

    res = await client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {data['token_b']}"},
        json={
            "query": "Tell me more about the launch code.",
            "session_id": str(data["session_a"].id),
        },
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_user_b_cannot_stream_in_session_a(client: AsyncClient, session_isolation_setup):
    """User B attempting to initiate an SSE stream against session_a must receive HTTP 403 Forbidden."""
    data = session_isolation_setup

    res = await client.post(
        "/api/v1/chat/stream",
        headers={"Authorization": f"Bearer {data['token_b']}"},
        json={
            "query": "Stream me the launch code.",
            "session_id": str(data["session_a"].id),
        },
    )
    assert res.status_code == 403
