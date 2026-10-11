"""Asynchronous database connection, sessionmaker, and health checks."""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.logging import logger

settings = get_settings()


def get_async_database_url(url: str) -> str:
    """Normalize database URL for asyncpg when connecting via standard postgresql URL."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


async_db_url = get_async_database_url(settings.DATABASE_URL)

# Configure engine based on driver
engine_kwargs = {
    "echo": settings.DB_ECHO,
    "future": True,
}

# If using PostgreSQL with asyncpg, add pool settings
if "postgresql" in async_db_url:
    engine_kwargs.update(
        {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_pre_ping": True,
        }
    )

engine: AsyncEngine = create_async_engine(async_db_url, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency yielding an async database session with automatic rollback on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


get_session = get_db


async def init_db() -> None:
    """Initialize database tables and extensions."""
    from app.database.models import Base

    async with engine.begin() as conn:
        if "postgresql" in settings.DATABASE_URL:
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            except Exception as e:
                logger.warning(f"Could not initialize pgvector extension: {e}")
        await conn.run_sync(Base.metadata.create_all)


async def check_db_connection() -> dict:
    """Check database connectivity and pgvector extension status for health checks."""
    try:
        async with AsyncSessionLocal() as session:
            # Check basic connection
            result = await session.execute(text("SELECT 1"))
            scalar = result.scalar()

            # Check pgvector extension in PostgreSQL
            vector_installed = False
            if "postgresql" in settings.DATABASE_URL:
                vec_check = await session.execute(
                    text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
                )
                vector_installed = vec_check.scalar() is not None
            else:
                vector_installed = True  # In fallback/sqlite mode

            return {
                "database": "connected" if scalar == 1 else "unhealthy",
                "pgvector": "installed" if vector_installed else "not_installed",
                "healthy": scalar == 1 and vector_installed,
            }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "database": "disconnected",
            "pgvector": "unknown",
            "healthy": False,
            "error": str(e),
        }
