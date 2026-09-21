"""Pydantic schemas and enums for Memory-Augmented Generation (MAG)."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.orchestration.models import ContextPriority, MemoryContext


class MemoryType(str, Enum):
    """Classification of long-term memory entries."""

    PREFERENCE = "preference"
    PROFILE = "profile"
    PROJECT_CONTEXT = "project_context"
    CONVERSATION_FACT = "conversation_fact"
    INSTRUCTION = "instruction"
    TEMPORARY_CONTEXT = "temporary_context"


class MemoryCreate(BaseModel):
    """Payload for creating a new memory."""

    content: str
    memory_type: MemoryType | str = MemoryType.PROJECT_CONTEXT
    importance: float = Field(default=1.0, ge=0.0, le=1.0)
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryUpdate(BaseModel):
    """Payload for updating an existing memory."""

    content: str | None = None
    importance: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] | None = None
    expires_at: datetime | None = None


class MemoryRecord(BaseModel):
    """Complete domain representation of a stored memory entry."""

    id: uuid.UUID
    user_id: uuid.UUID
    memory_type: str
    content: str
    importance: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_db(cls, db_memory: Any) -> "MemoryRecord":
        """Construct MemoryRecord from SQLAlchemy Memory instance avoiding MetaData collision."""
        meta = getattr(db_memory, "metadata_", {})
        if not isinstance(meta, dict):
            meta = {}
        return cls(
            id=db_memory.id,
            user_id=db_memory.user_id,
            memory_type=db_memory.memory_type,
            content=db_memory.content,
            importance=db_memory.importance,
            metadata=meta,
            expires_at=db_memory.expires_at,
            created_at=db_memory.created_at,
            updated_at=db_memory.updated_at,
        )

    def is_expired(self, now: datetime | None = None) -> bool:
        """Check if memory has expired."""
        if self.expires_at is None:
            return False
        current_time = now or datetime.now(timezone.utc)
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        return current_time > expires_at

    def to_memory_context(self, relevance_score: float | None = None) -> MemoryContext:
        """Convert into the unified MemoryContext for ContextBundle."""
        meta = dict(self.metadata)
        meta["user_id"] = str(self.user_id)
        meta["created_at"] = self.created_at.isoformat()

        return MemoryContext(
            content=self.content,
            memory_id=str(self.id),
            memory_type=self.memory_type,
            importance=self.importance,
            relevance_score=round(relevance_score, 4) if relevance_score is not None else None,
            priority=ContextPriority.MAG,
            metadata=meta,
        )


class MemoryStats(BaseModel):
    """Aggregate statistics for a user's memory store."""

    total_memories: int = 0
    memories_by_type: dict[str, int] = Field(default_factory=dict)
    last_updated: datetime | None = None
