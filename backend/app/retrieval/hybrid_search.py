"""Hybrid search combining dense vector search and sparse BM25 keyword search."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.embeddings.service import EmbeddingService
from app.retrieval.bm25_search import BM25Search
from app.retrieval.vector_search import ScoredChunk, VectorSearch

settings = get_settings()


class HybridSearch:
    """Fuses dense vector search and sparse BM25 search using weighted linear combination or RRF."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService | None = None,
        alpha: float | None = None,
    ):
        self.session = session
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_search = VectorSearch(session)
        self.bm25_search = BM25Search(session)
        self.alpha = alpha if alpha is not None else settings.HYBRID_ALPHA

        if not (0.0 <= self.alpha <= 1.0):
            raise ValueError(f"alpha must be between 0.0 and 1.0, got {self.alpha}")

    async def search(
        self,
        query: str,
        user_id: uuid.UUID,
        document_ids: list[uuid.UUID] | None = None,
        top_k: int | None = None,
        alpha: float | None = None,
        similarity_threshold: float | None = None,
        query_vector: list[float] | None = None,
        top_candidates: int | None = None,
    ) -> list[ScoredChunk]:
        """Perform hybrid retrieval combining dense vector similarity and sparse BM25."""
        k = top_k or settings.TOP_K
        candidates_limit = top_candidates or settings.TOP_N_CANDIDATES
        eff_alpha = alpha if alpha is not None else self.alpha

        # 1. Dense vector retrieval
        if query_vector is None:
            query_vector = self.embedding_service.embed_query(query)
        vector_candidates = await self.vector_search.search(
            query_vector=query_vector,
            user_id=user_id,
            document_ids=document_ids,
            top_k=candidates_limit,
            similarity_threshold=similarity_threshold,
        )

        # 2. Sparse BM25 retrieval
        bm25_candidates = await self.bm25_search.search(
            query=query,
            user_id=user_id,
            document_ids=document_ids,
            top_k=candidates_limit,
        )

        # 3. Combine scores
        # Index all candidate chunks by chunk_id
        chunk_map: dict[uuid.UUID, ScoredChunk] = {}
        vector_scores: dict[uuid.UUID, float] = {}
        bm25_scores: dict[uuid.UUID, float] = {}

        for c in vector_candidates:
            chunk_map[c.chunk_id] = c
            vector_scores[c.chunk_id] = c.score

        for c in bm25_candidates:
            chunk_map[c.chunk_id] = c
            bm25_scores[c.chunk_id] = c.score

        fused_candidates: list[ScoredChunk] = []
        for chunk_id, chunk_item in chunk_map.items():
            v_score = vector_scores.get(chunk_id, 0.0)
            b_score = bm25_scores.get(chunk_id, 0.0)

            # Weighted linear score: alpha * vector + (1 - alpha) * bm25
            final_score = (eff_alpha * v_score) + ((1.0 - eff_alpha) * b_score)

            fused_candidates.append(
                ScoredChunk(
                    chunk_id=chunk_item.chunk_id,
                    document_id=chunk_item.document_id,
                    filename=chunk_item.filename,
                    chunk_index=chunk_item.chunk_index,
                    content=chunk_item.content,
                    page_number=chunk_item.page_number,
                    metadata={
                        **chunk_item.metadata,
                        "vector_score": round(v_score, 4),
                        "bm25_score": round(b_score, 4),
                        "hybrid_alpha": eff_alpha,
                    },
                    score=final_score,
                )
            )

        # 4. Sort descending by combined score and return top k
        fused_candidates.sort(key=lambda x: x.score, reverse=True)
        return fused_candidates[:k]
