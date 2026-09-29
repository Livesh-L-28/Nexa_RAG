"""BM25 keyword search implementation using Okapi BM25."""

import math
import re
import uuid
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database.models import Document, DocumentChunk
from app.retrieval.vector_search import ScoredChunk

settings = get_settings()


def tokenize(text: str) -> list[str]:
    """Lowercase and extract alphanumeric tokens from text."""
    return re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())


class BM25Index:
    """In-memory BM25Okapi scoring engine."""

    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.doc_lengths = [len(doc) for doc in corpus]
        self.avgdl = sum(self.doc_lengths) / self.corpus_size if self.corpus_size > 0 else 1.0

        # Term frequencies and document frequencies
        self.doc_freqs: dict[str, int] = Counter()
        self.doc_term_counts: list[Counter] = []

        for doc in corpus:
            counts = Counter(doc)
            self.doc_term_counts.append(counts)
            for term in counts.keys():
                self.doc_freqs[term] += 1

        # Inverse document frequency (IDF) with BM25 smoothing
        self.idf: dict[str, float] = {}
        for term, freq in self.doc_freqs.items():
            idf_val = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)
            self.idf[term] = max(0.0, idf_val)

    def get_scores(self, query_tokens: list[str]) -> list[float]:
        """Compute BM25 scores for all documents in the corpus for the given query tokens."""
        scores = [0.0] * self.corpus_size
        if not query_tokens or self.corpus_size == 0:
            return scores

        for idx, counts in enumerate(self.doc_term_counts):
            doc_len = self.doc_lengths[idx]
            len_norm = 1.0 - self.b + self.b * (doc_len / self.avgdl)
            doc_score = 0.0

            for term in query_tokens:
                if term in counts:
                    freq = counts[term]
                    idf_val = self.idf.get(term, 0.0)
                    term_score = idf_val * ((freq * (self.k1 + 1.0)) / (freq + self.k1 * len_norm))
                    doc_score += term_score

            scores[idx] = doc_score

        return scores


class BM25Search:
    """Performs sparse keyword retrieval using BM25 across document chunks."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self,
        query: str,
        user_id: uuid.UUID,
        document_ids: list[uuid.UUID] | None = None,
        top_k: int | None = None,
    ) -> list[ScoredChunk]:
        """Retrieve top_k chunks matching query keywords with normalized BM25 scores."""
        k = top_k or settings.TOP_K
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        # Fetch candidate chunks from DB for this user/documents
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
        if not rows:
            return []

        # Build corpus of tokenized chunks
        corpus = [tokenize(chunk.content) for chunk, _ in rows]
        bm25 = BM25Index(corpus)
        raw_scores = bm25.get_scores(query_tokens)

        # Normalize raw BM25 scores to [0, 1] using min-max scaling
        max_score = max(raw_scores) if raw_scores else 0.0
        min_score = min(raw_scores) if raw_scores else 0.0

        scored_candidates: list[ScoredChunk] = []
        for idx, (chunk, filename) in enumerate(rows):
            score = raw_scores[idx]
            if score <= 0.0:
                continue

            if max_score > min_score:
                norm_score = (score - min_score) / (max_score - min_score)
            else:
                norm_score = 1.0 if score > 0 else 0.0

            scored_candidates.append(
                ScoredChunk(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    filename=filename,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    page_number=chunk.page_number,
                    metadata=chunk.metadata_ or {},
                    score=norm_score,
                )
            )

        scored_candidates.sort(key=lambda x: x.score, reverse=True)
        return scored_candidates[:k]
