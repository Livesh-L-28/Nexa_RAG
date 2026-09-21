"""Chat routes for sessions, messages, RAG querying, and SSE streaming."""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db, get_rag_pipeline
from app.core.exceptions import AuthorizationException, SessionNotFoundError
from app.database.models import User
from app.database.repositories.chat_repo import ChatRepository
from app.database.repositories.log_repo import RetrievalLogRepository
from app.rag.pipeline import RAGPipeline
from app.schemas.chat import (
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ChatSessionDetailResponse,
    ChatSessionResponse,
)

router = APIRouter(prefix="/chat", tags=["Chat & RAG Retrieval"])


async def _get_chat_history(
    chat_repo: ChatRepository, session_id: uuid.UUID | None
) -> list[tuple[str, str]]:
    """Retrieve prior message history as (role, content) pairs for context."""
    if not session_id:
        return []
    messages = await chat_repo.get_messages(session_id=session_id, limit=10)
    return [(m.role, m.content) for m in messages]


@router.post(
    "",
    response_model=ChatResponse,
    summary="Execute grounded RAG query over indexed documents",
)
async def chat(
    request: ChatRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rag_pipeline: RAGPipeline = Depends(get_rag_pipeline),
) -> ChatResponse:
    chat_repo = ChatRepository(session)

    # Validate session ownership if provided
    if request.session_id:
        chat_session = await chat_repo.get_session(request.session_id)
        if not chat_session:
            raise SessionNotFoundError(f"Chat session {request.session_id} not found")
        if chat_session.user_id != current_user.id:
            raise AuthorizationException("You do not have access to this chat session")

    history = await _get_chat_history(chat_repo, request.session_id)
    req_id = getattr(http_request.state, "request_id", None) or uuid.uuid4()

    response = await rag_pipeline.query(
        session=session,
        query=request.query,
        user_id=current_user.id,
        session_id=request.session_id,
        document_ids=request.document_ids,
        top_k=request.top_k,
        similarity_threshold=request.similarity_threshold,
        chat_history=history,
        request_id=req_id,
    )
    await session.commit()
    return response


@router.post(
    "/stream",
    summary="Stream RAG synthesis response via Server-Sent Events (SSE)",
)
async def chat_stream(
    request: ChatRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rag_pipeline: RAGPipeline = Depends(get_rag_pipeline),
):
    chat_repo = ChatRepository(session)

    if request.session_id:
        chat_session = await chat_repo.get_session(request.session_id)
        if not chat_session:
            raise SessionNotFoundError(f"Chat session {request.session_id} not found")
        if chat_session.user_id != current_user.id:
            raise AuthorizationException("You do not have access to this chat session")

    history = await _get_chat_history(chat_repo, request.session_id)
    req_id = getattr(http_request.state, "request_id", None) or uuid.uuid4()

    async def event_generator():
        async for sse_event in rag_pipeline.query_stream(
            session=session,
            query=request.query,
            user_id=current_user.id,
            session_id=request.session_id,
            document_ids=request.document_ids,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
            chat_history=history,
            request_id=req_id,
        ):
            yield sse_event
        await session.commit()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/sessions",
    response_model=list[ChatSessionResponse],
    summary="List all chat sessions for the current user",
)
async def list_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ChatSessionResponse]:
    chat_repo = ChatRepository(session)
    sessions = await chat_repo.list_sessions(user_id=current_user.id, skip=skip, limit=limit)
    return [ChatSessionResponse.model_validate(s) for s in sessions]


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionDetailResponse,
    summary="Get chat session details and message history",
)
async def get_session(
    session_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatSessionDetailResponse:
    chat_repo = ChatRepository(session)
    chat_session = await chat_repo.get_session(session_id, load_messages=True)
    if not chat_session:
        raise SessionNotFoundError(f"Chat session {session_id} not found")

    if chat_session.user_id != current_user.id:
        raise AuthorizationException("You do not have access to this chat session")

    messages = await chat_repo.get_messages(session_id)
    detail = ChatSessionDetailResponse.model_validate(chat_session)
    detail.messages = [ChatMessageResponse.model_validate(m) for m in messages]
    return detail


@router.delete(
    "/sessions/{session_id}",
    summary="Delete a chat session and all its messages",
)
async def delete_session(
    session_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    chat_repo = ChatRepository(session)
    chat_session = await chat_repo.get_session(session_id)
    if not chat_session:
        raise SessionNotFoundError(f"Chat session {session_id} not found")

    if chat_session.user_id != current_user.id:
        raise AuthorizationException("You do not have access to this chat session")

    await chat_repo.delete_session(session_id)
    await session.commit()
    return {"message": "Chat session deleted successfully"}


@router.get(
    "/sessions/{session_id}/logs",
    summary="Get retrieval latency and observability logs for a session",
)
async def get_session_logs(
    session_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    chat_repo = ChatRepository(session)
    chat_session = await chat_repo.get_session(session_id)
    if not chat_session:
        raise SessionNotFoundError(f"Chat session {session_id} not found")

    if chat_session.user_id != current_user.id:
        raise AuthorizationException("You do not have access to this chat session")

    log_repo = RetrievalLogRepository(session)
    logs = await log_repo.list_by_session(session_id)
    return [
        {
            "id": str(log.id),
            "query": log.query,
            "retrieval_method": log.retrieval_method,
            "candidate_count": log.candidate_count,
            "top_k": log.top_k,
            "reranking_enabled": log.reranking_enabled,
            "retrieval_latency_ms": log.retrieval_latency_ms,
            "reranking_latency_ms": log.reranking_latency_ms,
            "llm_latency_ms": log.llm_latency_ms,
            "total_latency_ms": log.total_latency_ms,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
