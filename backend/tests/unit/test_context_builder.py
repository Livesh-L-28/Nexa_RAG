"""Unit tests for ContextBuilder."""

import uuid

from app.rag.context_builder import ContextBuilder
from app.retrieval.vector_search import ScoredChunk


def test_context_builder_empty():
    builder = ContextBuilder()
    built = builder.build_context([])
    assert "No relevant document context found" in built.formatted_context
    assert len(built.citations) == 0
    assert len(built.chunk_ids) == 0


def test_context_builder_formatting_and_citations():
    builder = ContextBuilder()
    cid1 = uuid.uuid4()
    cid2 = uuid.uuid4()
    doc_id = uuid.uuid4()

    chunks = [
        ScoredChunk(
            chunk_id=cid1,
            document_id=doc_id,
            filename="handbook.pdf",
            chunk_index=0,
            content="NexaRAG processes documents with high efficiency.",
            page_number=3,
            metadata={"filename": "handbook.pdf"},
            score=0.92,
        ),
        ScoredChunk(
            chunk_id=cid2,
            document_id=doc_id,
            filename="handbook.pdf",
            chunk_index=1,
            content="Cross-encoder rerankers refine initial candidates.",
            page_number=4,
            metadata={"filename": "handbook.pdf"},
            score=0.88,
        ),
    ]

    built = builder.build_context(chunks)
    assert "[Source 1]" in built.formatted_context
    assert "[Source 2]" in built.formatted_context
    assert "handbook.pdf" in built.formatted_context
    assert "Page: 3" in built.formatted_context
    assert "Page: 4" in built.formatted_context

    assert len(built.citations) == 2
    assert built.citations[0].filename == "handbook.pdf"
    assert built.citations[0].page_number == 3
    assert built.citations[0].relevance_score == 0.92
    assert built.citations[1].page_number == 4


def test_context_builder_deduplication():
    builder = ContextBuilder()
    cid = uuid.uuid4()
    doc_id = uuid.uuid4()

    chunks = [
        ScoredChunk(
            chunk_id=cid,
            document_id=doc_id,
            filename="doc.pdf",
            chunk_index=0,
            content="Duplicate content item.",
            page_number=1,
            metadata={"filename": "doc.pdf"},
            score=0.9,
        ),
        ScoredChunk(
            chunk_id=cid,  # Same chunk ID
            document_id=doc_id,
            filename="doc.pdf",
            chunk_index=0,
            content="Duplicate content item.",
            page_number=1,
            metadata={"filename": "doc.pdf"},
            score=0.9,
        ),
    ]

    built = builder.build_context(chunks)
    assert len(built.citations) == 1
    assert len(built.chunk_ids) == 1
