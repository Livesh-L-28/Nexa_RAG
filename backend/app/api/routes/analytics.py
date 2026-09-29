"""Analytics, operational telemetry, and enterprise audit trail endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.database.models import (
    ChatMessage,
    ChatSession,
    Document,
    DocumentChunk,
    RetrievalLog,
    User,
    UserRole,
)
from app.observability.metrics import get_metrics_recorder

router = APIRouter(prefix="/analytics", tags=["Analytics & Telemetry"])


@router.get("/overview", summary="Get comprehensive operational platform metrics")
async def get_overview_metrics(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return aggregated platform metrics across documents, chunks, queries, and latencies."""
    is_admin = current_user.role == UserRole.ADMIN

    # 1. Documents summary
    doc_query = select(Document.status, func.count(Document.id))
    if not is_admin:
        doc_query = doc_query.where(Document.user_id == current_user.id)
    doc_query = doc_query.group_by(Document.status)
    doc_res = await session.execute(doc_query)
    doc_counts = dict(doc_res.all())
    total_docs = sum(doc_counts.values())

    # 2. Total chunks
    chunk_query = select(func.count(DocumentChunk.id)).select_from(DocumentChunk)
    if not is_admin:
        chunk_query = chunk_query.join(Document, DocumentChunk.document_id == Document.id).where(
            Document.user_id == current_user.id
        )
    chunk_res = await session.execute(chunk_query)
    total_chunks = chunk_res.scalar_one_or_none() or 0

    # 3. Chat sessions & messages
    session_query = select(func.count(ChatSession.id))
    if not is_admin:
        session_query = session_query.where(ChatSession.user_id == current_user.id)
    session_res = await session.execute(session_query)
    total_sessions = session_res.scalar_one_or_none() or 0

    msg_query = select(func.count(ChatMessage.id)).select_from(ChatMessage)
    if not is_admin:
        msg_query = msg_query.join(ChatSession, ChatMessage.session_id == ChatSession.id).where(
            ChatSession.user_id == current_user.id
        )
    msg_res = await session.execute(msg_query)
    total_messages = msg_res.scalar_one_or_none() or 0

    # 4. In-memory real-time metrics telemetry
    telemetry = get_metrics_recorder().get_metrics_summary()

    # 5. Total audit queries logged in DB
    log_query = select(func.count(RetrievalLog.id))
    if not is_admin:
        log_query = log_query.where(RetrievalLog.user_id == current_user.id)
    log_res = await session.execute(log_query)
    total_logged_queries = log_res.scalar_one_or_none() or 0

    return {
        "documents": {
            "total": total_docs,
            "status_breakdown": doc_counts,
            "total_chunks": total_chunks,
        },
        "chat": {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "total_queries": total_logged_queries,
        },
        "telemetry": telemetry,
        "is_admin": is_admin,
    }


@router.get("/audit-logs", summary="List operational retrieval and audit logs")
async def get_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    method: str | None = Query(None, description="Filter by retrieval method"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Fetch paginated audit trail of queries and security checks."""
    is_admin = current_user.role == UserRole.ADMIN

    query = select(RetrievalLog)
    if not is_admin:
        query = query.where(RetrievalLog.user_id == current_user.id)
    if method:
        query = query.where(RetrievalLog.retrieval_method == method)

    query = query.order_by(RetrievalLog.created_at.desc()).offset(skip).limit(limit)
    res = await session.execute(query)
    logs = res.scalars().all()

    # Count total
    count_query = select(func.count(RetrievalLog.id))
    if not is_admin:
        count_query = count_query.where(RetrievalLog.user_id == current_user.id)
    if method:
        count_query = count_query.where(RetrievalLog.retrieval_method == method)
    total = (await session.execute(count_query)).scalar_one_or_none() or 0

    return {
        "total": total,
        "items": [
            {
                "id": str(log.id),
                "user_id": str(log.user_id) if log.user_id else None,
                "session_id": str(log.session_id) if log.session_id else None,
                "request_id": str(log.request_id) if log.request_id else None,
                "query": log.query,
                "retrieval_method": log.retrieval_method,
                "candidate_count": log.candidate_count,
                "top_k": log.top_k,
                "reranking_enabled": log.reranking_enabled,
                "retrieval_latency_ms": log.retrieval_latency_ms,
                "reranking_latency_ms": log.reranking_latency_ms,
                "llm_latency_ms": log.llm_latency_ms,
                "total_latency_ms": log.total_latency_ms,
                "metadata": log.metadata_ or {},
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
    }
