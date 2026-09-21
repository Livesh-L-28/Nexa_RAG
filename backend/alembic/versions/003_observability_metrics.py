"""Add request_id and metadata to retrieval_logs for pipeline observability.

Revision ID: 003_observability_metrics
Revises: 002_memory_system
Create Date: 2026-09-21 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "003_observability_metrics"
down_revision: str | None = "002_memory_system"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("retrieval_logs", sa.Column("request_id", sa.UUID(), nullable=True))
    op.add_column(
        "retrieval_logs",
        sa.Column("metadata", sa.JSON(), nullable=True, server_default="{}"),
    )
    op.create_index("ix_retrieval_logs_request_id", "retrieval_logs", ["request_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_retrieval_logs_request_id", table_name="retrieval_logs")
    op.drop_column("retrieval_logs", "metadata")
    op.drop_column("retrieval_logs", "request_id")
