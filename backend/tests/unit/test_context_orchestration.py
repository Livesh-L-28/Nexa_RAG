"""Unit and security tests for Phase 0 Context Orchestration."""

import uuid
from datetime import datetime, timezone

from app.orchestration.adapters import RAGContextAdapter
from app.orchestration.fusion import DefaultContextFusion
from app.orchestration.interfaces import ContextFusion
from app.orchestration.models import (
    CachedContext,
    ContextBundle,
    ContextMetadata,
    ContextPriority,
    ContextSource,
    ConversationContext,
    MemoryContext,
    RAGContext,
)
from app.rag.prompt_builder import PromptBuilder
from app.retrieval.vector_search import ScoredChunk


def test_context_bundle_defaults():
    """Verify ContextBundle defaults safely to empty collections without mutable shared state."""
    bundle1 = ContextBundle(query="What is NexaRAG?")
    bundle2 = ContextBundle(query="How does indexing work?")

    assert bundle1.query == "What is NexaRAG?"
    assert bundle1.rag_context == []
    assert bundle1.cached_context == []
    assert bundle1.memories == []
    assert bundle1.conversation_history == []
    assert bundle1.sources == []
    assert bundle1.selected_sources == []
    assert isinstance(bundle1.metadata, ContextMetadata)
    assert bundle1.metadata.context_count == 0

    # Ensure no mutable default reference sharing
    bundle1.selected_sources.append("rag")
    assert "rag" not in bundle2.selected_sources


def test_empty_context_bundle():
    """Verify empty ContextBundle behavior and conversions."""
    bundle = ContextBundle(query="Empty test")
    assert bundle.to_citations() == []

    built = RAGContextAdapter.bundle_to_built_context(bundle)
    assert "No relevant document context found" in built.formatted_context
    assert len(built.citations) == 0
    assert len(built.chunk_ids) == 0


def test_context_bundle_with_rag_context():
    """Verify ContextBundle correctly encapsulates RAGContext and creates citations."""
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    rag_item = RAGContext(
        content="NexaRAG enables high performance RAG orchestration.",
        document_id=doc_id,
        chunk_id=chunk_id,
        filename="architecture.pdf",
        chunk_index=1,
        page_number=2,
        score=0.95,
        metadata={"section": "overview"},
    )

    bundle = ContextBundle(
        query="Explain architecture",
        rag_context=[rag_item],
        sources=[ContextSource.RAG],
        selected_sources=["rag"],
    )

    assert len(bundle.rag_context) == 1
    assert bundle.rag_context[0].filename == "architecture.pdf"
    assert bundle.rag_context[0].score == 0.95
    assert bundle.rag_context[0].priority == ContextPriority.RAG

    citations = bundle.to_citations()
    assert len(citations) == 1
    assert citations[0].document_id == doc_id
    assert citations[0].filename == "architecture.pdf"
    assert citations[0].page_number == 2
    assert citations[0].relevance_score == 0.95


def test_context_bundle_with_multiple_sources():
    """Verify ContextBundle handles multi-source contracts (RAG, CAG, MAG, Conversation)."""
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    rag_item = RAGContext(
        content="Retrieval chunk from handbook.",
        document_id=doc_id,
        chunk_id=chunk_id,
        filename="handbook.pdf",
    )
    cached_item = CachedContext(
        content="Pre-computed system overview cache.",
        cache_id="cache_sys_001",
        version="v1.0",
    )
    memory_item = MemoryContext(
        content="User prefers bullet points.",
        memory_id="mem_user_pref_001",
        importance=0.9,
    )
    history_item = ConversationContext(
        role="user",
        content="Can you summarize?",
        created_at=datetime.now(timezone.utc),
    )

    bundle = ContextBundle(
        query="Summarize",
        rag_context=[rag_item],
        cached_context=[cached_item],
        memories=[memory_item],
        conversation_history=[history_item],
        sources=[
            ContextSource.RAG,
            ContextSource.CAG,
            ContextSource.MAG,
            ContextSource.CONVERSATION,
        ],
        selected_sources=["rag", "cag", "mag", "conversation"],
    )

    assert len(bundle.rag_context) == 1
    assert len(bundle.cached_context) == 1
    assert len(bundle.memories) == 1
    assert len(bundle.conversation_history) == 1
    assert bundle.cached_context[0].cache_id == "cache_sys_001"
    assert bundle.memories[0].memory_type == "user"


def test_context_source_types():
    """Verify ContextSource enum members and values."""
    assert ContextSource.RAG.value == "rag"
    assert ContextSource.CAG.value == "cag"
    assert ContextSource.MAG.value == "mag"
    assert ContextSource.CONVERSATION.value == "conversation"
    assert ContextSource.SYSTEM.value == "system"


def test_context_priority():
    """Verify ContextPriority hierarchy enforces system and security precedence."""
    assert ContextPriority.SYSTEM < ContextPriority.SECURITY
    assert ContextPriority.SECURITY < ContextPriority.RAG
    assert ContextPriority.RAG < ContextPriority.CAG
    assert ContextPriority.CAG < ContextPriority.MAG
    assert ContextPriority.MAG < ContextPriority.CONVERSATION
    assert ContextPriority.CONVERSATION < ContextPriority.QUERY

    # Absolute priority values
    assert ContextPriority.SYSTEM == 1
    assert ContextPriority.SECURITY == 2
    assert ContextPriority.RAG == 3
    assert ContextPriority.CAG == 4
    assert ContextPriority.MAG == 5
    assert ContextPriority.CONVERSATION == 6
    assert ContextPriority.QUERY == 7


def test_context_fusion():
    """Verify DefaultContextFusion deterministically fuses context sources and aggregates metrics."""
    fusion = DefaultContextFusion()
    assert isinstance(fusion, ContextFusion)

    doc_id = uuid.uuid4()
    rag_item = RAGContext(
        content="Factual doc content.",
        document_id=doc_id,
        chunk_id=uuid.uuid4(),
        filename="doc.txt",
    )
    cached_item = CachedContext(
        content="Cached knowledge block.",
        cache_id="cache_1",
    )
    conv_item = ConversationContext(role="user", content="Hello")

    bundle = fusion.fuse(
        query="What is the content?",
        rag_context=[rag_item],
        cached_context=[cached_item],
        conversation_history=[conv_item],
    )

    assert bundle.query == "What is the content?"
    assert bundle.metadata.rag_selected is True
    assert bundle.metadata.cag_selected is True
    assert bundle.metadata.mag_selected is False
    assert "rag" in bundle.selected_sources
    assert "cag" in bundle.selected_sources
    assert "conversation" in bundle.selected_sources
    assert "mag" not in bundle.selected_sources
    assert bundle.metadata.context_count == 2
    assert bundle.metadata.context_size_chars == len("Factual doc content.") + len(
        "Cached knowledge block."
    )


def test_context_metadata():
    """Verify ContextMetadata fields and defaults."""
    meta = ContextMetadata(
        rag_selected=True,
        cag_selected=False,
        mag_selected=False,
        context_sources=["rag"],
        context_count=3,
        context_size_chars=1500,
        retrieval_latency_ms=12.5,
        reranking_latency_ms=8.3,
        total_latency_ms=55.0,
    )
    assert meta.rag_selected is True
    assert meta.cag_selected is False
    assert meta.context_sources == ["rag"]
    assert meta.context_count == 3
    assert meta.context_size_chars == 1500
    assert meta.retrieval_latency_ms == 12.5
    assert meta.reranking_latency_ms == 8.3
    assert meta.total_latency_ms == 55.0


def test_rag_context_adapter():
    """Verify RAGContextAdapter adapts ScoredChunks and chat history into models."""
    chunk = ScoredChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="specs.pdf",
        chunk_index=0,
        content="System specs detail.",
        page_number=1,
        metadata={"filename": "specs.pdf"},
        score=0.91,
    )

    rag_contexts = RAGContextAdapter.chunks_to_rag_context([chunk])
    assert len(rag_contexts) == 1
    assert rag_contexts[0].chunk_id == chunk.chunk_id
    assert rag_contexts[0].document_id == chunk.document_id
    assert rag_contexts[0].filename == "specs.pdf"
    assert rag_contexts[0].score == 0.91
    assert rag_contexts[0].content == "System specs detail."

    history = [("user", "Hi"), ("assistant", "Hello!")]
    conv_contexts = RAGContextAdapter.history_to_conversation_context(history)
    assert len(conv_contexts) == 2
    assert conv_contexts[0].role == "user"
    assert conv_contexts[0].content == "Hi"
    assert conv_contexts[1].role == "assistant"
    assert conv_contexts[1].content == "Hello!"

    # Empty history
    assert RAGContextAdapter.history_to_conversation_context(None) == []


def test_prompt_builder_from_bundle():
    """Verify PromptBuilder.build_user_prompt_from_bundle preserves formatting and grounding."""
    chunk = ScoredChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="guide.pdf",
        chunk_index=0,
        content="Guide content regarding latency optimization.",
        page_number=5,
        metadata={"filename": "guide.pdf"},
        score=0.89,
    )
    rag_contexts = RAGContextAdapter.chunks_to_rag_context([chunk])
    conv_contexts = [
        ConversationContext(role="user", content="Tell me about latency."),
        ConversationContext(role="assistant", content="Checking guides..."),
    ]

    bundle = ContextBundle(
        query="What is the optimization?",
        rag_context=rag_contexts,
        conversation_history=conv_contexts,
    )

    prompt = PromptBuilder.build_user_prompt_from_bundle(bundle)
    assert "CONVERSATION HISTORY:" in prompt
    assert "User: Tell me about latency." in prompt
    assert "Assistant: Checking guides..." in prompt
    assert "DOCUMENT CONTEXT:" in prompt
    assert "[Source 1]" in prompt
    assert "Document: guide.pdf" in prompt
    assert "Page: 5" in prompt
    assert "Guide content regarding latency optimization." in prompt
    assert "USER QUESTION: What is the optimization?" in prompt
    assert "GROUNDED ANSWER (with [Source X] citations):" in prompt


def test_context_bundle_user_isolation():
    """Security test: Verify ContextBundle does not leak or cross-contaminate user contexts.

    Ensures that ContextBundle is tenant-scoped, carries already-authorized data,
    and isolates records between disparate user contexts.
    """
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()

    doc_a_id = uuid.uuid4()
    doc_b_id = uuid.uuid4()

    chunk_a = RAGContext(
        content="Secret confidential data for User A",
        document_id=doc_a_id,
        chunk_id=uuid.uuid4(),
        filename="confidential_a.pdf",
        metadata={"owner_id": str(user_a_id)},
    )
    chunk_b = RAGContext(
        content="Secret confidential data for User B",
        document_id=doc_b_id,
        chunk_id=uuid.uuid4(),
        filename="confidential_b.pdf",
        metadata={"owner_id": str(user_b_id)},
    )

    fusion = DefaultContextFusion()

    # User A bundle
    bundle_a = fusion.fuse(
        query="User A query",
        rag_context=[chunk_a],
        conversation_history=[
            ConversationContext(
                role="user",
                content="User A question",
                session_id=uuid.uuid4(),
            )
        ],
    )

    # User B bundle
    bundle_b = fusion.fuse(
        query="User B query",
        rag_context=[chunk_b],
        conversation_history=[
            ConversationContext(
                role="user",
                content="User B question",
                session_id=uuid.uuid4(),
            )
        ],
    )

    # Validate isolation
    for rc in bundle_a.rag_context:
        assert rc.metadata.get("owner_id") == str(user_a_id)
        assert "User B" not in rc.content

    for rc in bundle_b.rag_context:
        assert rc.metadata.get("owner_id") == str(user_b_id)
        assert "User A" not in rc.content

    prompt_a = PromptBuilder.build_user_prompt_from_bundle(bundle_a)
    assert "User A" in prompt_a
    assert "User B" not in prompt_a

    prompt_b = PromptBuilder.build_user_prompt_from_bundle(bundle_b)
    assert "User B" in prompt_b
    assert "User A" not in prompt_b
