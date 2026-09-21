"""User repository for database operations on users."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower().strip())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self, email: str, password_hash: str, role: str = "USER", is_active: bool = True
    ) -> User:
        user = User(
            email=email.lower().strip(),
            password_hash=password_hash,
            role=role,
            is_active=is_active,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def list_all(self, skip: int = 0, limit: int = 50) -> list[User]:
        stmt = select(User).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
