"""Comprehensive unit and property tests for Phase 11: Context Fusion Hardening."""

import uuid
from datetime import datetime, timezone

from app.orchestration.fusion import DefaultContextFusion, TokenEstimator
from app.orchestration.models import (
    CachedContext,
    ContextBudgetConfig,
    ContextPriority,
    ContextSource,
    ConversationContext,
    MemoryContext,
    RAGContext,
)

# ============================================================================
# Helpers
# ============================================================================


def _create_rag_chunk(
    content: str,
    score: float | None = 0.90,
    chunk_id: uuid.UUID | None = None,
    doc_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> RAGContext:
    return RAGContext(
        content=content,
        document_id=doc_id or uuid.uuid4(),
        chunk_id=chunk_id or uuid.uuid4(),
        filename="system_spec.pdf",
        chunk_index=0,
        page_number=1,
        score=score,
        metadata=metadata or {},
    )


def _create_cag_context(
    content: str,
    cache_id: str = "cache_policy_1",
    version: str = "v1.0",
    metadata: dict | None = None,
) -> CachedContext:
    return CachedContext(
        content=content,
        cache_id=cache_id,
        version=version,
        metadata=metadata or {},
    )


def _create_mag_context(
    content: str,
    relevance_score: float | None = 0.85,
    memory_id: str = "mem_pref_1",
    metadata: dict | None = None,
) -> MemoryContext:
    return MemoryContext(
        content=content,
        memory_id=memory_id,
        memory_type="preference",
        relevance_score=relevance_score,
        metadata=metadata or {},
    )


def _create_conv_context(
    content: str,
    role: str = "user",
    created_at: datetime | None = None,
) -> ConversationContext:
    return ConversationContext(
        role=role,
        content=content,
        created_at=created_at or datetime.now(timezone.utc),
    )


# ============================================================================
# 1. Normalization Tests
# ============================================================================


def test_context_normalization():
    """Verify raw provider contexts normalize into canonical representation."""
    fusion = DefaultContextFusion()
    rc = _create_rag_chunk("NexaRAG normalizes enterprise context.", score=0.95)
    cc = _create_cag_context("Corporate leave guidelines.", cache_id="cache_1")
    mc = _create_mag_context("User prefers PostgreSQL.", relevance_score=0.88)
    ch = _create_conv_context("Can you help me?")

    bundle = fusion.fuse(
        query="test query",
        rag_context=[rc],
        cached_context=[cc],
        memories=[mc],
        conversation_history=[ch],
    )

    assert len(bundle.rag_context) == 1
    assert len(bundle.cached_context) == 1
    assert len(bundle.memories) == 1
    assert len(bundle.conversation_history) == 1
    assert bundle.metadata.total_context_items == 4
    assert bundle.metadata.dropped_items == 0


def test_whitespace_normalization():
    """Verify whitespace differences do not prevent duplicate detection."""
    fusion = DefaultContextFusion()
    c1 = "PostgreSQL is our primary relational database."
    c2 = "   PostgreSQL   is   our \n  primary \t relational database.  "

    rc = _create_rag_chunk(c1, score=0.9)
    mc = _create_mag_context(c2, relevance_score=0.8)

    bundle = fusion.fuse(query="db question", rag_context=[rc], memories=[mc])

    assert len(bundle.rag_context) == 1
    assert len(bundle.memories) == 0
    assert bundle.metadata.deduplicated_items == 1
    assert bundle.metadata.dropped_contexts[0].reason == "duplicate"


def test_invalid_context_rejected():
    """Verify empty or whitespace-only context items are dropped immediately."""
    fusion = DefaultContextFusion()
    valid_rc = _create_rag_chunk("Valid content here.")
    empty_rc = _create_rag_chunk("   \n\t  ")

    bundle = fusion.fuse(query="test", rag_context=[valid_rc, empty_rc])
    assert len(bundle.rag_context) == 1
    assert bundle.rag_context[0].content == "Valid content here."


# ============================================================================
# 2. Priority Tests
# ============================================================================


def test_priority_order():
    """Verify strict priority ordering: System < Security < RAG < CAG < MAG < Conversation."""
    assert ContextPriority.SYSTEM < ContextPriority.SECURITY
    assert ContextPriority.SECURITY < ContextPriority.RAG
    assert ContextPriority.RAG < ContextPriority.CAG
    assert ContextPriority.CAG < ContextPriority.MAG
    assert ContextPriority.MAG < ContextPriority.CONVERSATION
    assert ContextPriority.CONVERSATION < ContextPriority.QUERY


def test_rag_before_cag():
    """Verify RAG takes precedence over CAG for equivalent or competing context."""
    fusion = DefaultContextFusion()
    rc = _create_rag_chunk("Architecture facts from document.", score=0.95)
    cc = _create_cag_context("Architecture facts from document.", cache_id="cag_arch")

    bundle = fusion.fuse(query="test", rag_context=[rc], cached_context=[cc])
    assert len(bundle.rag_context) == 1
    assert len(bundle.cached_context) == 0
    assert bundle.metadata.dropped_contexts[0].source == ContextSource.CAG
    assert bundle.metadata.dropped_contexts[0].reason == "duplicate"


def test_cag_before_mag():
    """Verify CAG takes precedence over MAG when duplicate content exists."""
    fusion = DefaultContextFusion()
    cc = _create_cag_context("System configuration rule: use port 8000.")
    mc = _create_mag_context("System configuration rule: use port 8000.")

    bundle = fusion.fuse(query="port", cached_context=[cc], memories=[mc])
    assert len(bundle.cached_context) == 1
    assert len(bundle.memories) == 0
    assert bundle.metadata.dropped_contexts[0].source == ContextSource.MAG


def test_mag_before_conversation():
    """Verify MAG takes precedence over Conversation when content overlaps."""
    fusion = DefaultContextFusion()
    mc = _create_mag_context("User works as a Python backend engineer.")
    ch = _create_conv_context("User works as a Python backend engineer.")

    bundle = fusion.fuse(query="job", memories=[mc], conversation_history=[ch])
    assert len(bundle.memories) == 1
    assert len(bundle.conversation_history) == 0
    assert bundle.metadata.dropped_contexts[0].source == ContextSource.CONVERSATION


# ============================================================================
# 3. Deduplication Tests
# ============================================================================


def test_duplicate_context_removed():
    """Verify intra-source duplicate items are removed, retaining highest score."""
    fusion = DefaultContextFusion()
    rc1 = _create_rag_chunk("Dense embedding utilizes 384 dimensions.", score=0.75)
    rc2 = _create_rag_chunk("Dense embedding utilizes 384 dimensions.", score=0.92)

    bundle = fusion.fuse(query="embeddings", rag_context=[rc1, rc2])
    assert len(bundle.rag_context) == 1
    assert bundle.rag_context[0].score == 0.92
    assert bundle.metadata.deduplicated_items == 1


def test_cross_source_duplicate_removed():
    """Verify cross-source duplicates across RAG, CAG, and MAG are eliminated."""
    fusion = DefaultContextFusion()
    text = "The system uses FastAPI for REST endpoints."
    rc = _create_rag_chunk(text, score=0.90)
    cc = _create_cag_context(text)
    mc = _create_mag_context(text)

    bundle = fusion.fuse(query="framework", rag_context=[rc], cached_context=[cc], memories=[mc])
    assert len(bundle.rag_context) == 1
    assert len(bundle.cached_context) == 0
    assert len(bundle.memories) == 0
    assert bundle.metadata.deduplicated_items == 2


def test_higher_priority_duplicate_retained():
    """Verify lower-priority duplicate is dropped even if lower priority had higher nominal score."""
    fusion = DefaultContextFusion()
    text = "OAuth2 tokens expire in 60 minutes."
    # RAG has score 0.80, MAG has relevance 0.99. RAG still wins because RAG priority (3) < MAG priority (5).
    rc = _create_rag_chunk(text, score=0.80)
    mc = _create_mag_context(text, relevance_score=0.99)

    bundle = fusion.fuse(query="token expiry", rag_context=[rc], memories=[mc])
    assert len(bundle.rag_context) == 1
    assert len(bundle.memories) == 0
    assert bundle.metadata.dropped_contexts[0].source == ContextSource.MAG


# ============================================================================
# 4. Token Budget Tests
# ============================================================================


def test_context_budget():
    """Verify items exceeding total context budget are dropped."""
    # 1 token ~ 4 chars. A 40-char string is ~10 tokens.
    text_10_tokens_a = "A" * 40
    text_10_tokens_b = "B" * 40
    budget = ContextBudgetConfig(max_context_tokens=15)  # Can only fit 1 item
    fusion = DefaultContextFusion(budget_config=budget)

    rc1 = _create_rag_chunk(text_10_tokens_a, score=0.95)
    rc2 = _create_rag_chunk(text_10_tokens_b, score=0.85)

    bundle = fusion.fuse(query="test", rag_context=[rc1, rc2])
    assert len(bundle.rag_context) == 1
    assert bundle.rag_context[0].score == 0.95
    assert bundle.metadata.dropped_items == 1
    assert bundle.metadata.dropped_contexts[0].reason == "token_budget"


def test_priority_aware_budgeting():
    """Verify higher priority context is retained over lower priority when budget is constrained."""
    # Each item ~ 10 tokens (40 chars)
    budget = ContextBudgetConfig(max_context_tokens=15)
    fusion = DefaultContextFusion(budget_config=budget)

    rc = _create_rag_chunk("A" * 40, score=0.9)  # priority 3
    cc = _create_cag_context("B" * 40)  # priority 4
    mc = _create_mag_context("C" * 40)  # priority 5

    bundle = fusion.fuse(query="budget test", rag_context=[rc], cached_context=[cc], memories=[mc])
    assert len(bundle.rag_context) == 1
    assert len(bundle.cached_context) == 0
    assert len(bundle.memories) == 0


def test_no_partial_context_item():
    """Verify items are never truncated halfway; they are either fully included or excluded."""
    budget = ContextBudgetConfig(max_context_tokens=25)
    fusion = DefaultContextFusion(budget_config=budget)

    # item1 = 80 chars (~20 tokens), item2 = 80 chars (~20 tokens)
    rc1 = _create_rag_chunk("1" * 80, score=0.9)
    rc2 = _create_rag_chunk("2" * 80, score=0.8)

    bundle = fusion.fuse(query="test", rag_context=[rc1, rc2])
    assert len(bundle.rag_context) == 1
    # Check that rc1 content was not truncated
    assert bundle.rag_context[0].content == "1" * 80


def test_source_budget():
    """Verify source-specific token limits are respected."""
    # Each item ~ 10 tokens (40 chars)
    budget = ContextBudgetConfig(
        max_context_tokens=1000,
        max_rag_tokens=12,  # Permits only 1 RAG item
        max_cag_tokens=50,
    )
    fusion = DefaultContextFusion(budget_config=budget)

    rc1 = _create_rag_chunk("A" * 40, score=0.95)
    rc2 = _create_rag_chunk("B" * 40, score=0.90)
    cc = _create_cag_context("C" * 40)

    bundle = fusion.fuse(query="test", rag_context=[rc1, rc2], cached_context=[cc])
    assert len(bundle.rag_context) == 1
    assert len(bundle.cached_context) == 1
    assert bundle.metadata.dropped_contexts[0].reason == "source_token_budget"


def test_global_budget_overrides_source_budget():
    """Verify global budget strictly overrides source budget allowances."""
    budget = ContextBudgetConfig(
        max_context_tokens=15,  # Global limit allows only 1 item (~10 tokens)
        max_rag_tokens=100,  # Generous source limits
        max_cag_tokens=100,
    )
    fusion = DefaultContextFusion(budget_config=budget)

    rc = _create_rag_chunk("A" * 40, score=0.9)
    cc = _create_cag_context("B" * 40)

    bundle = fusion.fuse(query="test", rag_context=[rc], cached_context=[cc])
    assert len(bundle.rag_context) == 1
    assert len(bundle.cached_context) == 0


# ============================================================================
# 5. Relevance Tests
# ============================================================================


def test_low_score_context_removed():
    """Verify context items below min_context_score are excluded."""
    budget = ContextBudgetConfig(min_context_score=0.70)
    fusion = DefaultContextFusion(budget_config=budget)

    rc_high = _create_rag_chunk("High relevance doc.", score=0.88)
    rc_low = _create_rag_chunk("Low relevance noise.", score=0.45)

    bundle = fusion.fuse(query="test", rag_context=[rc_high, rc_low])
    assert len(bundle.rag_context) == 1
    assert bundle.rag_context[0].score == 0.88
    assert bundle.metadata.dropped_contexts[0].reason == "below_relevance_threshold"


def test_context_without_score_preserved():
    """Verify unscored contexts (such as CAG and Conversation) are not dropped by score filter."""
    budget = ContextBudgetConfig(min_context_score=0.80)
    fusion = DefaultContextFusion(budget_config=budget)

    cc = _create_cag_context("Company travel policy.")
    ch = _create_conv_context("Where is the office?")

    bundle = fusion.fuse(query="policy", cached_context=[cc], conversation_history=[ch])
    assert len(bundle.cached_context) == 1
    assert len(bundle.conversation_history) == 1


# ============================================================================
# 6. RAG Special Handling Tests
# ============================================================================


def test_rag_score_ordering():
    """Verify RAG chunks are consistently sorted by score descending."""
    fusion = DefaultContextFusion()
    rc1 = _create_rag_chunk("Doc A", score=0.72)
    rc2 = _create_rag_chunk("Doc B", score=0.94)
    rc3 = _create_rag_chunk("Doc C", score=0.85)

    bundle = fusion.fuse(query="test", rag_context=[rc1, rc2, rc3])
    scores = [rc.score for rc in bundle.rag_context]
    assert scores == [0.94, 0.85, 0.72]


def test_rag_citation_preserved():
    """Verify full citation attributes (document_id, chunk_id, page_number, filename) are preserved."""
    fusion = DefaultContextFusion()
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    rc = RAGContext(
        content="Enterprise citation facts.",
        document_id=doc_id,
        chunk_id=chunk_id,
        filename="compliance.pdf",
        chunk_index=2,
        page_number=7,
        score=0.91,
        metadata={"sec": "intro"},
    )

    bundle = fusion.fuse(query="test", rag_context=[rc])
    assert len(bundle.rag_context) == 1
    item = bundle.rag_context[0]
    assert item.document_id == doc_id
    assert item.chunk_id == chunk_id
    assert item.filename == "compliance.pdf"
    assert item.page_number == 7
    assert item.chunk_index == 2
    assert item.metadata == {"sec": "intro"}


# ============================================================================
# 7. CAG Special Handling Tests
# ============================================================================


def test_cache_metadata_preserved():
    """Verify cache identity, version, and metadata are intact after fusion."""
    fusion = DefaultContextFusion()
    cc = CachedContext(
        content="Global architecture schema definition.",
        cache_id="schema_v2",
        version="2.1.0",
        metadata={"author": "architect", "env": "prod"},
    )

    bundle = fusion.fuse(query="schema", cached_context=[cc])
    assert len(bundle.cached_context) == 1
    cag = bundle.cached_context[0]
    assert cag.cache_id == "schema_v2"
    assert cag.version == "2.1.0"
    assert cag.metadata["env"] == "prod"


# ============================================================================
# 8. MAG Special Handling Tests
# ============================================================================


def test_memory_metadata_preserved():
    """Verify memory attributes (memory_id, memory_type, importance) are intact."""
    fusion = DefaultContextFusion()
    mc = MemoryContext(
        content="User likes dark theme.",
        memory_id="mem_ui_99",
        memory_type="user_preference",
        importance=0.95,
        relevance_score=0.88,
        metadata={"device": "macos"},
    )

    bundle = fusion.fuse(query="theme", memories=[mc])
    assert len(bundle.memories) == 1
    m = bundle.memories[0]
    assert m.memory_id == "mem_ui_99"
    assert m.memory_type == "user_preference"
    assert m.importance == 0.95
    assert m.metadata["device"] == "macos"


def test_memory_never_overrides_rag():
    """Verify that when memory and RAG provide conflicting facts, RAG prevails."""
    fusion = DefaultContextFusion()
    rag_chunk = _create_rag_chunk("Database standard: The production database is PostgreSQL.")
    mem_chunk = _create_mag_context(
        "Database standard: The production database is PostgreSQL."
    )  # duplicate fact

    bundle = fusion.fuse(query="database", rag_context=[rag_chunk], memories=[mem_chunk])
    assert len(bundle.rag_context) == 1
    assert len(bundle.memories) == 0  # MAG dropped as duplicate of authoritative RAG


# ============================================================================
# 9. Conversation Handling Tests
# ============================================================================


def test_recent_conversation_preferred():
    """Verify recent conversation turns are prioritized over older turns under tight budget."""
    # Allow room for only 2 turns (t3 ~ 8 tokens, t2 ~ 7 tokens, t1 ~ 8 tokens). Total 23.
    budget = ContextBudgetConfig(max_context_tokens=18)
    fusion = DefaultContextFusion(budget_config=budget)

    t1 = _create_conv_context("First turn question - very old.", role="user")
    t2 = _create_conv_context("Second turn answer - medium.", role="assistant")
    t3 = _create_conv_context("Third turn question - recent.", role="user")

    bundle = fusion.fuse(query="test", conversation_history=[t1, t2, t3])
    # The 2 most recent should be selected (t2 and t3), in chronological order
    assert len(bundle.conversation_history) == 2
    contents = [ch.content for ch in bundle.conversation_history]
    assert t3.content in contents
    assert t2.content in contents
    assert t1.content not in contents


def test_old_conversation_dropped_first():
    """Verify older conversation turns are dropped before relevant RAG/CAG/MAG items."""
    budget = ContextBudgetConfig(max_context_tokens=35)
    fusion = DefaultContextFusion(budget_config=budget)

    rc = _create_rag_chunk("Authoritative document fact.", score=0.9)
    old_conv = _create_conv_context("Old small talk greeting from yesterday.")

    bundle = fusion.fuse(query="fact", rag_context=[rc], conversation_history=[old_conv])
    assert len(bundle.rag_context) == 1


# ============================================================================
# 10. Conflict Precedence Tests
# ============================================================================


def test_authoritative_context_precedence():
    """Verify strict hierarchy in conflict resolution across all 4 tiers."""
    fusion = DefaultContextFusion()
    claim = "NexaRAG port is configured to 8000."

    rc = _create_rag_chunk(claim, score=0.90)
    cc = _create_cag_context(claim)
    mc = _create_mag_context(claim)
    ch = _create_conv_context(claim)

    bundle = fusion.fuse(
        query="port",
        rag_context=[rc],
        cached_context=[cc],
        memories=[mc],
        conversation_history=[ch],
    )

    assert len(bundle.rag_context) == 1
    assert len(bundle.cached_context) == 0
    assert len(bundle.memories) == 0
    assert len(bundle.conversation_history) == 0


# ============================================================================
# 11. Security & User Isolation Tests
# ============================================================================


def test_user_context_isolation():
    """Verify that contexts tagged with a different user_id are dropped with security reason."""
    user_alice = uuid.uuid4()
    user_bob = uuid.uuid4()

    fusion = DefaultContextFusion()

    mc_alice = _create_mag_context(
        "Alice's private api key notes",
        memory_id="m1",
        metadata={"user_id": str(user_alice)},
    )
    mc_bob = _create_mag_context(
        "Bob's private api key notes",
        memory_id="m2",
        metadata={"user_id": str(user_bob)},
    )

    # Fusion for Alice
    bundle = fusion.fuse(
        query="api notes",
        memories=[mc_alice, mc_bob],
        current_user_id=user_alice,
    )

    assert len(bundle.memories) == 1
    assert bundle.memories[0].memory_id == "m1"
    dropped_reasons = [d.reason for d in bundle.metadata.dropped_contexts]
    assert "security_user_mismatch" in dropped_reasons


# ============================================================================
# 12. Edge Cases and Property Tests (Step 28)
# ============================================================================


def test_empty_context():
    """Verify empty inputs yield a valid empty bundle without errors."""
    fusion = DefaultContextFusion()
    bundle = fusion.fuse(query="empty test")

    assert bundle.query == "empty test"
    assert bundle.rag_context == []
    assert bundle.cached_context == []
    assert bundle.memories == []
    assert bundle.conversation_history == []
    assert bundle.sources == []
    assert bundle.metadata.context_count == 0


def test_only_rag():
    """Verify single-source RAG assembly."""
    fusion = DefaultContextFusion()
    rc = _create_rag_chunk("Solo RAG chunk.")
    bundle = fusion.fuse(query="solo", rag_context=[rc])
    assert len(bundle.rag_context) == 1
    assert bundle.selected_sources == ["rag"]


def test_only_cag():
    """Verify single-source CAG assembly."""
    fusion = DefaultContextFusion()
    cc = _create_cag_context("Solo CAG context.")
    bundle = fusion.fuse(query="solo", cached_context=[cc])
    assert len(bundle.cached_context) == 1
    assert bundle.selected_sources == ["cag"]


def test_only_mag():
    """Verify single-source MAG assembly."""
    fusion = DefaultContextFusion()
    mc = _create_mag_context("Solo MAG context.")
    bundle = fusion.fuse(query="solo", memories=[mc])
    assert len(bundle.memories) == 1
    assert bundle.selected_sources == ["mag"]


def test_only_conversation():
    """Verify single-source Conversation assembly."""
    fusion = DefaultContextFusion()
    ch = _create_conv_context("Solo chat turn.")
    bundle = fusion.fuse(query="solo", conversation_history=[ch])
    assert len(bundle.conversation_history) == 1
    assert bundle.selected_sources == ["conversation"]


def test_rag_plus_cag():
    """Verify dual RAG + CAG assembly."""
    fusion = DefaultContextFusion()
    rc = _create_rag_chunk("Doc context.")
    cc = _create_cag_context("Cached policy.")
    bundle = fusion.fuse(query="test", rag_context=[rc], cached_context=[cc])
    assert len(bundle.rag_context) == 1
    assert len(bundle.cached_context) == 1
    assert "rag" in bundle.selected_sources
    assert "cag" in bundle.selected_sources


def test_rag_plus_mag():
    """Verify dual RAG + MAG assembly."""
    fusion = DefaultContextFusion()
    rc = _create_rag_chunk("Doc context.")
    mc = _create_mag_context("User preference.")
    bundle = fusion.fuse(query="test", rag_context=[rc], memories=[mc])
    assert len(bundle.rag_context) == 1
    assert len(bundle.memories) == 1
    assert "rag" in bundle.selected_sources
    assert "mag" in bundle.selected_sources


def test_cag_plus_mag():
    """Verify dual CAG + MAG assembly."""
    fusion = DefaultContextFusion()
    cc = _create_cag_context("Cached policy.")
    mc = _create_mag_context("User preference.")
    bundle = fusion.fuse(query="test", cached_context=[cc], memories=[mc])
    assert len(bundle.cached_context) == 1
    assert len(bundle.memories) == 1
    assert "cag" in bundle.selected_sources
    assert "mag" in bundle.selected_sources


def test_rag_cag_mag_all_sources():
    """Verify complete 4-source assembly."""
    fusion = DefaultContextFusion()
    rc = _create_rag_chunk("Doc content.")
    cc = _create_cag_context("Policy cache.")
    mc = _create_mag_context("User memory.")
    ch = _create_conv_context("Hi assistant.")

    bundle = fusion.fuse(
        query="all",
        rag_context=[rc],
        cached_context=[cc],
        memories=[mc],
        conversation_history=[ch],
    )
    assert len(bundle.rag_context) == 1
    assert len(bundle.cached_context) == 1
    assert len(bundle.memories) == 1
    assert len(bundle.conversation_history) == 1
    assert len(bundle.sources) == 4


def test_duplicate_everything():
    """Verify that when identical text is supplied in all 4 sources, only 1 item (RAG) remains."""
    fusion = DefaultContextFusion()
    repeated = "Identical text across all systems."
    rc = _create_rag_chunk(repeated)
    cc = _create_cag_context(repeated)
    mc = _create_mag_context(repeated)
    ch = _create_conv_context(repeated)

    bundle = fusion.fuse(
        query="dup",
        rag_context=[rc],
        cached_context=[cc],
        memories=[mc],
        conversation_history=[ch],
    )
    assert len(bundle.rag_context) == 1
    assert len(bundle.cached_context) == 0
    assert len(bundle.memories) == 0
    assert len(bundle.conversation_history) == 0
    assert bundle.metadata.deduplicated_items == 3


def test_context_larger_than_budget():
    """Verify graceful handling when single context item exceeds global budget."""
    budget = ContextBudgetConfig(max_context_tokens=10)
    fusion = DefaultContextFusion(budget_config=budget)

    rc = _create_rag_chunk("Z" * 200)  # ~50 tokens > 10 tokens

    bundle = fusion.fuse(query="overflow", rag_context=[rc])
    assert len(bundle.rag_context) == 0
    assert bundle.metadata.dropped_items == 1
    assert bundle.metadata.dropped_contexts[0].reason == "token_budget"


def test_zero_budget():
    """Verify zero budget drops all context items cleanly without exception."""
    budget = ContextBudgetConfig(max_context_tokens=0)
    fusion = DefaultContextFusion(budget_config=budget)

    rc = _create_rag_chunk("Some data")
    bundle = fusion.fuse(query="zero", rag_context=[rc])
    assert len(bundle.rag_context) == 0
    assert bundle.metadata.dropped_items == 1


def test_very_large_context_item():
    """Verify very large context items estimate tokens and handle budgets without crash."""
    estimator = TokenEstimator()
    large_text = "word " * 10000  # 50,000 chars
    est = estimator.estimate(large_text)
    assert est == 12500

    fusion = DefaultContextFusion()
    rc = _create_rag_chunk(large_text)
    # Default budget is 6000 tokens, so 12500 tokens should exceed budget
    bundle = fusion.fuse(query="large", rag_context=[rc])
    assert len(bundle.rag_context) == 0
    assert bundle.metadata.dropped_contexts[0].reason == "source_token_budget"


def test_missing_metadata():
    """Verify contexts with empty metadata dicts fuse safely."""
    fusion = DefaultContextFusion()
    rc = _create_rag_chunk("Content without meta", metadata={})
    bundle = fusion.fuse(query="meta", rag_context=[rc])
    assert len(bundle.rag_context) == 1
    assert bundle.rag_context[0].metadata == {}


def test_missing_score():
    """Verify contexts with None score are handled deterministically."""
    fusion = DefaultContextFusion()
    rc_scored = _create_rag_chunk("Scored chunk", score=0.85)
    rc_unscored = _create_rag_chunk("Unscored chunk", score=None)

    bundle = fusion.fuse(query="score test", rag_context=[rc_unscored, rc_scored])
    # Scored chunk should appear before unscored chunk of the same priority
    assert bundle.rag_context[0].score == 0.85
    assert bundle.rag_context[1].score is None
