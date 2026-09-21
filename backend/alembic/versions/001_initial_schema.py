"""Initial schema migration with pgvector, users, documents, chunks, chats, and logs.

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-09-20 00:00:00.000000

"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa

from alembic import op

revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Enable pgvector extension if on postgres
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Users table
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="USER"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 3. Documents table
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=20), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="PENDING"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_user_id", "documents", ["user_id"])

    # 4. Document Chunks table
    vector_col = pgvector.sqlalchemy.Vector(384) if conn.dialect.name == "postgresql" else sa.JSON()
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("embedding", vector_col, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])

    # 5. Chat Sessions table
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False, server_default="New Chat"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])

    # 6. Chat Messages table
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])

    # 7. Retrieval Logs table
    op.create_table(
        "retrieval_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("retrieved_chunk_ids", sa.JSON(), nullable=True),
        sa.Column("retrieval_method", sa.String(length=50), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("top_k", sa.Integer(), nullable=False, server_default="5"),
        sa.Column(
            "reranking_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("retrieval_latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("reranking_latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("llm_latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_retrieval_logs_session_id", "retrieval_logs", ["session_id"])
    op.create_index("ix_retrieval_logs_user_id", "retrieval_logs", ["user_id"])


def downgrade() -> None:
    op.drop_table("retrieval_logs")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("users")
