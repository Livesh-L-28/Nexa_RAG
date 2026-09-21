"""Integration tests for BM25, cosine similarity, and hybrid retrieval fusion."""

import pytest

from app.retrieval.bm25_search import BM25Index, tokenize
from app.retrieval.vector_search import compute_cosine_similarity


def test_compute_cosine_similarity():
    # Identical vectors
    v1 = [1.0, 0.0, 0.0]
    assert pytest.approx(compute_cosine_similarity(v1, v1), 0.001) == 1.0

    # Orthogonal vectors
    v2 = [0.0, 1.0, 0.0]
    assert pytest.approx(compute_cosine_similarity(v1, v2), 0.001) == 0.0

    # Opposite or zero vectors
    assert compute_cosine_similarity([], []) == 0.0
    assert compute_cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0


def test_bm25_index_scoring():
    corpus = [
        tokenize("The quick brown fox jumps over the lazy dog"),
        tokenize("NexaRAG provides enterprise document intelligence"),
        tokenize("Vector embeddings and BM25 hybrid search retrieval"),
    ]
    index = BM25Index(corpus)

    # Query matching doc 1
    scores = index.get_scores(tokenize("enterprise document"))
    assert scores[1] > scores[0]
    assert scores[1] > scores[2]

    # Query matching doc 2
    scores_hybrid = index.get_scores(tokenize("hybrid search"))
    assert scores_hybrid[2] > scores_hybrid[0]
    assert scores_hybrid[2] > scores_hybrid[1]
