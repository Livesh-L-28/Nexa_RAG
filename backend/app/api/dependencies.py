"""FastAPI dependency injection utilities."""

import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthenticationException, AuthorizationException
from app.core.security import decode_access_token
from app.database.connection import get_session
from app.database.models import User, UserRole
from app.database.repositories.user_repo import UserRepository
from app.guardrails.service import GuardrailService, get_guardrail_service
from app.rag.pipeline import RAGPipeline

settings = get_settings()
security_bearer = HTTPBearer(auto_error=False)

# Global lazy RAG pipeline instance
_rag_pipeline_instance: RAGPipeline | None = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for obtaining an asynchronous SQLAlchemy database session."""
    async for session in get_session():
        yield session


def get_rag_pipeline(
    guardrails: GuardrailService = Depends(get_guardrail_service),
) -> RAGPipeline:
    """Dependency for obtaining the singleton RAGPipeline instance."""
    global _rag_pipeline_instance
    if _rag_pipeline_instance is None:
        _rag_pipeline_instance = RAGPipeline(
            routing_enabled=True,
            guardrail_service=guardrails,
        )
    return _rag_pipeline_instance


async def get_current_user(
    auth_header: HTTPAuthorizationCredentials | None = Security(security_bearer),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Validate Bearer JWT token and return active authenticated user."""
    if not auth_header or not auth_header.credentials:
        raise AuthenticationException("Authorization header with Bearer token is required")

    token = auth_header.credentials
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise AuthenticationException("Invalid or expired access token")

    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError:
        raise AuthenticationException("Malformed user identifier in token")

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise AuthenticationException("User account not found")

    if not user.is_active:
        raise AuthenticationException("User account is disabled")

    return user


class RoleChecker:
    """Authorization dependency verifying that user holds one of the required roles."""

    def __init__(self, allowed_roles: list[UserRole]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(get_current_user)) -> User:
        if user.role not in self.allowed_roles:
            raise AuthorizationException(
                f"User role '{user.role}' does not have sufficient permissions."
            )
        return user
