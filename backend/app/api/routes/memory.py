"""Memory-Augmented Generation (MAG) routes for viewing, managing, and deleting long-term memories."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.core.exceptions import AppException
from app.database.models import User
from app.memory.models import MemoryCreate, MemoryRecord, MemoryStats
from app.memory.store import MemoryStore

router = APIRouter(prefix="/memory", tags=["Memory (MAG)"])


@router.get("", response_model=list[MemoryRecord], summary="List user memories")
async def list_memories(
    memory_type: str | None = Query(None, description="Filter by memory type"),
    include_expired: bool = Query(False, description="Include expired memories"),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MemoryRecord]:
    """Retrieve memories scoped strictly to the authenticated user."""
    return await MemoryStore.list_memories(
        session=session,
        user_id=current_user.id,
        memory_type=memory_type,
        include_expired=include_expired,
        limit=limit,
    )


@router.get("/stats", response_model=MemoryStats, summary="Get user memory statistics")
async def get_memory_stats(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MemoryStats:
    """Return memory counts broken down by category for the current user."""
    return await MemoryStore.get_stats(session=session, user_id=current_user.id)


@router.post(
    "",
    response_model=MemoryRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new memory record",
)
async def create_memory(
    data: MemoryCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MemoryRecord:
    """Create and persist a new memory entry for the authenticated user."""
    record = await MemoryStore.add_memory(
        session=session,
        user_id=current_user.id,
        memory=data,
    )
    await session.commit()
    return record


@router.delete("/{memory_id}", summary="Delete a memory record")
async def delete_memory(
    memory_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Delete a specific memory, enforcing user isolation."""
    deleted = await MemoryStore.delete_memory(
        session=session,
        memory_id=memory_id,
        user_id=current_user.id,
    )
    if not deleted:
        raise AppException(
            message=f"Memory {memory_id} not found or unauthorized.",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    await session.commit()
    return {"message": "Memory deleted successfully", "id": str(memory_id)}


@router.delete("", summary="Purge all user memories")
async def clear_all_memories(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Clear all memories associated with the current user."""
    count = await MemoryStore.delete_user_memories(session=session, user_id=current_user.id)
    await session.commit()
    return {"message": f"Successfully deleted {count} memories."}
