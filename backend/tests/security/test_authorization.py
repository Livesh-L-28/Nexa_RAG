"""Authorization & Insecure Direct Object Reference (IDOR) tests (Invariants S2, S3, S4, S5, S9).

Verifies that User A cannot access, read, inspect, reprocess, or delete User B's resources
by substituting resource IDs in API paths or client payloads.
"""

import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.database.models import Document, DocumentChunk, User
from app.database.repositories.chat_repo import ChatRepository


@pytest.fixture
async def user_b(db_session: AsyncSession) -> User:
    """Create a distinct second user (User B)."""
    user = User(
        id=uuid.uuid4(),
        email="user_b@nexarag.ai",
        password_hash=hash_password("password456"),
        role="USER",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def user_b_token(user_b: User) -> str:
    """JWT token for User B."""
    return create_access_token(subject=str(user_b.id), role=user_b.role)


@pytest.fixture
async def doc_b(db_session: AsyncSession, user_b: User) -> Document:
    """Create a document owned by User B with chunks."""
    doc = Document(
        id=uuid.uuid4(),
        user_id=user_b.id,
        filename="secret_project_b.txt",
        file_type="txt",
        file_size=256,
        storage_path="/tmp/secret_project_b.txt",
        status="COMPLETED",
        chunk_count=2,
    )
    db_session.add(doc)
    await db_session.flush()

    chunk1 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        chunk_index=0,
        content="User B confidential architecture details.",
        embedding=[0.1] * 384,
    )
    chunk2 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        chunk_index=1,
        content="User B financial revenue targets for Q4.",
        embedding=[0.2] * 384,
    )
    db_session.add_all([chunk1, chunk2])
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


@pytest.fixture
async def session_b(db_session: AsyncSession, user_b: User):
    """Create a chat session owned by User B with messages."""
    chat_repo = ChatRepository(db_session)
    session = await chat_repo.create_session(
        user_id=user_b.id,
        title="User B Secret Planning Session",
    )
    await chat_repo.add_message(
        session_id=session.id,
        role="user",
        content="What is the internal API key for project B?",
    )
    await chat_repo.add_message(
        session_id=session.id,
        role="assistant",
        content="The internal key is b-secret-key-999.",
    )
    await db_session.commit()
    return session


@pytest.mark.asyncio
async def test_user_a_cannot_get_document_b(client: AsyncClient, user_token: str, doc_b: Document):
    """User A requesting User B's document ID must receive HTTP 403 Forbidden."""
    response = await client.get(
        f"/api/v1/documents/{doc_b.id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403
    assert "permission" in response.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_user_a_cannot_delete_document_b(
    client: AsyncClient, user_token: str, doc_b: Document, db_session: AsyncSession
):
    """User A attempting to delete User B's document must receive HTTP 403 Forbidden."""
    response = await client.delete(
        f"/api/v1/documents/{doc_b.id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403

    # Verify document was NOT deleted
    doc = await db_session.get(Document, doc_b.id)
    assert doc is not None


@pytest.mark.asyncio
async def test_user_a_cannot_reprocess_document_b(
    client: AsyncClient, user_token: str, doc_b: Document
):
    """User A attempting to trigger reprocessing on User B's document must receive HTTP 403."""
    response = await client.post(
        f"/api/v1/documents/{doc_b.id}/process",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_user_a_cannot_access_session_b(client: AsyncClient, user_token: str, session_b):
    """User A requesting User B's chat session detail must receive HTTP 403 Forbidden."""
    response = await client.get(
        f"/api/v1/chat/sessions/{session_b.id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403
    assert (
        "permission" in response.json()["error"]["message"].lower()
        or "access" in response.json()["error"]["message"].lower()
    )


@pytest.mark.asyncio
async def test_user_a_cannot_delete_session_b(client: AsyncClient, user_token: str, session_b):
    """User A attempting to delete User B's chat session must receive HTTP 403 Forbidden."""
    response = await client.delete(
        f"/api/v1/chat/sessions/{session_b.id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_user_a_cannot_read_session_b_logs(client: AsyncClient, user_token: str, session_b):
    """User A attempting to read retrieval/observability logs for Session B must receive HTTP 403."""
    response = await client.get(
        f"/api/v1/chat/sessions/{session_b.id}/logs",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_user_a_cannot_chat_in_session_b(client: AsyncClient, user_token: str, session_b):
    """User A attempting to inject a message into User B's session must receive HTTP 403."""
    response = await client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "query": "What did we talk about earlier?",
            "session_id": str(session_b.id),
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_client_supplied_identity_is_ignored(
    client: AsyncClient, user_token: str, user_b: User
):
    """Client cannot spoof identity by passing a user_id or owner_id in request body or headers."""
    # When uploading a document, server derives user_id strictly from JWT, not client parameters
    files = {"file": ("test_doc.txt", io.BytesIO(b"Document content for User A."), "text/plain")}
    response = await client.post(
        "/api/v1/documents/upload",
        headers={
            "Authorization": f"Bearer {user_token}",
            "X-User-ID": str(user_b.id),  # Spoofed header
        },
        files=files,
    )
    assert response.status_code == 201
    data = response.json()
    # The document must belong to User A, NOT User B
    assert data["user_id"] != str(user_b.id)
