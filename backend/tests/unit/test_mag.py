"""Unit, integration, and security tests for Phase 9: Memory-Augmented Generation (MAG)."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.cag.cache import LocalCacheStore, build_cache_key
from app.cag.manager import CAGContextProvider, CAGManager
from app.database.models import User
from app.memory.extractor import MemoryExtractor
from app.memory.manager import MAGContextProvider, MemoryManager
from app.memory.models import MemoryCreate, MemoryRecord, MemoryType, MemoryUpdate
from app.memory.retriever import MemoryRetriever
from app.memory.store import MemoryStore
from app.orchestration.fusion import DefaultContextFusion
from app.orchestration.models import ContextPriority
from app.rag.pipeline import RAGPipeline
from app.rag.prompt_builder import PromptBuilder
from app.retrieval.vector_search import ScoredChunk

# ============================================================================
# Store Tests
# ============================================================================


@pytest.mark.asyncio
async def test_add_memory(db_session: AsyncSession, test_user: User):
    """Verify persisting a memory to the database."""
    mem_in = MemoryCreate(
        content="User prefers Python for backend development.",
        memory_type=MemoryType.PREFERENCE,
        importance=0.9,
    )
    record = await MemoryStore.add_memory(db_session, test_user.id, mem_in)
    await db_session.commit()

    assert record.id is not None
    assert record.user_id == test_user.id
    assert record.content == "User prefers Python for backend development."
    assert record.importance == 0.9
    assert record.memory_type == "preference"


@pytest.mark.asyncio
async def test_get_memory(db_session: AsyncSession, test_user: User):
    """Verify retrieving a memory by ID enforcing user boundary."""
    mem_in = MemoryCreate(
        content="Project uses FastAPI.",
        memory_type=MemoryType.PROJECT_CONTEXT,
    )
    record = await MemoryStore.add_memory(db_session, test_user.id, mem_in)
    await db_session.commit()

    fetched = await MemoryStore.get_memory(db_session, record.id, test_user.id)
    assert fetched is not None
    assert fetched.id == record.id
    assert fetched.content == "Project uses FastAPI."


@pytest.mark.asyncio
async def test_update_memory(db_session: AsyncSession, test_user: User):
    """Verify updating memory content and importance."""
    mem_in = MemoryCreate(
        content="Initial context note.",
        memory_type=MemoryType.PROJECT_CONTEXT,
        importance=0.5,
    )
    record = await MemoryStore.add_memory(db_session, test_user.id, mem_in)
    await db_session.commit()

    updated = await MemoryStore.update_memory(
        db_session,
        record.id,
        test_user.id,
        MemoryUpdate(content="Updated context note.", importance=0.8),
    )
    await db_session.commit()

    assert updated is not None
    assert updated.content == "Updated context note."
    assert updated.importance == 0.8


@pytest.mark.asyncio
async def test_delete_memory(db_session: AsyncSession, test_user: User):
    """Verify deleting a memory."""
    mem_in = MemoryCreate(
        content="Temporary fact to delete.",
        memory_type=MemoryType.TEMPORARY_CONTEXT,
    )
    record = await MemoryStore.add_memory(db_session, test_user.id, mem_in)
    await db_session.commit()

    deleted = await MemoryStore.delete_memory(db_session, record.id, test_user.id)
    await db_session.commit()
    assert deleted is True

    fetched = await MemoryStore.get_memory(db_session, record.id, test_user.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_list_memories(db_session: AsyncSession, test_user: User):
    """Verify listing memories with type filtering."""
    await MemoryStore.add_memory(
        db_session,
        test_user.id,
        MemoryCreate(content="Pref 1", memory_type=MemoryType.PREFERENCE),
    )
    await MemoryStore.add_memory(
        db_session,
        test_user.id,
        MemoryCreate(content="Proj 1", memory_type=MemoryType.PROJECT_CONTEXT),
    )
    await db_session.commit()

    all_mems = await MemoryStore.list_memories(db_session, test_user.id)
    assert len(all_mems) == 2

    prefs = await MemoryStore.list_memories(
        db_session, test_user.id, memory_type=MemoryType.PREFERENCE.value
    )
    assert len(prefs) == 1
    assert prefs[0].content == "Pref 1"


# ============================================================================
# Isolation & Security Tests
# ============================================================================


@pytest.mark.asyncio
async def test_user_memory_isolation(db_session: AsyncSession, test_user: User, test_admin: User):
    """Security test: User A must never access User B's memories."""
    # test_user adds a memory
    mem_a = await MemoryStore.add_memory(
        db_session,
        test_user.id,
        MemoryCreate(
            content="User A confidential project plan.",
            memory_type=MemoryType.PROJECT_CONTEXT,
        ),
    )
    await db_session.commit()

    # test_admin attempts to get User A's memory
    unauthorized = await MemoryStore.get_memory(db_session, mem_a.id, test_admin.id)
    assert unauthorized is None

    # test_admin attempts to delete User A's memory
    del_result = await MemoryStore.delete_memory(db_session, mem_a.id, test_admin.id)
    assert del_result is False

    # Verify User A's memory is still intact
    intact = await MemoryStore.get_memory(db_session, mem_a.id, test_user.id)
    assert intact is not None


@pytest.mark.asyncio
async def test_user_cannot_access_other_user_memory(
    db_session: AsyncSession, test_user: User, test_admin: User
):
    """Verify list and retrieval isolation between multiple users."""
    await MemoryStore.add_memory(
        db_session,
        test_user.id,
        MemoryCreate(content="User A secret preference", memory_type=MemoryType.PREFERENCE),
    )
    await MemoryStore.add_memory(
        db_session,
        test_admin.id,
        MemoryCreate(content="User B secret preference", memory_type=MemoryType.PREFERENCE),
    )
    await db_session.commit()

    retriever = MemoryRetriever()
    user_a_results = await retriever.retrieve(db_session, test_user.id, "preference")
    user_b_results = await retriever.retrieve(db_session, test_admin.id, "preference")

    assert len(user_a_results) == 1
    assert "User A" in user_a_results[0][0].content
    assert "User B" not in user_a_results[0][0].content

    assert len(user_b_results) == 1
    assert "User B" in user_b_results[0][0].content
    assert "User A" not in user_b_results[0][0].content


def test_sensitive_secret_not_persisted():
    """Security test: Secret credentials must be rejected by the extractor."""
    extractor = MemoryExtractor()

    # API key patterns
    assert extractor.extract("Remember that my api key is sk-1234567890abcdef1234567890") == []
    assert extractor.extract("My GitHub token is ghp_1234567890abcdef12345678901234567890") == []
    assert (
        extractor.extract(
            "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdef"
        )
        == []
    )

    # Password patterns
    assert extractor.extract("Remember password: SuperSecretPassword123") == []
    assert extractor.extract("postgres://admin:secretpassword@localhost:5432/db") == []


# ============================================================================
# Extraction Tests
# ============================================================================


def test_extract_preference():
    """Verify extracting preference from user statements."""
    extractor = MemoryExtractor()
    mems = extractor.extract("I prefer Python over JavaScript for the backend.")
    assert len(mems) == 1
    assert mems[0].memory_type == MemoryType.PREFERENCE
    assert "User prefers Python over JavaScript for the backend" in mems[0].content
    assert mems[0].importance >= 0.8


def test_extract_project_context():
    """Verify extracting project context and tech stack."""
    extractor = MemoryExtractor()
    mems = extractor.extract("I'm building a document intelligence RAG system.")
    assert len(mems) == 1
    assert mems[0].memory_type == MemoryType.PROJECT_CONTEXT
    assert "User is building a document intelligence RAG system" in mems[0].content


def test_extract_instruction():
    """Verify extracting durable formatting instructions."""
    extractor = MemoryExtractor()
    mems = extractor.extract("Always respond in bullet points with concise explanations.")
    assert len(mems) == 1
    assert mems[0].memory_type == MemoryType.INSTRUCTION
    assert mems[0].importance >= 0.9


def test_ignore_irrelevant_message():
    """Verify trivial chit-chat is not extracted into memory."""
    extractor = MemoryExtractor()
    assert extractor.extract("ok") == []
    assert extractor.extract("thanks") == []
    assert extractor.extract("hello there") == []
    assert extractor.extract("sure, got it") == []


def test_explicit_remember_instruction():
    """Verify 'Remember that...' generates a high-importance memory."""
    extractor = MemoryExtractor()
    mems = extractor.extract(
        "Remember that our production deployment uses Kubernetes on port 8080."
    )
    assert len(mems) == 1
    assert mems[0].importance == 0.95
    assert "Kubernetes on port 8080" in mems[0].content


# ============================================================================
# Retrieval & Ranking Tests
# ============================================================================


@pytest.mark.asyncio
async def test_memory_relevance(db_session: AsyncSession, test_user: User):
    """Verify retrieval returns relevant memories based on query terms."""
    await MemoryStore.add_memory(
        db_session,
        test_user.id,
        MemoryCreate(
            content="User prefers Python for data processing.", memory_type=MemoryType.PREFERENCE
        ),
    )
    await MemoryStore.add_memory(
        db_session,
        test_user.id,
        MemoryCreate(content="User likes Italian food.", memory_type=MemoryType.PREFERENCE),
    )
    await db_session.commit()

    retriever = MemoryRetriever()
    results = await retriever.retrieve(
        db_session, test_user.id, "Which programming language for data?"
    )
    assert len(results) == 1
    assert "Python" in results[0][0].content


@pytest.mark.asyncio
async def test_memory_top_k(db_session: AsyncSession, test_user: User):
    """Verify top-k limit is respected."""
    for i in range(10):
        await MemoryStore.add_memory(
            db_session,
            test_user.id,
            MemoryCreate(
                content=f"User project fact #{i} with python",
                memory_type=MemoryType.PROJECT_CONTEXT,
            ),
        )
    await db_session.commit()

    retriever = MemoryRetriever()
    results = await retriever.retrieve(db_session, test_user.id, "python project facts", top_k=3)
    assert len(results) == 3


@pytest.mark.asyncio
async def test_expired_memory_excluded(db_session: AsyncSession, test_user: User):
    """Verify expired temporary memories are not retrieved."""
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    future = datetime.now(timezone.utc) + timedelta(hours=2)

    await MemoryStore.add_memory(
        db_session,
        test_user.id,
        MemoryCreate(
            content="Expired debugging note on auth",
            memory_type=MemoryType.TEMPORARY_CONTEXT,
            expires_at=past,
        ),
    )
    await MemoryStore.add_memory(
        db_session,
        test_user.id,
        MemoryCreate(
            content="Active debugging note on auth",
            memory_type=MemoryType.TEMPORARY_CONTEXT,
            expires_at=future,
        ),
    )
    await db_session.commit()

    retriever = MemoryRetriever()
    results = await retriever.retrieve(db_session, test_user.id, "debugging auth")
    assert len(results) == 1
    assert "Active" in results[0][0].content


@pytest.mark.asyncio
async def test_importance_affects_ranking(db_session: AsyncSession, test_user: User):
    """Verify that higher importance boosts memory rank for similar relevance."""
    await MemoryStore.add_memory(
        db_session,
        test_user.id,
        MemoryCreate(
            content="FastAPI is used", memory_type=MemoryType.PROJECT_CONTEXT, importance=0.5
        ),
    )
    await MemoryStore.add_memory(
        db_session,
        test_user.id,
        MemoryCreate(
            content="FastAPI is critical core framework",
            memory_type=MemoryType.PROJECT_CONTEXT,
            importance=0.95,
        ),
    )
    await db_session.commit()

    retriever = MemoryRetriever()
    results = await retriever.retrieve(db_session, test_user.id, "FastAPI")
    assert len(results) == 2
    assert results[0][0].importance == 0.95


@pytest.mark.asyncio
async def test_recency_affects_ranking(db_session: AsyncSession, test_user: User):
    """Verify recency score calculation decays over time."""
    now = datetime.now(timezone.utc)
    recent_time = now - timedelta(hours=1)
    old_time = now - timedelta(days=20)

    recent_score = MemoryRetriever.compute_recency(recent_time, now)
    old_score = MemoryRetriever.compute_recency(old_time, now)

    assert recent_score > old_score
    assert recent_score <= 1.0
    assert old_score >= 0.1


# ============================================================================
# Manager & Conflict Resolution Tests
# ============================================================================


@pytest.mark.asyncio
async def test_memory_manager_create(db_session: AsyncSession, test_user: User):
    """Verify MemoryManager extracts and saves memories from conversation text."""
    manager = MemoryManager()
    saved = await manager.save_from_text(
        db_session,
        test_user.id,
        "Remember that we are building a FastAPI backend with PostgreSQL.",
    )
    await db_session.commit()

    assert len(saved) >= 1
    assert "FastAPI" in saved[0].content


@pytest.mark.asyncio
async def test_memory_conflict_resolution(db_session: AsyncSession, test_user: User):
    """Verify that contradictory newer preferences update existing records."""
    manager = MemoryManager()

    # First preference
    await manager.add_memory(
        db_session,
        test_user.id,
        MemoryCreate(
            content="User prefers Java for enterprise services.", memory_type=MemoryType.PREFERENCE
        ),
    )
    await db_session.commit()

    # Newer contradictory preference
    await manager.add_memory(
        db_session,
        test_user.id,
        MemoryCreate(
            content="User prefers Python for enterprise services.",
            memory_type=MemoryType.PREFERENCE,
        ),
    )
    await db_session.commit()

    # Should update existing record rather than keeping both contradictory preferences
    mems = await manager.list_memories(
        db_session, test_user.id, memory_type=MemoryType.PREFERENCE.value
    )
    assert len(mems) == 1
    assert "Python" in mems[0].content


@pytest.mark.asyncio
async def test_memory_manager_retrieve(db_session: AsyncSession, test_user: User):
    """Verify MemoryManager retrieves relevant Context instances enforcing ownership."""
    manager = MemoryManager()
    await manager.add_memory(
        db_session,
        test_user.id,
        MemoryCreate(
            content="User prefers PostgreSQL over MongoDB.",
            memory_type=MemoryType.PREFERENCE,
            importance=0.9,
        ),
    )
    await db_session.commit()

    contexts = await manager.retrieve_relevant_contexts(
        db_session, test_user.id, "What database does user prefer?", top_k=5
    )
    assert len(contexts) >= 1
    assert "PostgreSQL" in contexts[0].content


@pytest.mark.asyncio
async def test_memory_manager_delete(db_session: AsyncSession, test_user: User, test_admin: User):
    """Verify MemoryManager deletes memory while enforcing tenant isolation."""
    manager = MemoryManager()
    record = await manager.add_memory(
        db_session,
        test_user.id,
        MemoryCreate(
            content="User temporary fact to delete.",
            memory_type=MemoryType.TEMPORARY_CONTEXT,
        ),
    )
    await db_session.commit()

    # Another user cannot delete
    denied = await manager.delete_memory(db_session, record.id, test_admin.id)
    assert denied is False

    # Owner can delete
    deleted = await manager.delete_memory(db_session, record.id, test_user.id)
    assert deleted is True

    # Confirm deletion
    fetched = await manager.get_memory(db_session, record.id, test_user.id)
    assert fetched is None


# ============================================================================
# Orchestration Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_memory_context_generation(db_session: AsyncSession, test_user: User):
    """Verify converting stored memory into unified MemoryContext."""
    manager = MemoryManager()
    await manager.add_memory(
        db_session,
        test_user.id,
        MemoryCreate(
            content="User prefers concise answers.",
            memory_type=MemoryType.INSTRUCTION,
            importance=0.9,
        ),
    )
    await db_session.commit()

    contexts = await manager.retrieve_relevant_contexts(db_session, test_user.id, "concise answers")
    assert len(contexts) == 1
    ctx = contexts[0]
    assert ctx.content == "User prefers concise answers."
    assert ctx.memory_type == "instruction"
    assert ctx.importance == 0.9
    assert ctx.priority == ContextPriority.MAG
    assert ctx.metadata["user_id"] == str(test_user.id)


def test_mag_context_bundle_integration():
    """Verify ContextBundle formats relevant user memories into prompt under priority."""
    fusion = DefaultContextFusion()

    record = MemoryRecord(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        memory_type=MemoryType.PREFERENCE.value,
        content="User prefers Python over TypeScript.",
        importance=0.85,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mem_ctx = record.to_memory_context(relevance_score=0.92)

    bundle = fusion.fuse(
        query="What language should I use?",
        memories=[mem_ctx],
    )

    assert bundle.metadata.mag_selected is True
    assert "mag" in bundle.selected_sources

    prompt = PromptBuilder.build_user_prompt_from_bundle(bundle)
    assert "RELEVANT USER MEMORY CONTEXT:" in prompt
    assert "[User Memory 1] (Type: preference)" in prompt
    assert "User prefers Python over TypeScript." in prompt


@pytest.mark.asyncio
async def test_rag_cag_mag_context_fusion(db_session: AsyncSession, test_user: User):
    """Verify end-to-end fusion of RAG + CAG + MAG into ContextBundle and LLM prompt."""
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value="Answer grounded with RAG, CAG, and MAG.")

    mock_embed = MagicMock()
    mock_embed.embed_query.return_value = [0.1] * 384

    # Setup CAG
    cag_manager = CAGManager(store=LocalCacheStore())
    cag_key = build_cache_key("policy", "security")
    cag_manager.set_context("policy", "security", "Mandatory TLS 1.3 encryption.")
    cag_manager.policy.register_domain("security", cag_key)
    cag_provider = CAGContextProvider(manager=cag_manager)

    # Setup MAG
    mag_manager = MemoryManager()
    await mag_manager.add_memory(
        db_session,
        test_user.id,
        MemoryCreate(
            content="User prefers bullet points.",
            memory_type=MemoryType.INSTRUCTION,
            importance=0.9,
        ),
    )
    await db_session.commit()
    mag_provider = MAGContextProvider(manager=mag_manager)

    pipeline = RAGPipeline(
        llm=mock_llm,
        embedding_service=mock_embed,
        cag_provider=cag_provider,
        cag_enabled=True,
        mag_provider=mag_provider,
        mag_enabled=True,
    )
    pipeline._retrieve_and_rerank = AsyncMock(
        return_value=(
            [
                ScoredChunk(
                    chunk_id=uuid.uuid4(),
                    document_id=uuid.uuid4(),
                    filename="architecture.pdf",
                    chunk_index=0,
                    content="System uses microservices with HTTPS.",
                    page_number=1,
                    metadata={},
                    score=0.91,
                )
            ],
            10.0,
            5.0,
            1,
        )
    )

    res = await pipeline.query(
        session=db_session,
        query="What are the security standards?",
        user_id=test_user.id,
        session_id=uuid.uuid4(),
    )

    assert res.answer == "Answer grounded with RAG, CAG, and MAG."
    assert res.metadata.cag_selected is True
    assert res.metadata.mag_selected is True
    assert res.metadata.memories_retrieved >= 1
    assert "instruction" in res.metadata.memory_types
