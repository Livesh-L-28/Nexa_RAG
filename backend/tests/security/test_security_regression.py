"""End-to-End Multi-Tenant Lifecycle Security Regression Test (Step 35).

Executes a complete real-world scenario:
1. User A registers.
2. User A uploads a private confidential document.
3. User A creates a private long-term memory.
4. User A creates a chat session and asks a question, receiving a grounded answer.
5. User B registers.
6. User B attempts to access User A's document -> FAILS (403).
7. User B attempts vector retrieval for User A's secrets -> FAILS (0 results).
8. User B attempts BM25 retrieval for User A's keywords -> FAILS (0 results).
9. User B attempts memory retrieval for User A's memory -> FAILS (0 results).
10. User B attempts to access or continue User A's session -> FAILS (403).
"""

import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.manager import MAGContextProvider, MemoryManager
from app.memory.models import MemoryCreate, MemoryType
from app.retrieval.bm25_search import BM25Search
from app.retrieval.vector_search import VectorSearch


@pytest.mark.asyncio
async def test_end_to_end_multi_tenant_isolation_scenario(
    client: AsyncClient, db_session: AsyncSession
):
    # -------------------------------------------------------------
    # PHASE A: User A Lifecycle
    # -------------------------------------------------------------

    # 1. User A registers
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={"email": "alpha_owner@enterprise.ai", "password": "SecurePasswordA123!"},
    )
    assert reg_a.status_code == 201
    user_a_id = uuid.UUID(reg_a.json()["id"])

    login_a = await client.post(
        "/api/v1/auth/login",
        json={"email": "alpha_owner@enterprise.ai", "password": "SecurePasswordA123!"},
    )
    assert login_a.status_code == 200
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 2. User A uploads private confidential document
    doc_content = (
        b"PROJECT TITAN CONFIDENTIAL SPECIFICATION:\n"
        b"The primary reactor core frequency is strictly 432.85 MHz.\n"
        b"Authorized launch commander is Admiral Vance.\n"
    )
    files = {"file": ("titan_specs.txt", io.BytesIO(doc_content), "text/plain")}
    upload_res = await client.post("/api/v1/documents/upload", headers=headers_a, files=files)
    assert upload_res.status_code == 201
    doc_a_id = upload_res.json()["id"]

    # 3. User A creates private memory
    memory_manager = MemoryManager()
    await memory_manager.add_memory(
        session=db_session,
        user_id=user_a_id,
        memory_in=MemoryCreate(
            content="User preference: Always format physics calculations with 3 decimals.",
            memory_type=MemoryType.PREFERENCE,
            importance=1.0,
        ),
    )
    await db_session.commit()

    # 4. User A chats and asks a question
    chat_res = await client.post(
        "/api/v1/chat",
        headers=headers_a,
        json={"query": "What is the reactor core frequency for Project Titan?"},
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert "session_id" in chat_data
    session_a_id = chat_data["session_id"]
    # User A receives citations to their document
    assert len(chat_data["sources"]) >= 1
    assert any("titan_specs" in s["filename"] for s in chat_data["sources"])

    # -------------------------------------------------------------
    # PHASE B: User B Unauthorized Access Attempts
    # -------------------------------------------------------------

    # 5. User B registers
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={"email": "beta_intruder@enterprise.ai", "password": "SecurePasswordB456!"},
    )
    assert reg_b.status_code == 201
    user_b_id = uuid.UUID(reg_b.json()["id"])

    login_b = await client.post(
        "/api/v1/auth/login",
        json={"email": "beta_intruder@enterprise.ai", "password": "SecurePasswordB456!"},
    )
    assert login_b.status_code == 200
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 6. User B attempts direct document access on User A's document -> MUST FAIL (403)
    doc_attempt = await client.get(f"/api/v1/documents/{doc_a_id}", headers=headers_b)
    assert doc_attempt.status_code == 403

    # User B attempts to delete User A's document -> MUST FAIL (403)
    del_attempt = await client.delete(f"/api/v1/documents/{doc_a_id}", headers=headers_b)
    assert del_attempt.status_code == 403

    # 7. User B attempts Vector Retrieval for User A's document chunks -> MUST YIELD 0
    vec_search = VectorSearch(db_session)
    vector_results = await vec_search.search(
        query_vector=[0.1] * 384,
        user_id=user_b_id,
        top_k=10,
    )
    assert len(vector_results) == 0

    # 8. User B attempts BM25 keyword search for "PROJECT TITAN reactor frequency" -> MUST YIELD 0
    bm25_search = BM25Search(db_session)
    bm25_results = await bm25_search.search(
        query="PROJECT TITAN reactor core frequency Admiral Vance",
        user_id=user_b_id,
        top_k=10,
    )
    assert len(bm25_results) == 0

    # 9. User B attempts Memory Retrieval for User A's memories -> MUST YIELD 0
    mag_provider = MAGContextProvider(memory_manager)
    b_memories = await mag_provider.retrieve(
        query="What format should calculations use?",
        user_id=user_b_id,
        session=db_session,
    )
    assert len(b_memories) == 0
    assert not any("decimals" in m.content for m in b_memories)

    # 10. User B attempts to read User A's session -> MUST FAIL (403)
    session_read = await client.get(f"/api/v1/chat/sessions/{session_a_id}", headers=headers_b)
    assert session_read.status_code == 403

    # User B attempts to continue/chat in User A's session -> MUST FAIL (403)
    session_chat = await client.post(
        "/api/v1/chat",
        headers=headers_b,
        json={
            "query": "Tell me the reactor frequency again.",
            "session_id": session_a_id,
        },
    )
    assert session_chat.status_code == 403

    # 11. User B performs normal chat asking about Project Titan -> receives NO sources or leaked context
    b_chat = await client.post(
        "/api/v1/chat",
        headers=headers_b,
        json={"query": "What is the reactor core frequency for Project Titan?"},
    )
    assert b_chat.status_code == 200
    b_chat_data = b_chat.json()
    # 0 sources cited for User B
    assert len(b_chat_data["sources"]) == 0
    assert len(b_chat_data["retrieved_chunks"]) == 0
    # Answer cannot reveal 432.85 MHz
    assert "432.85" not in b_chat_data["answer"]
