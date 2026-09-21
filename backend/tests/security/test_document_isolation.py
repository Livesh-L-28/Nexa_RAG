"""Document & Chunk multi-tenant isolation tests (Invariants S2, S3, S10).

Verifies that all document queries filter by authenticated user_id at the database level,
and deleted resources are immediately unreachable.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.database.models import Document, DocumentChunk, User
from app.database.repositories.document_repo import DocumentRepository


@pytest.fixture
async def two_users_with_documents(db_session: AsyncSession):
    """Create User A and User B each with private documents and chunks."""
    user_a = User(
        id=uuid.uuid4(),
        email="tenant_a@nexarag.ai",
        password_hash=hash_password("passwordA123"),
        role="USER",
        is_active=True,
    )
    user_b = User(
        id=uuid.uuid4(),
        email="tenant_b@nexarag.ai",
        password_hash=hash_password("passwordB123"),
        role="USER",
        is_active=True,
    )
    db_session.add_all([user_a, user_b])
    await db_session.flush()

    doc_a = Document(
        id=uuid.uuid4(),
        user_id=user_a.id,
        filename="project_alpha_specs.txt",
        file_type="txt",
        file_size=512,
        storage_path="/tmp/project_alpha_specs.txt",
        status="COMPLETED",
        chunk_count=2,
    )
    doc_b = Document(
        id=uuid.uuid4(),
        user_id=user_b.id,
        filename="project_beta_specs.txt",
        file_type="txt",
        file_size=512,
        storage_path="/tmp/project_beta_specs.txt",
        status="COMPLETED",
        chunk_count=2,
    )
    db_session.add_all([doc_a, doc_b])
    await db_session.flush()

    chunks_a = [
        DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc_a.id,
            chunk_index=0,
            content="Project Alpha: confidential nuclear power propulsion blueprint.",
            embedding=[0.5] * 384,
        ),
        DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc_a.id,
            chunk_index=1,
            content="Project Alpha: contact lead engineer at alpha@internal.",
            embedding=[0.6] * 384,
        ),
    ]

    chunks_b = [
        DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc_b.id,
            chunk_index=0,
            content="Project Beta: confidential quantum encryption algorithms.",
            embedding=[0.1] * 384,
        ),
        DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc_b.id,
            chunk_index=1,
            content="Project Beta: key material stored in vault beta-01.",
            embedding=[0.2] * 384,
        ),
    ]
    db_session.add_all(chunks_a + chunks_b)
    await db_session.commit()

    token_a = create_access_token(subject=str(user_a.id), role=user_a.role)
    token_b = create_access_token(subject=str(user_b.id), role=user_b.role)

    return {
        "user_a": user_a,
        "token_a": token_a,
        "doc_a": doc_a,
        "chunks_a": chunks_a,
        "user_b": user_b,
        "token_b": token_b,
        "doc_b": doc_b,
        "chunks_b": chunks_b,
    }


@pytest.mark.asyncio
async def test_document_listing_isolation(client: AsyncClient, two_users_with_documents):
    """GET /documents must only return documents belonging to the authenticated caller."""
    data = two_users_with_documents

    # User A listing
    res_a = await client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {data['token_a']}"},
    )
    assert res_a.status_code == 200
    items_a = res_a.json()["items"]
    ids_a = [d["id"] for d in items_a]
    assert str(data["doc_a"].id) in ids_a
    assert str(data["doc_b"].id) not in ids_a

    # User B listing
    res_b = await client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {data['token_b']}"},
    )
    assert res_b.status_code == 200
    items_b = res_b.json()["items"]
    ids_b = [d["id"] for d in items_b]
    assert str(data["doc_b"].id) in ids_b
    assert str(data["doc_a"].id) not in ids_b


@pytest.mark.asyncio
async def test_chunk_inspection_isolation(client: AsyncClient, two_users_with_documents):
    """User B cannot inspect chunk content of User A's document via detail endpoint."""
    data = two_users_with_documents

    # User B attempts to access User A document detail (which embeds chunks)
    res = await client.get(
        f"/api/v1/documents/{data['doc_a'].id}",
        headers={"Authorization": f"Bearer {data['token_b']}"},
    )
    assert res.status_code == 403
    # No chunk content leaked
    assert "nuclear" not in res.text


@pytest.mark.asyncio
async def test_repository_level_document_scoping(
    db_session: AsyncSession, two_users_with_documents
):
    """DocumentRepository queries must strictly isolate documents by user_id."""
    data = two_users_with_documents
    doc_repo = DocumentRepository(db_session)

    # list_by_user for User A
    docs_a = await doc_repo.list_by_user(user_id=data["user_a"].id)
    assert len(docs_a) == 1
    assert docs_a[0].id == data["doc_a"].id

    # list_by_user for User B
    docs_b = await doc_repo.list_by_user(user_id=data["user_b"].id)
    assert len(docs_b) == 1
    assert docs_b[0].id == data["doc_b"].id


@pytest.mark.asyncio
async def test_deleted_document_unreachable(
    client: AsyncClient, two_users_with_documents, db_session: AsyncSession
):
    """Once deleted, a document and its chunks must be completely unreachable (Invariant S10)."""
    data = two_users_with_documents
    doc_a_id = data["doc_a"].id

    # Delete Document A as User A
    del_res = await client.delete(
        f"/api/v1/documents/{doc_a_id}",
        headers={"Authorization": f"Bearer {data['token_a']}"},
    )
    assert del_res.status_code == 200

    # User A subsequent GET must return 404
    get_res = await client.get(
        f"/api/v1/documents/{doc_a_id}",
        headers={"Authorization": f"Bearer {data['token_a']}"},
    )
    assert get_res.status_code == 404

    # Direct database check: document and chunks should no longer exist
    from sqlalchemy import select

    db_check = await db_session.execute(select(Document).where(Document.id == doc_a_id))
    assert db_check.scalar_one_or_none() is None

    chunks = await DocumentRepository(db_session).get_chunks_by_document(doc_a_id)
    assert len(chunks) == 0
