"""Unit and integration tests for Phase 8: Cache-Augmented Generation (CAG)."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cag.cache import LocalCacheStore, build_cache_key
from app.cag.manager import CAGContextProvider, CAGManager
from app.cag.models import CacheEntry
from app.cag.policy import CachePolicy
from app.orchestration.fusion import DefaultContextFusion
from app.orchestration.models import RAGContext
from app.rag.pipeline import RAGPipeline
from app.rag.prompt_builder import PromptBuilder
from app.retrieval.vector_search import ScoredChunk


def test_cache_set():
    """Verify storing an entry in the cache store."""
    store = LocalCacheStore()
    entry = CacheEntry(
        cache_id="cag_policy_security",
        namespace="policy",
        key="policy:security",
        content="All data must be encrypted at rest.",
        version=1,
    )
    store.set(entry)
    stats = store.stats()
    assert stats.entries == 1
    assert stats.total_size_bytes > 0


def test_cache_get():
    """Verify retrieving a stored entry."""
    store = LocalCacheStore()
    entry = CacheEntry(
        cache_id="cag_policy_security",
        namespace="policy",
        key="policy:security",
        content="All data must be encrypted at rest.",
        version=1,
    )
    store.set(entry)
    retrieved = store.get("policy:security")
    assert retrieved is not None
    assert retrieved.content == "All data must be encrypted at rest."
    assert store.stats().hits == 1


def test_cache_miss():
    """Verify cache miss behavior when key does not exist."""
    store = LocalCacheStore()
    result = store.get("nonexistent:key")
    assert result is None
    assert store.stats().misses == 1


def test_cache_invalidate():
    """Verify explicit invalidation of cache entries."""
    store = LocalCacheStore()
    entry = CacheEntry(
        cache_id="cag_arch_v1",
        namespace="arch",
        key="arch:system",
        content="System architecture overview.",
        version=1,
    )
    store.set(entry)
    assert store.get("arch:system") is not None

    deleted = store.delete("arch:system")
    assert deleted is True
    assert store.get("arch:system") is None


def test_cache_refresh():
    """Verify refreshing cache entry increments version and updates content."""
    manager = CAGManager(store=LocalCacheStore())
    manager.set_context(
        namespace="policy",
        identifier="auth",
        content="JWT tokens expire in 1 hour.",
        version=1,
    )

    key = build_cache_key("policy", "auth")
    ctx1 = manager.get_context(key)
    assert ctx1 is not None
    assert ctx1.version == "1"
    assert "1 hour" in ctx1.content

    updated = manager.refresh_context(key, "JWT tokens expire in 15 minutes.")
    assert updated is not None
    assert updated.version == 2

    ctx2 = manager.get_context(key)
    assert ctx2 is not None
    assert ctx2.version == "2"
    assert "15 minutes" in ctx2.content


def test_cache_version():
    """Verify cache versions are tracked and updated."""
    manager = CAGManager(store=LocalCacheStore())
    manager.set_context("compliance", "gdpr", "GDPR compliance rules v1", version=1)
    key = build_cache_key("compliance", "gdpr")

    entry1 = manager.get_context(key)
    assert entry1 is not None
    assert entry1.version == "1"

    manager.refresh_context(key, "GDPR compliance rules v2")
    entry2 = manager.get_context(key)
    assert entry2 is not None
    assert entry2.version == "2"

    stats = manager.get_cache_stats()
    assert stats.versions[entry2.cache_id] == 2


def test_cache_stats():
    """Verify cache statistics tracking hits, misses, entries, and size."""
    store = LocalCacheStore()
    store.set(
        CacheEntry(
            cache_id="c1",
            namespace="ns",
            key="k1",
            content="Sample text",
        )
    )
    store.get("k1")  # Hit
    store.get("k2")  # Miss

    stats = store.stats()
    assert stats.hits == 1
    assert stats.misses == 1
    assert stats.entries == 1
    assert stats.total_size_bytes == len("Sample text".encode("utf-8"))


def test_cache_policy():
    """Verify deterministic CachePolicy eligibility and key resolution."""
    policy = CachePolicy()
    assert policy.is_cag_eligible("What is our security policy?") is True
    assert policy.is_cag_eligible("Explain the system architecture.") is True
    assert policy.is_cag_eligible("Calculate 2 + 2") is False

    # Domain registration
    policy.register_domain("database schema", "docs:schema")
    assert policy.is_cag_eligible("Show me the database schema") is True
    assert policy.resolve_cache_keys("Show me the database schema") == ["docs:schema"]

    # Unregister domain
    policy.unregister_domain("database schema")
    assert policy.resolve_cache_keys("Show me the database schema") == []


@pytest.mark.asyncio
async def test_cag_context_provider():
    """Verify CAGContextProvider retrieves CachedContext objects for eligible queries."""
    manager = CAGManager(store=LocalCacheStore(), policy=CachePolicy())
    policy = manager.policy

    # Set up cached context
    manager.set_context("policy", "encryption", "Encryption at rest is mandatory.")
    key = build_cache_key("policy", "encryption")
    policy.register_domain("encryption", key)

    provider = CAGContextProvider(manager=manager, policy=policy)
    assert provider.source_name == "cag"

    # Eligible query
    results = await provider.retrieve("What is the policy for encryption?")
    assert len(results) == 1
    assert "Encryption at rest is mandatory." in results[0].content
    assert results[0].cache_id == f"cag_{key.replace(':', '_')}"

    # Ineligible query
    empty_results = await provider.retrieve("Tell me a fictional joke.")
    assert len(empty_results) == 0


def test_cag_context_bundle_integration():
    """Verify ContextBundle seamlessly holds both RAG and CAG contexts and formats them."""
    fusion = DefaultContextFusion()

    rag_item = RAGContext(
        content="Document excerpt from company docs.",
        document_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        filename="company_docs.pdf",
    )
    cached_manager = CAGManager(store=LocalCacheStore())
    cached_entry = cached_manager.set_context(
        "policy",
        "retention",
        "Data retention policy: 7 years.",
    )
    cached_item = cached_entry.to_cached_context()

    bundle = fusion.fuse(
        query="What is the data retention policy?",
        rag_context=[rag_item],
        cached_context=[cached_item],
    )

    assert bundle.metadata.rag_selected is True
    assert bundle.metadata.cag_selected is True
    assert "rag" in bundle.selected_sources
    assert "cag" in bundle.selected_sources
    assert bundle.metadata.context_count == 2

    # Verify prompt builder incorporates both RAG and CAG
    prompt = PromptBuilder.build_user_prompt_from_bundle(bundle)
    assert "DOCUMENT CONTEXT:" in prompt
    assert "CACHED KNOWLEDGE CONTEXT:" in prompt
    assert "Data retention policy: 7 years." in prompt
    assert "USER QUESTION: What is the data retention policy?" in prompt


def test_cache_context_size_limit():
    """Verify CAGManager truncates content exceeding max_context_chars."""
    manager = CAGManager(store=LocalCacheStore(), max_context_chars=50)
    long_content = "A" * 150
    manager.set_context("ns", "long", long_content)

    key = build_cache_key("ns", "long")
    ctx = manager.get_context(key)
    assert ctx is not None
    assert len(ctx.content) < 150
    assert "[Truncated by CAG size limit]" in ctx.content


def test_user_cache_isolation():
    """Security test: User A must never access User B's cache entry."""
    store = LocalCacheStore()
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    key_a = build_cache_key("user_notes", "project_x", user_id=user_a)
    entry_a = CacheEntry(
        cache_id="cag_user_a",
        namespace="user_notes",
        key=key_a,
        content="User A confidential design note.",
        user_id=user_a,
    )
    store.set(entry_a)

    # User A accesses own entry
    assert store.get(key_a, user_id=user_a) is not None

    # User B attempts to access User A's entry
    user_b_result = store.get(key_a, user_id=user_b)
    assert user_b_result is None

    # User B cannot delete User A's entry
    deleted = store.delete(key_a, user_id=user_b)
    assert deleted is False
    assert store.get(key_a, user_id=user_a) is not None

    # User B cannot list User A's entry
    user_b_entries = store.list_entries(user_id=user_b)
    assert len(user_b_entries) == 0


def test_cag_disabled():
    """Verify that when CAG is disabled, policy rejects queries and provider returns empty."""
    policy = CachePolicy(enabled=False)
    assert policy.is_cag_eligible("What is our architecture policy?") is False
    assert policy.resolve_cache_keys("architecture policy") == []

    manager = CAGManager(store=LocalCacheStore(), policy=policy)
    provider = CAGContextProvider(manager=manager, policy=policy)

    import asyncio

    res = asyncio.run(provider.retrieve("architecture policy"))
    assert res == []


@pytest.mark.asyncio
async def test_rag_without_cag():
    """Verify RAGPipeline operates completely and cleanly when CAG has no hits."""
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value="RAG answer without CAG.")

    mock_embed = MagicMock()
    mock_embed.embed_query.return_value = [0.1] * 384

    pipeline = RAGPipeline(
        llm=mock_llm,
        embedding_service=mock_embed,
        cag_enabled=False,
        mag_enabled=False,
    )
    pipeline._retrieve_and_rerank = AsyncMock(
        return_value=(
            [
                ScoredChunk(
                    chunk_id=uuid.uuid4(),
                    document_id=uuid.uuid4(),
                    filename="doc.pdf",
                    chunk_index=0,
                    content="Doc text",
                    page_number=1,
                    metadata={},
                    score=0.9,
                )
            ],
            10.0,
            5.0,
            1,
        )
    )

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    res = await pipeline.query(
        session=mock_session,
        query="What is in the doc?",
        user_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
    )

    assert res.answer == "RAG answer without CAG."
    assert res.metadata.cag_enabled is False
    assert res.metadata.cag_selected is False
    assert res.metadata.cache_hit is False


@pytest.mark.asyncio
async def test_rag_with_cag():
    """Verify RAGPipeline enriches ContextBundle when CAG hits matching domain knowledge."""
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value="Answer grounded with RAG and CAG.")

    mock_embed = MagicMock()
    mock_embed.embed_query.return_value = [0.1] * 384

    cag_manager = CAGManager(store=LocalCacheStore())
    key = build_cache_key("policy", "security")
    cag_manager.set_context("policy", "security", "Mandatory TLS 1.3 encryption.")
    cag_manager.policy.register_domain("security", key)
    cag_provider = CAGContextProvider(manager=cag_manager)

    pipeline = RAGPipeline(
        llm=mock_llm,
        embedding_service=mock_embed,
        cag_provider=cag_provider,
        cag_enabled=True,
        mag_enabled=False,
    )
    pipeline._retrieve_and_rerank = AsyncMock(
        return_value=(
            [
                ScoredChunk(
                    chunk_id=uuid.uuid4(),
                    document_id=uuid.uuid4(),
                    filename="handbook.pdf",
                    chunk_index=0,
                    content="Handbook security guidelines.",
                    page_number=2,
                    metadata={},
                    score=0.88,
                )
            ],
            12.0,
            6.0,
            1,
        )
    )

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    res = await pipeline.query(
        session=mock_session,
        query="What are the security standards?",
        user_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
    )

    assert res.answer == "Answer grounded with RAG and CAG."
    assert res.metadata.cag_enabled is True
    assert res.metadata.cag_selected is True
    assert res.metadata.cache_hit is True
    assert res.metadata.cache_context_count == 1
    assert res.metadata.cache_context_size > 0


def test_empty_cache():
    """Verify operations on an empty cache store."""
    store = LocalCacheStore()
    assert store.get("any_key") is None
    assert store.list_entries() == []
    stats = store.stats()
    assert stats.entries == 0
    assert stats.hits == 0
    assert stats.misses == 1


def test_missing_cache_key():
    """Verify invalidating or refreshing a non-existent key returns False/None."""
    manager = CAGManager(store=LocalCacheStore())
    assert manager.invalidate_context("missing:key") is False
    assert manager.refresh_context("missing:key", "new content") is None


def test_duplicate_cache_entries():
    """Verify setting the same key overwrites the entry gracefully."""
    store = LocalCacheStore()
    entry1 = CacheEntry(
        cache_id="c1",
        namespace="ns",
        key="k1",
        content="Version 1",
    )
    entry2 = CacheEntry(
        cache_id="c1",
        namespace="ns",
        key="k1",
        content="Version 1 Overwrite",
    )
    store.set(entry1)
    store.set(entry2)
    assert store.stats().entries == 1
    retrieved = store.get("k1")
    assert retrieved is not None
    assert retrieved.content == "Version 1 Overwrite"


def test_expired_context():
    """Verify that an entry past its expires_at timestamp is treated as expired and deleted."""
    store = LocalCacheStore()
    past_time = datetime.now(timezone.utc) - timedelta(seconds=10)
    entry = CacheEntry(
        cache_id="c_expired",
        namespace="temp",
        key="temp:key",
        content="Temporary content",
        expires_at=past_time,
    )
    store.set(entry)
    assert entry.is_expired() is True

    # Accessing expired entry returns None and evicts it
    result = store.get("temp:key")
    assert result is None
    assert store.stats().entries == 0
