"""Deterministic cache policy for Cache-Augmented Generation (CAG)."""

import re
import uuid


class CachePolicy:
    """Deterministic policy governing CAG eligibility and cache key resolution.

    Does NOT use LLM evaluation or heuristic classifiers (reserved for Phase 10).
    Uses deterministic keyword and domain registry matching.
    """

    DEFAULT_ELIGIBLE_KEYWORDS = {
        "policy",
        "guideline",
        "standard",
        "handbook",
        "architecture",
        "faq",
        "security",
        "compliance",
        "reference",
        "overview",
    }

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        # Mapping of trigger keyword/phrase to list of cache keys
        self._registry: dict[str, list[tuple[str, uuid.UUID | None]]] = {}

    def register_domain(
        self,
        keyword: str,
        cache_key: str,
        user_id: uuid.UUID | None = None,
    ) -> None:
        """Register a keyword trigger mapping to a specific cache key."""
        clean_kw = keyword.strip().lower()
        if clean_kw not in self._registry:
            self._registry[clean_kw] = []
        # Prevent duplicates
        for existing_key, existing_uid in self._registry[clean_kw]:
            if existing_key == cache_key and existing_uid == user_id:
                return
        self._registry[clean_kw].append((cache_key, user_id))

    def unregister_domain(self, keyword: str) -> bool:
        """Unregister all cache key mappings for a keyword."""
        clean_kw = keyword.strip().lower()
        if clean_kw in self._registry:
            del self._registry[clean_kw]
            return True
        return False

    def is_cag_eligible(self, query: str) -> bool:
        """Check if query matches registered domains or default reference keywords."""
        if not self.enabled:
            return False

        words = set(re.findall(r"\b\w+\b", query.lower()))
        if words.intersection(self.DEFAULT_ELIGIBLE_KEYWORDS):
            return True

        for kw in self._registry:
            if kw in query.lower():
                return True

        return False

    def resolve_cache_keys(
        self,
        query: str,
        user_id: uuid.UUID | None = None,
    ) -> list[str]:
        """Resolve relevant cache keys for the query respecting user isolation."""
        if not self.enabled:
            return []

        resolved_keys: list[str] = []
        q_lower = query.lower()

        # Check registered domains
        for kw, entries in self._registry.items():
            if kw in q_lower:
                for cache_key, entry_user_id in entries:
                    # Accessible if global or matches requesting user
                    if entry_user_id is None or entry_user_id == user_id:
                        if cache_key not in resolved_keys:
                            resolved_keys.append(cache_key)

        return resolved_keys
