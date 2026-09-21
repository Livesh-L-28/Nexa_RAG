"""Pydantic execution models for pipeline observability metrics in NexaRAG."""

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class PipelineMetrics(BaseModel):
    """Execution telemetry captured across the end-to-end NexaRAG query lifecycle.

    Contains stage latencies, source contributions, RAG quality statistics,
    fusion deduplication/budget drops, token metrics, and error diagnostics.
    Does NOT store raw document contents, full memories, or secret credentials.
    """

    # 1. Identification & Correlation
    request_id: uuid.UUID
    session_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None

    # 2. Stage Latencies (in milliseconds)
    query_processing_latency_ms: float = 0.0
    routing_latency_ms: float = 0.0
    retrieval_latency_ms: float = 0.0
    reranking_latency_ms: float = 0.0
    cag_latency_ms: float = 0.0
    mag_latency_ms: float = 0.0
    fusion_latency_ms: float = 0.0
    prompt_build_latency_ms: float = 0.0
    llm_time_to_first_token_ms: float | None = None
    llm_generation_latency_ms: float | None = None
    total_latency_ms: float = 0.0

    # 3. RAG Retrieval & Reranking Metrics
    rag_selected: bool = False
    vector_candidates_count: int = 0
    bm25_candidates_count: int = 0
    hybrid_candidates_count: int = 0
    reranked_chunks_count: int = 0
    top_score: float | None = None
    average_score: float | None = None
    minimum_score: float | None = None
    unique_documents_count: int = 0
    unique_pages_count: int = 0
    citation_count: int = 0

    # 4. CAG Metrics
    cag_selected: bool = False
    cag_cache_hit: bool = False
    cag_cache_miss: bool = False
    cag_items_used: int = 0
    cag_context_tokens: int = 0

    # 5. MAG Metrics
    mag_selected: bool = False
    memories_considered: int = 0
    memories_retrieved: int = 0
    memories_used: int = 0
    memory_context_tokens: int = 0
    memory_types: list[str] = Field(default_factory=list)

    # 6. Context Orchestrator Metrics
    routing_enabled: bool = False
    routing_confidence: float = 1.0
    routing_reason: str = ""
    selected_sources: list[str] = Field(default_factory=list)

    # 7. Context Fusion Metrics
    contexts_received: int = 0
    contexts_selected: int = 0
    contexts_deduplicated: int = 0
    contexts_dropped: int = 0
    estimated_tokens: int = 0
    token_budget: int = 0
    dropped_reasons: dict[str, int] = Field(default_factory=dict)

    # 8. Prompt Metrics
    # Note: Explicitly marked as estimated to distinguish from provider actuals
    estimated_input_tokens: int = 0

    # 9. LLM Metrics
    llm_provider: str = ""
    llm_model: str = ""
    actual_input_tokens: int | None = None
    actual_output_tokens: int | None = None
    actual_total_tokens: int | None = None
    finish_reason: str | None = None

    # 10. Error Diagnostics
    has_error: bool = False
    error_type: str | None = None
    error_stage: str | None = None
    error_message_sanitized: str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def to_safe_summary(self) -> dict[str, Any]:
        """Export sanitized high-level dictionary suitable for telemetry export or logs."""
        return {
            "request_id": str(self.request_id),
            "session_id": str(self.session_id) if self.session_id else None,
            "user_id": str(self.user_id) if self.user_id else None,
            "total_latency_ms": self.total_latency_ms,
            "latencies": {
                "query": self.query_processing_latency_ms,
                "routing": self.routing_latency_ms,
                "retrieval": self.retrieval_latency_ms,
                "reranking": self.reranking_latency_ms,
                "cag": self.cag_latency_ms,
                "mag": self.mag_latency_ms,
                "fusion": self.fusion_latency_ms,
                "prompt": self.prompt_build_latency_ms,
                "llm_ttft": self.llm_time_to_first_token_ms,
                "llm_generation": self.llm_generation_latency_ms,
            },
            "sources": {
                "rag": self.rag_selected,
                "cag": self.cag_selected,
                "mag": self.mag_selected,
                "selected": self.selected_sources,
            },
            "rag_quality": {
                "candidates": self.hybrid_candidates_count,
                "reranked": self.reranked_chunks_count,
                "top_score": self.top_score,
                "avg_score": self.average_score,
                "citations": self.citation_count,
            },
            "fusion": {
                "received": self.contexts_received,
                "selected": self.contexts_selected,
                "deduped": self.contexts_deduplicated,
                "dropped": self.contexts_dropped,
                "dropped_reasons": self.dropped_reasons,
                "estimated_tokens": self.estimated_tokens,
            },
            "llm": {
                "provider": self.llm_provider,
                "model": self.llm_model,
                "actual_input_tokens": self.actual_input_tokens,
                "actual_output_tokens": self.actual_output_tokens,
                "actual_total_tokens": self.actual_total_tokens,
            },
            "has_error": self.has_error,
            "error_type": self.error_type,
        }
