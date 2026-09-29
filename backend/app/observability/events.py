"""Structured observability lifecycle events for NexaRAG."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class EventType(str, Enum):
    """Controlled set of lifecycle event types across pipeline execution."""

    REQUEST_STARTED = "request_started"
    INPUT_GUARDRAIL_COMPLETED = "input_guardrail_completed"
    QUERY_PROCESSED = "query_processed"
    CONTEXT_SOURCES_SELECTED = "context_sources_selected"
    RAG_COMPLETED = "rag_completed"
    CAG_COMPLETED = "cag_completed"
    MAG_COMPLETED = "mag_completed"
    FUSION_COMPLETED = "fusion_completed"
    RETRIEVAL_GUARDRAIL_COMPLETED = "retrieval_guardrail_completed"
    PROMPT_BUILT = "prompt_built"
    LLM_STARTED = "llm_started"
    LLM_FIRST_TOKEN = "llm_first_token"
    LLM_COMPLETED = "llm_completed"
    OUTPUT_GUARDRAIL_COMPLETED = "output_guardrail_completed"
    GUARDRAIL_BLOCKED = "guardrail_blocked"
    REQUEST_COMPLETED = "request_completed"
    STAGE_FAILED = "stage_failed"
    REQUEST_FAILED = "request_failed"


class ObservabilityEvent(BaseModel):
    """A discrete, structured lifecycle event suitable for audit logging and metrics export."""

    event: EventType | str
    request_id: uuid.UUID
    session_id: uuid.UUID | None = None
    timestamp: datetime = Field(default_factory=utc_now)
    data: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to a JSON-compatible structured dictionary."""
        event_name = self.event.value if isinstance(self.event, EventType) else str(self.event)
        return {
            "event": event_name,
            "request_id": str(self.request_id),
            "session_id": str(self.session_id) if self.session_id else None,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }
