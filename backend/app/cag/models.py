"""Pydantic data models for Cache-Augmented Generation (CAG)."""

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.orchestration.models import CachedContext, ContextPriority


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class CacheEntry(BaseModel):
    """Storage representation for a cached knowledge entry."""

    cache_id: str
    namespace: str
    key: str
    content: str
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    user_id: uuid.UUID | None = None  # None indicates globally accessible knowledge
    metadata: dict[str, Any] = Field(default_factory=dict)
    expires_at: datetime | None = None
    priority: int = ContextPriority.CAG

    model_config = ConfigDict(frozen=True)

    def is_expired(self, now: datetime | None = None) -> bool:
        """Check if entry has expired based on expires_at timestamp."""
        if self.expires_at is None:
            return False
        current_time = now or utc_now()
        return current_time > self.expires_at

    def to_cached_context(self) -> CachedContext:
        """Convert entry into the standardized CachedContext model."""
        meta = dict(self.metadata)
        meta["namespace"] = self.namespace
        meta["cache_key"] = self.key
        if self.user_id:
            meta["user_id"] = str(self.user_id)

        return CachedContext(
            content=self.content,
            cache_id=self.cache_id,
            version=str(self.version),
            priority=self.priority,
            metadata=meta,
        )


class CacheStats(BaseModel):
    """Observability metrics and counters for cache operations."""

    hits: int = 0
    misses: int = 0
    entries: int = 0
    total_size_bytes: int = 0
    last_refresh: datetime | None = None
    versions: dict[str, int] = Field(default_factory=dict)


class CAGConfig(BaseModel):
    """Runtime configuration settings for CAG."""

    enabled: bool = True
    max_context_chars: int = 4000
    default_ttl_seconds: int | None = None
