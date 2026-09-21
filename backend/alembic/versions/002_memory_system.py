"""Add memories table for Memory-Augmented Generation (MAG).

Revision ID: 002_memory_system
Revises: 001_initial_schema
Create Date: 2026-09-21 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "002_memory_system"
down_revision: str | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("memory_type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_memories_user_id", "memories", ["user_id"], unique=False)
    op.create_index("ix_memories_memory_type", "memories", ["memory_type"], unique=False)
    op.create_index("ix_memories_created_at", "memories", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_memories_created_at", table_name="memories")
    op.drop_index("ix_memories_memory_type", table_name="memories")
    op.drop_index("ix_memories_user_id", table_name="memories")
    op.drop_table("memories")
