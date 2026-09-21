"""Pytest fixtures and configuration for unit, integration, and API tests."""

import os
import sys
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set test environment flags before importing application code
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["SECRET_KEY"] = "test_super_secret_jwt_key_at_least_32_chars_long"
os.environ["RERANKING_ENABLED"] = "false"
os.environ["UPLOAD_DIR"] = "/tmp/nexarag_test_uploads"

# Add backend directory to sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db
from app.core.security import create_access_token, hash_password
from app.database.models import Base, User
from app.main import app

# In-memory test database engine with StaticPool
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Create fresh database schema and yield clean isolated test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    """Create and persist a standard test user."""
    user = User(
        id=uuid.uuid4(),
        email="testuser@nexarag.ai",
        password_hash=hash_password("password123"),
        role="USER",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def test_admin(db_session: AsyncSession) -> User:
    """Create and persist an admin test user."""
    admin = User(
        id=uuid.uuid4(),
        email="admin@nexarag.ai",
        password_hash=hash_password("admin12345"),
        role="ADMIN",
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest_asyncio.fixture(scope="function")
def user_token(test_user: User) -> str:
    """Generate valid JWT token for test user."""
    return create_access_token(subject=str(test_user.id), role=test_user.role)


@pytest_asyncio.fixture(scope="function")
def admin_token(test_admin: User) -> str:
    """Generate valid JWT token for admin user."""
    return create_access_token(subject=str(test_admin.id), role=test_admin.role)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession):
    """Async test client with db session override."""

    async def override_get_db():
        async with TestingSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
