"""CAG Manager and ContextProvider implementation."""

import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from app.cag.cache import BaseCacheStore, LocalCacheStore, build_cache_key
from app.cag.models import CacheEntry, CacheStats
from app.cag.policy import CachePolicy
from app.orchestration.interfaces import ContextProvider
from app.orchestration.models import CachedContext


class CAGManager:
    """Manages cache lifecycle, versioning, size limits, and user boundaries."""

    def __init__(
        self,
        store: BaseCacheStore | None = None,
        policy: CachePolicy | None = None,
        max_context_chars: int = 4000,
    ):
        self.store = store or LocalCacheStore()
        self.policy = policy or CachePolicy()
        self.max_context_chars = max_context_chars

    def get_context(
        self,
        key: str,
        user_id: uuid.UUID | None = None,
    ) -> CachedContext | None:
        """Retrieve cached context by key enforcing isolation and character budget."""
        entry = self.store.get(key, user_id=user_id)
        if entry is None:
            return None

        # Apply context size control
        content = entry.content
        if len(content) > self.max_context_chars:
            content = content[: self.max_context_chars] + "... [Truncated by CAG size limit]"

        # Create CachedContext
        meta = dict(entry.metadata)
        meta["namespace"] = entry.namespace
        meta["cache_key"] = entry.key
        if entry.user_id:
            meta["user_id"] = str(entry.user_id)

        return CachedContext(
            content=content,
            cache_id=entry.cache_id,
            version=str(entry.version),
            priority=entry.priority,
            metadata=meta,
        )

    def set_context(
        self,
        namespace: str,
        identifier: str,
        content: str,
        user_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
        version: int = 1,
        ttl_seconds: int | None = None,
    ) -> CacheEntry:
        """Store or update a cached knowledge entry."""
        key = build_cache_key(namespace, identifier, user_id)
        cache_id = f"cag_{key.replace(':', '_')}"
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds) if ttl_seconds else None

        entry = CacheEntry(
            cache_id=cache_id,
            namespace=namespace,
            key=key,
            content=content,
            version=version,
            created_at=now,
            updated_at=now,
            user_id=user_id,
            metadata=metadata or {},
            expires_at=expires_at,
        )
        self.store.set(entry)
        return entry

    def invalidate_context(
        self,
        key: str,
        user_id: uuid.UUID | None = None,
    ) -> bool:
        """Invalidate an entry from the cache."""
        return self.store.delete(key, user_id=user_id)

    def refresh_context(
        self,
        key: str,
        new_content: str,
        user_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CacheEntry | None:
        """Refresh an existing cache entry with new content and incremented version."""
        existing = self.store.get(key, user_id=user_id)
        if existing is None:
            return None

        now = datetime.now(timezone.utc)
        new_version = existing.version + 1
        merged_meta = dict(existing.metadata)
        if metadata:
            merged_meta.update(metadata)

        updated_entry = CacheEntry(
            cache_id=existing.cache_id,
            namespace=existing.namespace,
            key=existing.key,
            content=new_content,
            version=new_version,
            created_at=existing.created_at,
            updated_at=now,
            user_id=existing.user_id,
            metadata=merged_meta,
            expires_at=existing.expires_at,
            priority=existing.priority,
        )
        self.store.set(updated_entry)
        return updated_entry

    def get_cache_stats(self) -> CacheStats:
        """Return cache hits, misses, entries, and size metrics."""
        return self.store.stats()

    def load_context(self, entries: Sequence[CacheEntry]) -> None:
        """Bulk load pre-configured cache entries."""
        for entry in entries:
            self.store.set(entry)


class CAGContextProvider(ContextProvider):
    """Integrates CAG into ContextProvider interface for ContextBundle consumption."""

    def __init__(
        self,
        manager: CAGManager,
        policy: CachePolicy | None = None,
    ):
        self.manager = manager
        self.policy = policy or manager.policy

    @property
    def source_name(self) -> str:
        return "cag"

    async def retrieve(
        self,
        query: str,
        user_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> list[CachedContext]:
        """Retrieve relevant cached contexts for the query adhering to policy and isolation."""
        if not self.policy.is_cag_eligible(query):
            return []

        resolved_keys = self.policy.resolve_cache_keys(query, user_id=user_id)
        cached_contexts: list[CachedContext] = []

        for key in resolved_keys:
            ctx = self.manager.get_context(key, user_id=user_id)
            if ctx is not None:
                cached_contexts.append(ctx)

        return cached_contexts


_global_cag_manager = CAGManager()


def get_cag_manager() -> CAGManager:
    """Return the global CAGManager singleton instance."""
    return _global_cag_manager
