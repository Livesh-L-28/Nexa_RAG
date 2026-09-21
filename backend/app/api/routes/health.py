"""Health check and readiness endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.core.config import get_settings
from app.core.logging import logger
from app.observability.metrics import get_metrics_recorder

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get("/health", summary="Liveness probe")
async def health_check():
    """Liveness probe verifying that the FastAPI server is responding."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ready", summary="Readiness probe")
async def readiness_check(session: AsyncSession = Depends(get_db)):
    """Readiness probe checking database connectivity and vector support."""
    db_status = "unknown"
    vector_extension = False
    details = {}

    try:
        # Check basic database connectivity
        result = await session.execute(text("SELECT 1"))
        if result.scalar() == 1:
            db_status = "connected"

        # Check pgvector extension if running on PostgreSQL
        if "postgresql" in settings.ASYNC_DATABASE_URL:
            try:
                ext_check = await session.execute(
                    text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
                )
                if ext_check.scalar_one_or_none():
                    vector_extension = True
            except Exception as e:
                logger.warning(f"Could not verify pgvector extension: {e}")
        else:
            # SQLite fallback active
            vector_extension = True
            details["database_type"] = "sqlite"

    except Exception as e:
        db_status = f"unreachable: {e!s}"
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "database": db_status,
                "vector_support": vector_extension,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    metrics_summary = get_metrics_recorder().get_metrics_summary()

    return {
        "status": "ready",
        "database": db_status,
        "vector_support": vector_extension,
        "llm_provider": settings.LLM_PROVIDER,
        "metrics": metrics_summary,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
