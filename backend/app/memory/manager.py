"""Manager and ContextProvider for Memory-Augmented Generation (MAG)."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.extractor import MemoryExtractor
from app.memory.models import MemoryCreate, MemoryRecord, MemoryUpdate
from app.memory.retriever import MemoryRetriever
from app.memory.store import MemoryStore
from app.orchestration.interfaces import ContextProvider
from app.orchestration.models import MemoryContext


class MemoryManager:
    """Coordinates memory extraction, persistence, conflict resolution, and retrieval."""

    def __init__(
        self,
        store: MemoryStore | None = None,
        extractor: MemoryExtractor | None = None,
        retriever: MemoryRetriever | None = None,
    ):
        self.store = store or MemoryStore()
        self.extractor = extractor or MemoryExtractor()
        self.retriever = retriever or MemoryRetriever()

    async def add_memory(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        memory_in: MemoryCreate,
    ) -> MemoryRecord:
        """Add a memory with conflict resolution against existing records."""
        mem_type_str = (
            memory_in.memory_type.value
            if hasattr(memory_in.memory_type, "value")
            else str(memory_in.memory_type)
        )
        existing = await self.store.list_memories(
            session=session,
            user_id=user_id,
            memory_type=mem_type_str,
            limit=20,
        )

        # Conflict resolution: Check if new memory supersedes existing one
        # e.g. "User prefers Python" supersedes "User prefers Java"
        target_existing: MemoryRecord | None = None
        new_words = set(memory_in.content.lower().split())

        for ex in existing:
            ex_words = set(ex.content.lower().split())
            # If both start similarly or share prefix concepts (e.g. "user prefers")
            if memory_in.content.lower().startswith(
                "user prefers"
            ) and ex.content.lower().startswith("user prefers"):
                target_existing = ex
                break
            if memory_in.content.lower().startswith(
                "user instruction"
            ) and ex.content.lower().startswith("user instruction"):
                # Check significant overlap in instruction verbs
                if len(new_words.intersection(ex_words)) >= 2:
                    target_existing = ex
                    break

        if target_existing:
            # Update existing memory with newer content and refreshed timestamp
            updated = await self.store.update_memory(
                session=session,
                memory_id=target_existing.id,
                user_id=user_id,
                update=MemoryUpdate(
                    content=memory_in.content,
                    importance=memory_in.importance,
                    metadata=memory_in.metadata,
                    expires_at=memory_in.expires_at,
                ),
            )
            return updated or target_existing

        return await self.store.add_memory(
            session=session,
            user_id=user_id,
            memory=memory_in,
        )

    async def save_from_text(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        text: str,
    ) -> list[MemoryRecord]:
        """Extract candidate memories from message text and selectively persist them."""
        candidates = self.extractor.extract(text)
        saved: list[MemoryRecord] = []
        for cand in candidates:
            rec = await self.add_memory(session=session, user_id=user_id, memory_in=cand)
            saved.append(rec)
        return saved

    async def retrieve_relevant_contexts(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        query: str,
        top_k: int | None = None,
    ) -> list[MemoryContext]:
        """Retrieve relevant memories and convert them into MemoryContext objects."""
        scored_pairs = await self.retriever.retrieve(
            session=session,
            user_id=user_id,
            query=query,
            top_k=top_k,
        )
        return [mem.to_memory_context(relevance_score=score) for mem, score in scored_pairs]

    async def get_memory(
        self,
        session: AsyncSession,
        memory_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> MemoryRecord | None:
        """Get memory by ID enforcing user isolation."""
        return await self.store.get_memory(session=session, memory_id=memory_id, user_id=user_id)

    async def delete_memory(
        self,
        session: AsyncSession,
        memory_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Delete memory by ID enforcing user isolation."""
        return await self.store.delete_memory(session=session, memory_id=memory_id, user_id=user_id)

    async def list_memories(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        memory_type: str | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        """List active memories for user."""
        return await self.store.list_memories(
            session=session, user_id=user_id, memory_type=memory_type, limit=limit
        )


class MAGContextProvider(ContextProvider):
    """Integrates MAG with the ContextProvider interface for ContextBundle consumption."""

    def __init__(self, manager: MemoryManager | None = None):
        self.manager = manager or MemoryManager()

    @property
    def source_name(self) -> str:
        return "mag"

    async def retrieve(
        self,
        query: str,
        user_id: uuid.UUID | None = None,
        session: AsyncSession | None = None,
        **kwargs: Any,
    ) -> list[MemoryContext]:
        """Retrieve relevant MemoryContext instances adhering to user ownership."""
        if user_id is None or session is None:
            return []

        top_k = kwargs.get("top_k")
        return await self.manager.retrieve_relevant_contexts(
            session=session,
            user_id=user_id,
            query=query,
            top_k=top_k,
        )

    async def extract_and_save(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        text: str,
    ) -> list[MemoryRecord]:
        """Extract and persist long-term memories from user message."""
        return await self.manager.save_from_text(
            session=session,
            user_id=user_id,
            text=text,
        )
