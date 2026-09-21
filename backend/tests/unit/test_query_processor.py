"""Unit tests for QueryProcessor."""

from app.rag.query_processor import QueryProcessor


def test_query_normalization():
    raw = "   What   is   pgvector?  \x00 "
    normalized = QueryProcessor.normalize(raw)
    assert normalized == "What is pgvector?"


def test_pronoun_rewriting_with_history():
    history = [
        ("user", "Tell me about PostgreSQL 16 vector extensions"),
        ("assistant", "pgvector supports cosine distance, L2 distance, and inner product."),
    ]
    query = "How do I install it?"
    rewritten = QueryProcessor.rewrite_with_history(query, history)
    assert "context:" in rewritten
    assert "pgvector" in rewritten


def test_pronoun_rewriting_without_history():
    query = "How do I install it?"
    rewritten = QueryProcessor.rewrite_with_history(query, [])
    assert rewritten == "How do I install it?"


def test_extract_keywords():
    query = "Explain hybrid search retrieval using BM25 and vector similarity"
    keywords = QueryProcessor.extract_keywords(query)
    assert "hybrid" in keywords
    assert "search" in keywords
    assert "retrieval" in keywords
    assert "bm25" in keywords
    assert "vector" in keywords
    assert "similarity" in keywords
    # Stopwords excluded
    assert "and" not in keywords
    assert "using" not in keywords
