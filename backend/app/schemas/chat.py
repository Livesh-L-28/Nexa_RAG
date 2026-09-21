"""Pydantic schemas for chat sessions, messages, and RAG retrieval."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    document_id: uuid.UUID
    filename: str
    page_number: int | None = None
    chunk_index: int
    content: str
    relevance_score: float | None = None


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    session_id: uuid.UUID | None = None
    document_ids: list[uuid.UUID] | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    stream: bool = False


class RetrievalMetadata(BaseModel):
    retrieval_method: str
    candidates_count: int
    top_k: int
    reranking_enabled: bool
    retrieval_latency_ms: float
    reranking_latency_ms: float
    llm_latency_ms: float
    total_latency_ms: float
    rag_selected: bool = False
    cag_enabled: bool = False
    cag_selected: bool = False
    cache_hit: bool = False
    cache_miss: bool = False
    cache_context_count: int = 0
    cache_context_size: int = 0
    mag_enabled: bool = False
    mag_selected: bool = False
    memories_retrieved: int = 0
    memories_used: int = 0
    memory_retrieval_latency_ms: float = 0.0
    memory_types: list[str] = Field(default_factory=list)
    routing_enabled: bool = False
    routing_latency_ms: float = 0.0
    routing_confidence: float = 1.0
    routing_reason: str = ""
    selected_sources: list[str] = Field(default_factory=list)
    provider_failures: list[str] = Field(default_factory=list)
    llm_provider: str = ""
    llm_model: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    time_to_first_token_ms: float | None = None
    request_id: uuid.UUID | None = None
    prompt_build_latency_ms: float = 0.0
    estimated_input_tokens: int = 0
    dropped_contexts_count: int = 0
    dropped_reasons: dict[str, int] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    session_id: uuid.UUID
    query: str
    answer: str
    sources: list[Citation]
    retrieved_chunks: list[dict[str, Any]]
    metadata: RetrievalMetadata
    request_id: uuid.UUID | None = None


class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    sources: list[dict[str, Any]] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionDetailResponse(ChatSessionResponse):
    messages: list[ChatMessageResponse] = []
