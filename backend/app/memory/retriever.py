"""Multi-signal memory retrieval scoring relevance, importance, and recency."""

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.models import MemoryRecord, MemoryType
from app.memory.store import MemoryStore

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "he",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "that",
    "the",
    "to",
    "was",
    "were",
    "will",
    "with",
    "what",
    "how",
    "can",
    "you",
    "i",
    "my",
    "me",
}


class MemoryRetriever:
    """Retrieves and ranks relevant user memories using lexical overlap, importance, and recency."""

    def __init__(self, default_top_k: int = 5):
        self.default_top_k = default_top_k

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """Extract meaningful alphanumeric tokens filtering stop words."""
        tokens = re.findall(r"\b\w+\b", text.lower())
        return {t for t in tokens if len(t) > 1 and t not in STOP_WORDS}

    def compute_relevance(self, query_tokens: set[str], memory: MemoryRecord) -> float:
        """Calculate lexical relevance score in [0.0, 1.0]."""
        mem_tokens = self._tokenize(memory.content)
        if not mem_tokens:
            return 0.0

        overlap = query_tokens.intersection(mem_tokens)
        if overlap:
            return min(1.0, len(overlap) / max(1, len(query_tokens)))

        # Global instructions (e.g. "always explain concisely") are relevant across queries
        if memory.memory_type == MemoryType.INSTRUCTION.value:
            return 0.4

        return 0.0

    @staticmethod
    def compute_recency(updated_at: datetime, now: datetime) -> float:
        """Calculate recency score in [0.1, 1.0] decaying over 30 days."""
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        age_seconds = max(0.0, (now - updated_at).total_seconds())
        decay_period = 30 * 86400.0  # 30 days in seconds
        fraction = age_seconds / decay_period
        return max(0.1, min(1.0, 1.0 - (fraction * 0.9)))

    async def retrieve(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        query: str,
        top_k: int | None = None,
    ) -> list[tuple[MemoryRecord, float]]:
        """Retrieve top-k relevant memories for a user given a query."""
        k = top_k or self.default_top_k
        memories = await MemoryStore.list_memories(
            session=session,
            user_id=user_id,
            include_expired=False,
            limit=100,
        )
        if not memories:
            return []

        query_tokens = self._tokenize(query)
        now = datetime.now(timezone.utc)
        scored_candidates: list[tuple[MemoryRecord, float]] = []

        for mem in memories:
            relevance = self.compute_relevance(query_tokens, mem)
            # Skip memories with zero relevance to the current question
            if relevance <= 0.0:
                continue

            importance = max(0.0, min(1.0, mem.importance))
            recency = self.compute_recency(mem.updated_at, now)

            # Combined multi-signal score:
            # 60% relevance, 25% importance, 15% recency
            final_score = (relevance * 0.6) + (importance * 0.25) + (recency * 0.15)
            scored_candidates.append((mem, round(final_score, 4)))

        # Sort descending by final score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        return scored_candidates[:k]
