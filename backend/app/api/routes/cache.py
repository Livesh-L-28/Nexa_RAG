"""Cache-Augmented Generation (CAG) observability and lifecycle management routes."""

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_current_user
from app.cag.manager import get_cag_manager
from app.cag.models import CacheEntry, CacheStats
from app.core.exceptions import AppException
from app.database.models import User, UserRole

router = APIRouter(prefix="/cache", tags=["Cache (CAG)"])


class InvalidateRequest(BaseModel):
    key: str = Field(..., description="Cache key to invalidate")


class PreloadRequest(BaseModel):
    namespace: str = Field(..., description="Cache namespace (e.g. system, user, faq)")
    identifier: str = Field(..., description="Unique entry identifier")
    content: str = Field(..., description="Cached context text")
    ttl_seconds: int | None = Field(default=None, description="Time to live in seconds")
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.get("", summary="Get CAG cache statistics and entries")
async def get_cache_info(
    namespace: str | None = Query(None, description="Filter by namespace"),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return cache hit/miss statistics and entries accessible to current user."""
    mgr = get_cag_manager()
    stats: CacheStats = mgr.get_cache_stats()

    # If ADMIN, can view all entries; otherwise only user's entries + shared system entries
    user_scope = None if current_user.role == UserRole.ADMIN else current_user.id
    entries: list[CacheEntry] = mgr.store.list_entries(user_id=user_scope)

    if namespace:
        entries = [e for e in entries if e.namespace.lower() == namespace.lower()]

    return {
        "stats": stats.model_dump(),
        "entries_count": len(entries),
        "entries": [e.model_dump() for e in entries],
    }


@router.post("/invalidate", summary="Invalidate a cache key")
async def invalidate_key(
    data: InvalidateRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Invalidate an entry from CAG cache, enforcing tenant boundary."""
    mgr = get_cag_manager()
    user_scope = None if current_user.role == UserRole.ADMIN else current_user.id
    success = mgr.invalidate_context(data.key, user_id=user_scope)
    if not success:
        raise AppException(
            message=f"Cache key '{data.key}' not found or unauthorized.",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return {"message": f"Successfully invalidated cache key '{data.key}'."}


@router.post("/preload", summary="Preload or seed a cache entry")
async def preload_entry(
    data: PreloadRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Set or update a cached knowledge entry."""
    mgr = get_cag_manager()
    # If namespace is system, require ADMIN; otherwise user owns it
    is_system = data.namespace.lower() in ("system", "global")
    if is_system and current_user.role != UserRole.ADMIN:
        raise AppException(
            message="Only administrators can manage system-level cache entries.",
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    user_scope = None if is_system else current_user.id
    entry = mgr.set_context(
        namespace=data.namespace,
        identifier=data.identifier,
        content=data.content,
        user_id=user_scope,
        metadata=data.metadata,
        ttl_seconds=data.ttl_seconds,
    )
    return {"message": "Cache entry saved", "entry": entry.model_dump()}


@router.post("/clear", summary="Clear cache namespace")
async def clear_cache(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Clear cached knowledge entries."""
    mgr = get_cag_manager()
    if current_user.role == UserRole.ADMIN:
        mgr.store.clear()
        return {"message": "All cache entries cleared successfully by administrator."}
    else:
        # Non-admin only clears own entries
        user_entries = mgr.store.list_entries(user_id=current_user.id)
        for e in user_entries:
            if e.user_id == current_user.id:
                mgr.invalidate_context(e.key, user_id=current_user.id)
        return {"message": f"Cleared {len(user_entries)} user cache entries."}
