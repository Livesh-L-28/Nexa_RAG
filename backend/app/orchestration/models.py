"""Strongly-typed models and contracts for Context Orchestration in NexaRAG."""

import uuid
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.chat import Citation


class ContextSource(str, Enum):
    """Origin sources that can contribute to the ContextBundle."""

    SYSTEM = "system"
    RAG = "rag"
    CAG = "cag"
    MAG = "mag"
    CONVERSATION = "conversation"


class ContextPriority(IntEnum):
    """Strict priority ordering for context injection to enforce system integrity."""

    SYSTEM = 1
    SECURITY = 2
    RAG = 3
    CAG = 4
    MAG = 5
    CONVERSATION = 6
    QUERY = 7


class RAGContext(BaseModel):
    """Represents authoritative context retrieved from enterprise documents."""

    content: str
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    filename: str
    chunk_index: int = 0
    page_number: int | None = None
    score: float | None = None
    priority: int = ContextPriority.RAG
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class CachedContext(BaseModel):
    """Contract representing context retrieved from Cache-Augmented Generation (CAG)."""

    content: str
    cache_id: str
    version: str | None = None
    priority: int = ContextPriority.CAG
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class MemoryContext(BaseModel):
    """Contract representing context retrieved from Memory-Augmented Generation (MAG)."""

    content: str
    memory_id: str
    memory_type: str = "user"
    importance: float = 1.0
    relevance_score: float | None = None
    priority: int = ContextPriority.MAG
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ConversationContext(BaseModel):
    """Represents conversational history turns relevant to the current session."""

    role: str
    content: str
    session_id: uuid.UUID | None = None
    created_at: datetime | None = None
    priority: int = ContextPriority.CONVERSATION

    model_config = ConfigDict(frozen=True)


class NormalizedContext(BaseModel):
    """Canonical internal context representation for fusion normalization and ranking."""

    source: ContextSource
    content: str
    priority: int
    score: float | None = None
    source_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    estimated_tokens: int = 0
    original_item: Any = Field(default=None, exclude=True)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class DroppedContext(BaseModel):
    """Diagnostic tracking record for an excluded or deduplicated context item."""

    source: ContextSource
    source_id: str
    reason: str  # "duplicate", "below_relevance_threshold", "token_budget", "source_token_budget", "security_user_mismatch", "invalid"
    priority: int
    score: float | None = None
    estimated_tokens: int = 0


class ContextBudgetConfig(BaseModel):
    """Budget constraints and relevance thresholds for hardened Context Fusion."""

    max_context_tokens: int = 6000
    max_rag_tokens: int | None = 4000
    max_cag_tokens: int | None = 1500
    max_mag_tokens: int | None = 1000
    max_conversation_tokens: int | None = 1000
    min_context_score: float | None = None

    model_config = ConfigDict(frozen=True)


class ContextMetadata(BaseModel):
    """Observability metadata tracking context assembly statistics and latencies."""

    rag_selected: bool = False
    cag_selected: bool = False
    mag_selected: bool = False
    context_sources: list[str] = Field(default_factory=list)
    context_count: int = 0
    context_size_chars: int = 0
    retrieval_latency_ms: float = 0.0
    reranking_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    routing_latency_ms: float = 0.0
    routing_confidence: float = 1.0
    routing_reason: str = ""
    provider_failures: list[str] = Field(default_factory=list)

    # Fusion hardening observability (Phase 11)
    total_context_items: int = 0
    deduplicated_items: int = 0
    dropped_items: int = 0
    estimated_tokens: int = 0
    token_budget: int = 0
    dropped_contexts: list[DroppedContext] = Field(default_factory=list)
    fusion_latency_ms: float = 0.0

    custom_attributes: dict[str, Any] = Field(default_factory=dict)


class ContextDecision(BaseModel):
    """Routing decision for an individual context source."""

    source: ContextSource
    enabled: bool
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reason: str = ""

    model_config = ConfigDict(frozen=True)


class ContextPlan(BaseModel):
    """Orchestration execution plan detailing which context sources participate."""

    use_rag: bool = False
    use_cag: bool = False
    use_mag: bool = False
    use_conversation: bool = True
    rag_top_k: int = 5
    memory_top_k: int = 5
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reason: str = ""
    decisions: list[ContextDecision] = Field(default_factory=list)

    @property
    def selected_sources(self) -> list[str]:
        """List of active context source names."""
        sources: list[str] = []
        if self.use_rag:
            sources.append(ContextSource.RAG.value)
        if self.use_cag:
            sources.append(ContextSource.CAG.value)
        if self.use_mag:
            sources.append(ContextSource.MAG.value)
        if self.use_conversation:
            sources.append(ContextSource.CONVERSATION.value)
        return sources


class ContextBundle(BaseModel):
    """Provider-agnostic unified context bundle delivered to prompt builders."""

    query: str
    rag_context: list[RAGContext] = Field(default_factory=list)
    cached_context: list[CachedContext] = Field(default_factory=list)
    memories: list[MemoryContext] = Field(default_factory=list)
    conversation_history: list[ConversationContext] = Field(default_factory=list)
    sources: list[ContextSource] = Field(default_factory=list)
    selected_sources: list[str] = Field(default_factory=list)
    metadata: ContextMetadata = Field(default_factory=ContextMetadata)

    def to_citations(self) -> list[Citation]:
        """Convert RAG contexts into API citations."""
        citations: list[Citation] = []
        for rc in self.rag_context:
            preview = rc.content[:250] + ("..." if len(rc.content) > 250 else "")
            citations.append(
                Citation(
                    document_id=rc.document_id,
                    filename=rc.filename,
                    page_number=rc.page_number,
                    chunk_index=rc.chunk_index,
                    content=preview,
                    relevance_score=round(rc.score, 4) if rc.score is not None else None,
                )
            )
        return citations
