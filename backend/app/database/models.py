"""SQLAlchemy 2.x typed database models with pgvector support."""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.core.security import UserRole

__all__ = [
    "Base",
    "User",
    "Document",
    "DocumentChunk",
    "ChatSession",
    "ChatMessage",
    "RetrievalLog",
    "Memory",
    "UserRole",
]

settings = get_settings()


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy models."""


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="USER", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="user", cascade="all, delete-orphan"
    )
    chat_sessions: Mapped[list["ChatSession"]] = relationship(
        "ChatSession", back_populates="user", cascade="all, delete-orphan"
    )
    memories: Mapped[list["Memory"]] = relationship(
        "Memory", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="PENDING", nullable=False, index=True
    )  # PENDING, PROCESSING, COMPLETED, FAILED
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
    )

    def __repr__(self) -> str:
        return f"<Document {self.filename} ({self.status})>"


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    embedding = mapped_column(
        Vector(settings.EMBEDDING_DIMENSION).with_variant(JSON, "sqlite"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    __table_args__ = (Index("ix_document_chunks_doc_idx", "document_id", "chunk_index"),)

    def __repr__(self) -> str:
        return f"<DocumentChunk doc={self.document_id} idx={self.chunk_index}>"


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), default="New Chat", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )
    retrieval_logs: Mapped[list["RetrievalLog"]] = relationship(
        "RetrievalLog", back_populates="session"
    )

    def __repr__(self) -> str:
        return f"<ChatSession {self.id}: {self.title}>"


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # "user", "assistant", "system"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")

    def __repr__(self) -> str:
        return f"<ChatMessage {self.role} in {self.session_id}>"


class RetrievalLog(Base):
    __tablename__ = "retrieval_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_chunk_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    retrieval_method: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # vector, bm25, hybrid
    candidate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    reranking_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    retrieval_latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reranking_latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    llm_latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    request_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSON, default=dict, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    session: Mapped[Optional["ChatSession"]] = relationship(
        "ChatSession", back_populates="retrieval_logs"
    )

    def __repr__(self) -> str:
        return f"<RetrievalLog {self.retrieval_method} for query: {self.query[:30]}>"


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="memories")

    def __repr__(self) -> str:
        return f"<Memory {self.id} user={self.user_id} type={self.memory_type}>"
