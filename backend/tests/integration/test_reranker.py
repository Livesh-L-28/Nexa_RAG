"""Integration tests for CrossEncoderReranker layer."""

import uuid

from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.vector_search import ScoredChunk


def test_reranker_disabled_fast_path():
    reranker = CrossEncoderReranker(enabled=False)
    doc_id = uuid.uuid4()
    candidates = [
        ScoredChunk(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            filename="test.pdf",
            chunk_index=0,
            content="Content A",
            page_number=1,
            metadata={},
            score=0.9,
        ),
        ScoredChunk(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            filename="test.pdf",
            chunk_index=1,
            content="Content B",
            page_number=2,
            metadata={},
            score=0.8,
        ),
    ]

    reranked = reranker.rerank(query="test query", candidates=candidates, top_k=1)
    assert len(reranked) == 1
    assert reranked[0].chunk_index == 0


def test_reranker_empty_candidates():
    reranker = CrossEncoderReranker(enabled=False)
    assert reranker.rerank(query="anything", candidates=[], top_k=5) == []
