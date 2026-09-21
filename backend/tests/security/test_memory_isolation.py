"""Memory-Augmented Generation (MAG) & CAG Multi-Tenant Isolation Tests (Invariants S6, S7, S8, S12, S13).

Verifies:
1. Memory isolation between User A ("Project Alpha") and User B ("Project Beta").
2. Memory IDOR defenses across GET, UPDATE, and DELETE.
3. Memory semantic/lexical retrieval enforces WHERE user_id = authenticated_user_id.
4. User A's memory never enters User B's ContextBundle.
5. CAG cache entries enforce user boundaries (private vs global).
6. Malicious mixed ContextBundle ownership sanitization.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.cag.cache import LocalCacheStore
from app.cag.models import CacheEntry
from app.memory.manager import MAGContextProvider, MemoryManager
from app.memory.models import MemoryCreate, MemoryType, MemoryUpdate
from app.memory.store import MemoryStore
from app.orchestration.fusion import DefaultContextFusion
from app.orchestration.models import (
    ConversationContext,
    MemoryContext,
    RAGContext,
)


@pytest.fixture
def user_a_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def user_b_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.mark.asyncio
async def test_memory_crud_isolation_and_idor(
    db_session: AsyncSession, user_a_id: uuid.UUID, user_b_id: uuid.UUID
):
    """User A creating memory_a must prevent User B from reading, updating, or deleting it."""
    store = MemoryStore()

    # 1. User A creates memory A
    mem_a = await store.add_memory(
        session=db_session,
        user_id=user_a_id,
        memory=MemoryCreate(
            content="User A private secret: master password is secret-A-123",
            memory_type=MemoryType.PROJECT_CONTEXT,
            importance=0.9,
        ),
    )
    assert mem_a.id is not None

    # 2. User B attempts IDOR GET on User A's memory
    b_read = await store.get_memory(session=db_session, memory_id=mem_a.id, user_id=user_b_id)
    assert b_read is None, "User B should not be able to read User A's memory"

    # 3. User B attempts IDOR UPDATE on User A's memory
    b_update = await store.update_memory(
        session=db_session,
        memory_id=mem_a.id,
        user_id=user_b_id,
        update=MemoryUpdate(content="Attacker modified content!"),
    )
    assert b_update is None, "User B should not be able to update User A's memory"

    # Verify content was NOT modified
    a_read = await store.get_memory(session=db_session, memory_id=mem_a.id, user_id=user_a_id)
    assert a_read is not None
    assert "secret-A-123" in a_read.content

    # 4. User B attempts IDOR DELETE on User A's memory
    b_deleted = await store.delete_memory(session=db_session, memory_id=mem_a.id, user_id=user_b_id)
    assert b_deleted is False, "User B should not be able to delete User A's memory"

    # Verify memory still exists for User A
    a_read_after = await store.get_memory(session=db_session, memory_id=mem_a.id, user_id=user_a_id)
    assert a_read_after is not None


@pytest.mark.asyncio
async def test_memory_retrieval_isolation_project_alpha_vs_beta(
    db_session: AsyncSession, user_a_id: uuid.UUID, user_b_id: uuid.UUID
):
    """User A building Project Alpha vs User B building Project Beta.

    Querying "What project am I building?" must retrieve ONLY the caller's memory.
    """
    manager = MemoryManager()

    # User A memory
    await manager.add_memory(
        session=db_session,
        user_id=user_a_id,
        memory_in=MemoryCreate(
            content="I am building Project Alpha for aerospace telemetry.",
            memory_type=MemoryType.PROJECT_CONTEXT,
            importance=1.0,
        ),
    )

    # User B memory
    await manager.add_memory(
        session=db_session,
        user_id=user_b_id,
        memory_in=MemoryCreate(
            content="I am building Project Beta for maritime navigation.",
            memory_type=MemoryType.PROJECT_CONTEXT,
            importance=1.0,
        ),
    )

    query = "What project am I building?"

    # User A retrieves
    contexts_a = await manager.retrieve_relevant_contexts(
        session=db_session,
        user_id=user_a_id,
        query=query,
        top_k=5,
    )
    assert len(contexts_a) >= 1
    assert any("Project Alpha" in c.content for c in contexts_a)
    assert not any("Project Beta" in c.content for c in contexts_a)

    # User B retrieves
    contexts_b = await manager.retrieve_relevant_contexts(
        session=db_session,
        user_id=user_b_id,
        query=query,
        top_k=5,
    )
    assert len(contexts_b) >= 1
    assert any("Project Beta" in c.content for c in contexts_b)
    assert not any("Project Alpha" in c.content for c in contexts_b)


@pytest.mark.asyncio
async def test_mag_security_integration_context_bundle(
    db_session: AsyncSession, user_a_id: uuid.UUID, user_b_id: uuid.UUID
):
    """User A memory 'Database host is internal-db-alpha'.

    User B asking 'What database host did the user mention?' must NEVER receive A's memory in ContextBundle.
    """
    mag_provider = MAGContextProvider()

    # User A memory
    await mag_provider.manager.add_memory(
        session=db_session,
        user_id=user_a_id,
        memory_in=MemoryCreate(
            content="Database host is internal-db-alpha.",
            memory_type=MemoryType.INSTRUCTION,
            importance=1.0,
        ),
    )

    # User B retrieves memories via MAGContextProvider
    retrieved_for_b = await mag_provider.retrieve(
        query="What database host did the user mention?",
        user_id=user_b_id,
        session=db_session,
    )

    # User B must receive 0 memories belonging to User A
    assert len(retrieved_for_b) == 0
    assert not any("internal-db-alpha" in m.content for m in retrieved_for_b)


def test_cag_cache_access_rules(user_a_id: uuid.UUID, user_b_id: uuid.UUID):
    """CAG cache entries enforce user isolation: private cache entries cannot be read by other users."""
    cache = LocalCacheStore()

    # 1. Global entry (user_id=None)
    global_entry = CacheEntry(
        cache_id="global_doc_1",
        namespace="docs",
        key="docs:faq",
        content="Global public NexaRAG FAQ information.",
        user_id=None,
    )
    cache.set(global_entry)

    # 2. User A private entry
    user_a_entry = CacheEntry(
        cache_id="private_doc_a",
        namespace="private",
        key="private:user_a_config",
        content="User A internal staging configuration.",
        user_id=user_a_id,
    )
    cache.set(user_a_entry)

    # User A can read global entry
    assert cache.get("docs:faq", user_id=user_a_id) is not None
    # User A can read own private entry
    assert cache.get("private:user_a_config", user_id=user_a_id) is not None

    # User B can read global entry
    assert cache.get("docs:faq", user_id=user_b_id) is not None
    # User B CANNOT read User A private entry (returns None as cache miss)
    assert cache.get("private:user_a_config", user_id=user_b_id) is None

    # Listing entries for User B should NOT include User A private entry
    b_entries = cache.list_entries(user_id=user_b_id)
    b_cache_ids = [e.cache_id for e in b_entries]
    assert "global_doc_1" in b_cache_ids
    assert "private_doc_a" not in b_cache_ids

    # User B cannot delete User A private entry
    assert cache.delete("private:user_a_config", user_id=user_b_id) is False
    # User A can delete own entry
    assert cache.delete("private:user_a_config", user_id=user_a_id) is True


def test_context_bundle_sanitizes_malicious_mixed_ownership(
    user_a_id: uuid.UUID, user_b_id: uuid.UUID
):
    """Construct a malicious mixed bundle:

    RAGContext -> User A
    MemoryContext -> User B (cross-tenant injection attempt)
    Conversation -> User A
    ContextFusion must drop User B's memory when fusing for User A.
    """
    fusion = DefaultContextFusion()

    rag_item = RAGContext(
        content="Project Alpha architecture specification.",
        document_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        filename="alpha_specs.txt",
        chunk_index=0,
        score=0.95,
        metadata={"user_id": str(user_a_id)},
    )

    injected_memory_b = MemoryContext(
        content="User B secret memory: credit card 4111-XXXX-XXXX-1111",
        memory_id=str(uuid.uuid4()),
        memory_type=MemoryType.PROFILE.value,
        relevance_score=0.98,
        metadata={"user_id": str(user_b_id)},  # Belongs to User B!
    )

    conv_item = ConversationContext(
        role="user",
        content="Tell me about the system.",
    )

    # Fuse with current_user_id = user_a_id
    bundle = fusion.fuse(
        query="What is the architecture?",
        rag_context=[rag_item],
        memories=[injected_memory_b],
        conversation_history=[conv_item],
        current_user_id=user_a_id,
    )

    # Verify: RAGContext is retained
    assert len(bundle.rag_context) == 1
    assert "Project Alpha" in bundle.rag_context[0].content

    # Verify: Injected MemoryContext belonging to User B was DROPPED
    assert len(bundle.memories) == 0
    assert not any("credit card" in m.content for m in bundle.memories)

    # Verify: DroppedContext recorded with 'security_user_mismatch'
    dropped = bundle.metadata.dropped_contexts
    security_drops = [d for d in dropped if d.reason == "security_user_mismatch"]
    assert len(security_drops) == 1
    assert security_drops[0].source_id == injected_memory_b.memory_id
