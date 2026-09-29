"""Administration routes for user management, role modification, and system configuration."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import RoleChecker, get_db
from app.core.config import get_settings
from app.core.exceptions import AppException
from app.database.models import User, UserRole

router = APIRouter(prefix="/admin", tags=["Administration"])
settings = get_settings()

admin_required = RoleChecker([UserRole.ADMIN])


class UserUpdateRequest(BaseModel):
    role: str | None = Field(default=None, description="USER or ADMIN")
    is_active: bool | None = Field(default=None, description="Active status toggle")


@router.get("/users", summary="List all platform users (Admin only)")
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(admin_required),
) -> dict[str, Any]:
    """Retrieve platform user registry with roles and statuses."""
    stmt = select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
    res = await session.execute(stmt)
    users = res.scalars().all()

    return {
        "total": len(users),
        "items": [
            {
                "id": str(u.id),
                "email": u.email,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ],
    }


@router.patch("/users/{user_id}", summary="Update user role or active status (Admin only)")
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdateRequest,
    session: AsyncSession = Depends(get_db),
    current_admin: User = Depends(admin_required),
) -> dict[str, Any]:
    """Change a user's role or activate/deactivate an account."""
    stmt = select(User).where(User.id == user_id)
    res = await session.execute(stmt)
    target_user = res.scalar_one_or_none()
    if not target_user:
        raise AppException(
            message=f"User {user_id} not found.",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Protect self-demotion
    if target_user.id == current_admin.id and data.role == UserRole.USER:
        raise AppException(
            message="Administrators cannot demote their own account.",
            code="INVALID_OPERATION",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if data.role is not None:
        if data.role.upper() not in (UserRole.ADMIN, UserRole.USER):
            raise AppException(
                message="Role must be either 'ADMIN' or 'USER'.",
                code="INVALID_ROLE",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        target_user.role = data.role.upper()

    if data.is_active is not None:
        if target_user.id == current_admin.id and not data.is_active:
            raise AppException(
                message="Administrators cannot disable their own account.",
                code="INVALID_OPERATION",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        target_user.is_active = data.is_active

    await session.commit()
    return {
        "message": "User updated successfully",
        "user": {
            "id": str(target_user.id),
            "email": target_user.email,
            "role": target_user.role,
            "is_active": target_user.is_active,
        },
    }


@router.get("/system-config", summary="Get platform system configuration (Admin only)")
async def get_system_config(
    _: User = Depends(admin_required),
) -> dict[str, Any]:
    """Return sanitized non-secret system settings for platform transparency."""
    return {
        "app_name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL_NAME,
        "embedding_dimension": settings.EMBEDDING_DIMENSION,
        "embedding_device": settings.EMBEDDING_DEVICE,
        "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
        "allowed_extensions": settings.ALLOWED_EXTENSIONS,
        "chunk_size": settings.CHUNK_SIZE,
        "chunk_overlap": settings.CHUNK_OVERLAP,
        "chunking_strategy": settings.CHUNKING_STRATEGY,
        "top_k": settings.TOP_K,
        "similarity_threshold": settings.SIMILARITY_THRESHOLD,
        "reranking_enabled": settings.RERANKING_ENABLED,
        "access_token_expire_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    }
