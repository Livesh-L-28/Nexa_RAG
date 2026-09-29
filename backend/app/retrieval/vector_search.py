"""Vector search implementation using pgvector cosine similarity and in-memory fallback."""

import math
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database.models import Document, DocumentChunk

settings = get_settings()


@dataclass
class ScoredChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    chunk_index: int
    content: str
    page_number: int | None
    metadata: dict[str, Any]
    score: float  # Cosine similarity in [0, 1]


def compute_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two float vectors in pure Python."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


class VectorSearch:
    """Performs dense vector retrieval against pgvector document chunks."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self,
        query_vector: list[float],
        user_id: uuid.UUID,
        document_ids: list[uuid.UUID] | None = None,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
    ) -> list[ScoredChunk]:
        """Retrieve top_k chunks matching query_vector with cosine similarity >= threshold."""
        k = top_k or settings.TOP_K
        threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else settings.SIMILARITY_THRESHOLD
        )

        is_postgres = "postgresql" in settings.DATABASE_URL

        if is_postgres:
            # Native pgvector cosine distance: embedding <=> query_vector
            cosine_dist = DocumentChunk.embedding.cosine_distance(query_vector)
            where_conditions = [
                Document.status == "COMPLETED",
                (1.0 - cosine_dist) >= threshold,
            ]
            if not settings.DOCUMENTS_ADMIN_ONLY:
                where_conditions.append(Document.user_id == user_id)

            stmt = (
                select(
                    DocumentChunk,
                    Document.filename,
                    (1.0 - cosine_dist).label("similarity"),
                )
                .join(Document, DocumentChunk.document_id == Document.id)
                .where(*where_conditions)
            )
            if document_ids:
                stmt = stmt.where(Document.id.in_(document_ids))

            stmt = stmt.order_by(cosine_dist.asc()).limit(k)
            result = await self.session.execute(stmt)
            rows = result.all()

            scored: list[ScoredChunk] = []
            for chunk, filename, sim in rows:
                scored.append(
                    ScoredChunk(
                        chunk_id=chunk.id,
                        document_id=chunk.document_id,
                        filename=filename,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        page_number=chunk.page_number,
                        metadata=chunk.metadata_ or {},
                        score=float(sim),
                    )
                )
            return scored
        else:
            # In-memory fallback for SQLite / test environments
            where_conditions = [Document.status == "COMPLETED"]
            if not settings.DOCUMENTS_ADMIN_ONLY:
                where_conditions.append(Document.user_id == user_id)

            stmt = (
                select(DocumentChunk, Document.filename)
                .join(Document, DocumentChunk.document_id == Document.id)
                .where(*where_conditions)
            )
            if document_ids:
                stmt = stmt.where(Document.id.in_(document_ids))

            result = await self.session.execute(stmt)
            rows = result.all()

            scored = []
            for chunk, filename in rows:
                if chunk.embedding is not None:
                    sim = compute_cosine_similarity(query_vector, list(chunk.embedding))
                    if sim >= threshold:
                        scored.append(
                            ScoredChunk(
                                chunk_id=chunk.id,
                                document_id=chunk.document_id,
                                filename=filename,
                                chunk_index=chunk.chunk_index,
                                content=chunk.content,
                                page_number=chunk.page_number,
                                metadata=chunk.metadata_ or {},
                                score=sim,
                            )
                        )

            scored.sort(key=lambda x: x.score, reverse=True)
            return scored[:k]
