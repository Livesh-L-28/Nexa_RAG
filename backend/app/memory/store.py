"""Persistent database repository for long-term user memories."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Memory
from app.memory.models import MemoryCreate, MemoryRecord, MemoryStats, MemoryUpdate


class MemoryStore:
    """Repository managing CRUD operations for User memories in PostgreSQL."""

    @staticmethod
    async def add_memory(
        session: AsyncSession,
        user_id: uuid.UUID,
        memory: MemoryCreate,
    ) -> MemoryRecord:
        """Create and persist a new user memory."""
        mem_type = (
            memory.memory_type.value
            if hasattr(memory.memory_type, "value")
            else str(memory.memory_type)
        )
        db_memory = Memory(
            user_id=user_id,
            memory_type=mem_type,
            content=memory.content.strip(),
            importance=memory.importance,
            metadata_=memory.metadata,
            expires_at=memory.expires_at,
        )
        session.add(db_memory)
        await session.flush()
        return MemoryRecord.from_db(db_memory)

    @staticmethod
    async def get_memory(
        session: AsyncSession,
        memory_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> MemoryRecord | None:
        """Retrieve a specific memory enforcing user ownership boundary."""
        stmt = select(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
        result = await session.execute(stmt)
        db_memory = result.scalar_one_or_none()
        if db_memory is None:
            return None
        return MemoryRecord.from_db(db_memory)

    @staticmethod
    async def update_memory(
        session: AsyncSession,
        memory_id: uuid.UUID,
        user_id: uuid.UUID,
        update: MemoryUpdate,
    ) -> MemoryRecord | None:
        """Update a specific memory enforcing user ownership boundary."""
        stmt = select(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
        result = await session.execute(stmt)
        db_memory = result.scalar_one_or_none()
        if db_memory is None:
            return None

        if update.content is not None:
            db_memory.content = update.content.strip()
        if update.importance is not None:
            db_memory.importance = update.importance
        if update.metadata is not None:
            db_memory.metadata_ = update.metadata
        if update.expires_at is not None:
            db_memory.expires_at = update.expires_at

        db_memory.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return MemoryRecord.from_db(db_memory)

    @staticmethod
    async def delete_memory(
        session: AsyncSession,
        memory_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Delete a memory entry enforcing user ownership boundary."""
        stmt = delete(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
        result = await session.execute(stmt)
        return (result.rowcount or 0) > 0

    @staticmethod
    async def list_memories(
        session: AsyncSession,
        user_id: uuid.UUID,
        memory_type: str | None = None,
        include_expired: bool = False,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        """List memories for a user with optional type filtering and expiration check."""
        stmt = select(Memory).where(Memory.user_id == user_id)
        if memory_type:
            stmt = stmt.where(Memory.memory_type == memory_type)

        if not include_expired:
            now = datetime.now(timezone.utc)
            stmt = stmt.where((Memory.expires_at.is_(None)) | (Memory.expires_at > now))

        stmt = stmt.order_by(Memory.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        records = result.scalars().all()
        return [MemoryRecord.from_db(r) for r in records]

    @staticmethod
    async def delete_user_memories(
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> int:
        """Purge all memories belonging to a user."""
        stmt = delete(Memory).where(Memory.user_id == user_id)
        result = await session.execute(stmt)
        return result.rowcount or 0

    @staticmethod
    async def get_stats(
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> MemoryStats:
        """Compute aggregate statistics for a user's memories."""
        stmt = (
            select(Memory.memory_type, func.count(Memory.id))
            .where(Memory.user_id == user_id)
            .group_by(Memory.memory_type)
        )
        result = await session.execute(stmt)
        breakdown = dict(result.all())

        stmt_latest = select(func.max(Memory.updated_at)).where(Memory.user_id == user_id)
        latest_res = await session.execute(stmt_latest)
        latest = latest_res.scalar_one_or_none()

        total = sum(breakdown.values())
        return MemoryStats(
            total_memories=total,
            memories_by_type=breakdown,
            last_updated=latest,
        )
