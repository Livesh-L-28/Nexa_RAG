"""Repository for RAG observability logs."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import RetrievalLog


class RetrievalLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_log(
        self,
        query: str,
        retrieved_chunk_ids: list[str],
        retrieval_method: str,
        candidate_count: int,
        top_k: int,
        reranking_enabled: bool,
        retrieval_latency_ms: float,
        reranking_latency_ms: float,
        llm_latency_ms: float,
        total_latency_ms: float,
        session_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        request_id: uuid.UUID | None = None,
        metadata_: dict | None = None,
    ) -> RetrievalLog:
        log_entry = RetrievalLog(
            session_id=session_id,
            user_id=user_id,
            request_id=request_id,
            metadata_=metadata_ or {},
            query=query,
            retrieved_chunk_ids=retrieved_chunk_ids,
            retrieval_method=retrieval_method,
            candidate_count=candidate_count,
            top_k=top_k,
            reranking_enabled=reranking_enabled,
            retrieval_latency_ms=retrieval_latency_ms,
            reranking_latency_ms=reranking_latency_ms,
            llm_latency_ms=llm_latency_ms,
            total_latency_ms=total_latency_ms,
        )
        self.session.add(log_entry)
        await self.session.flush()
        await self.session.refresh(log_entry)
        return log_entry

    async def list_by_session(self, session_id: uuid.UUID, limit: int = 50) -> list[RetrievalLog]:
        stmt = (
            select(RetrievalLog)
            .where(RetrievalLog.session_id == session_id)
            .order_by(RetrievalLog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_user(self, user_id: uuid.UUID, limit: int = 50) -> list[RetrievalLog]:
        stmt = (
            select(RetrievalLog)
            .where(RetrievalLog.user_id == user_id)
            .order_by(RetrievalLog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
