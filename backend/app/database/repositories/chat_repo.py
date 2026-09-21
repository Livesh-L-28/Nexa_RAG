"""Chat repository for sessions and messages."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import ChatMessage, ChatSession


class ChatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_session(self, user_id: uuid.UUID, title: str = "New Chat") -> ChatSession:
        session = ChatSession(user_id=user_id, title=title)
        self.session.add(session)
        await self.session.flush()
        await self.session.refresh(session)
        return session

    async def get_session(
        self, session_id: uuid.UUID, load_messages: bool = False
    ) -> ChatSession | None:
        stmt = select(ChatSession).where(ChatSession.id == session_id)
        if load_messages:
            stmt = stmt.options(selectinload(ChatSession.messages))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_sessions(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> list[ChatSession]:
        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_session(self, session_id: uuid.UUID) -> bool:
        session = await self.get_session(session_id)
        if not session:
            return False
        await self.session.delete(session)
        await self.session.flush()
        return True

    async def update_session_title(self, session_id: uuid.UUID, title: str) -> ChatSession | None:
        session = await self.get_session(session_id)
        if not session:
            return None
        session.title = title
        await self.session.flush()
        await self.session.refresh(session)
        return session

    async def add_message(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str,
        sources: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            sources=sources,
        )
        self.session.add(message)
        await self.session.flush()
        await self.session.refresh(message)
        return message

    async def get_messages(self, session_id: uuid.UUID, limit: int = 100) -> list[ChatMessage]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
