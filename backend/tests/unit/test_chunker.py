"""Unit tests for text chunking algorithms and page metadata preservation."""

import uuid

import pytest

from app.documents.chunker import Chunker
from app.documents.extractor import PageContent


def test_chunker_fixed_size():
    chunker = Chunker(chunk_size=50, chunk_overlap=10, strategy="fixed")
    sample_text = "A" * 120
    chunks = chunker.split_fixed(sample_text)
    assert len(chunks) >= 3
    for chunk in chunks:
        assert len(chunk) <= 50


def test_chunker_sentence_aware():
    chunker = Chunker(chunk_size=100, chunk_overlap=20, strategy="sentence_aware")
    text = (
        "First sentence is here. Second sentence follows immediately. "
        "Third sentence is quite informative. Fourth sentence completes the paragraph."
    )
    chunks = chunker.split_sentence_aware(text)
    assert len(chunks) >= 1
    assert "First sentence is here." in chunks[0]


def test_chunker_paragraph_aware():
    chunker = Chunker(chunk_size=120, chunk_overlap=20, strategy="paragraph_aware")
    text = "Paragraph one with detail.\n\nParagraph two with different concepts."
    chunks = chunker.split_paragraph_aware(text)
    assert len(chunks) >= 1


def test_chunker_invalid_overlap_raises():
    with pytest.raises(ValueError):
        Chunker(chunk_size=50, chunk_overlap=50)


def test_chunk_document_preserves_page_numbers():
    chunker = Chunker(chunk_size=100, chunk_overlap=20)
    pages = [
        PageContent(page_number=1, text="Page 1 text content here with facts."),
        PageContent(page_number=2, text="Page 2 text content with additional context."),
    ]
    doc_id = uuid.uuid4()
    chunk_items = chunker.chunk_document(document_id=doc_id, pages=pages)

    assert len(chunk_items) == 2
    assert chunk_items[0].page_number == 1
    assert chunk_items[1].page_number == 2
    assert chunk_items[0].document_id == doc_id
    assert chunk_items[0].chunk_index == 0
    assert chunk_items[1].chunk_index == 1
