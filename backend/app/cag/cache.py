"""Cache storage implementations for Cache-Augmented Generation (CAG)."""

import json
import threading
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.cag.models import CacheEntry, CacheStats


def build_cache_key(namespace: str, identifier: str, user_id: uuid.UUID | None = None) -> str:
    """Build a deterministic cache key adhering to namespace and ownership."""
    clean_ns = namespace.strip().lower()
    clean_id = identifier.strip().lower()
    if user_id:
        return f"{clean_ns}:{user_id}:{clean_id}"
    return f"{clean_ns}:{clean_id}"


class BaseCacheStore(ABC):
    """Abstract base class for CAG cache backends."""

    @abstractmethod
    def get(self, key: str, user_id: uuid.UUID | None = None) -> CacheEntry | None:
        """Retrieve an entry by key enforcing user isolation."""

    @abstractmethod
    def set(self, entry: CacheEntry) -> None:
        """Store or update a cache entry."""

    @abstractmethod
    def delete(self, key: str, user_id: uuid.UUID | None = None) -> bool:
        """Delete an entry by key enforcing user isolation."""

    @abstractmethod
    def clear(self) -> None:
        """Clear all entries in the store."""

    @abstractmethod
    def list_entries(self, user_id: uuid.UUID | None = None) -> list[CacheEntry]:
        """List active entries accessible to the provided user."""

    @abstractmethod
    def stats(self) -> CacheStats:
        """Return cache hit/miss statistics and storage metrics."""

    @abstractmethod
    def record_hit(self) -> None:
        """Increment cache hit counter."""

    @abstractmethod
    def record_miss(self) -> None:
        """Increment cache miss counter."""


class LocalCacheStore(BaseCacheStore):
    """Thread-safe local in-memory cache store with optional file-based persistence."""

    def __init__(self, persistence_file: Path | str | None = None):
        self._lock = threading.RLock()
        self._entries: dict[str, CacheEntry] = {}
        self._hits: int = 0
        self._misses: int = 0
        self._last_refresh: datetime | None = None
        self._persistence_file = Path(persistence_file) if persistence_file else None

        if self._persistence_file and self._persistence_file.exists():
            self._load_from_disk()

    def _persist_to_disk(self) -> None:
        """Persist cache entries to disk as JSON if persistence_file is configured."""
        if not self._persistence_file:
            return
        try:
            self._persistence_file.parent.mkdir(parents=True, exist_ok=True)
            data: dict[str, Any] = {}
            for k, entry in self._entries.items():
                data[k] = entry.model_dump(mode="json")
            with open(self._persistence_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass  # Fall back to in-memory silently without crashing

    def _load_from_disk(self) -> None:
        """Load cache entries from disk JSON file."""
        if not self._persistence_file or not self._persistence_file.exists():
            return
        try:
            with open(self._persistence_file, encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                self._entries[k] = CacheEntry.model_validate(v)
        except Exception:
            self._entries.clear()

    def record_hit(self) -> None:
        with self._lock:
            self._hits += 1

    def record_miss(self) -> None:
        with self._lock:
            self._misses += 1

    def get(self, key: str, user_id: uuid.UUID | None = None) -> CacheEntry | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None

            # Check expiration
            if entry.is_expired():
                del self._entries[key]
                self._misses += 1
                self._persist_to_disk()
                return None

            # Enforce user boundary
            if entry.user_id is not None and entry.user_id != user_id:
                # User B cannot access User A's cache entry
                self._misses += 1
                return None

            self._hits += 1
            return entry

    def set(self, entry: CacheEntry) -> None:
        with self._lock:
            self._entries[entry.key] = entry
            self._last_refresh = datetime.now(timezone.utc)
            self._persist_to_disk()

    def delete(self, key: str, user_id: uuid.UUID | None = None) -> bool:
        with self._lock:
            entry = self._entries.get(key)
            if not entry:
                return False

            # Isolation check: only owner or global admin can delete
            if entry.user_id is not None and user_id is not None and entry.user_id != user_id:
                return False

            del self._entries[key]
            self._persist_to_disk()
            return True

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._persist_to_disk()

    def list_entries(self, user_id: uuid.UUID | None = None) -> list[CacheEntry]:
        with self._lock:
            valid: list[CacheEntry] = []
            expired_keys: list[str] = []

            for k, entry in self._entries.items():
                if entry.is_expired():
                    expired_keys.append(k)
                    continue
                # Include if global or matches requesting user
                if entry.user_id is None or entry.user_id == user_id:
                    valid.append(entry)

            for ek in expired_keys:
                del self._entries[ek]

            return valid

    def stats(self) -> CacheStats:
        with self._lock:
            total_bytes = sum(len(e.content.encode("utf-8")) for e in self._entries.values())
            versions = {e.cache_id: e.version for e in self._entries.values()}
            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                entries=len(self._entries),
                total_size_bytes=total_bytes,
                last_refresh=self._last_refresh,
                versions=versions,
            )
