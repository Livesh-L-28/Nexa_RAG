"""Configurable chunking algorithms supporting fixed-size, sentence-aware, and paragraph-aware splitting with overlap."""

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.documents.extractor import PageContent

settings = get_settings()


@dataclass
class DocumentChunkItem:
    document_id: uuid.UUID
    chunk_index: int
    content: str
    page_number: int | None
    metadata: dict[str, Any] = field(default_factory=dict)


class Chunker:
    """Configurable text chunker supporting multiple splitting strategies and overlap."""

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        strategy: str | None = None,
    ):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        self.strategy = strategy or settings.CHUNKING_STRATEGY

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be strictly less than chunk_size ({self.chunk_size})"
            )

    @staticmethod
    def _split_into_sentences(text: str) -> list[str]:
        """Split text into sentences using regex boundary detection."""
        # Splits on period, exclamation, question mark followed by space or newline
        sentence_end = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
        sentences = sentence_end.split(text)
        return [s.strip() for s in sentences if s.strip()]

    def split_fixed(self, text: str) -> list[str]:
        """Fixed character size chunking with step overlap."""
        if not text:
            return []
        chunks: list[str] = []
        step = self.chunk_size - self.chunk_overlap
        for start in range(0, len(text), step):
            chunk = text[start : start + self.chunk_size].strip()
            if chunk:
                chunks.append(chunk)
            if start + self.chunk_size >= len(text):
                break
        return chunks

    def split_sentence_aware(self, text: str) -> list[str]:
        """Sentence-aware chunking with sliding window overlap."""
        sentences = self._split_into_sentences(text)
        if not sentences:
            return self.split_fixed(text)

        chunks: list[str] = []
        current_chunk: list[str] = []
        current_len = 0

        i = 0
        while i < len(sentences):
            sentence = sentences[i]
            sentence_len = len(sentence)

            # If a single sentence exceeds chunk_size, fallback to fixed split for that sentence
            if sentence_len > self.chunk_size:
                if current_chunk:
                    chunks.append(" ".join(current_chunk).strip())
                    current_chunk = []
                    current_len = 0
                sub_chunks = self.split_fixed(sentence)
                chunks.extend(sub_chunks)
                i += 1
                continue

            # If adding sentence exceeds chunk_size, push current_chunk
            if current_len + sentence_len + 1 > self.chunk_size and current_chunk:
                chunk_str = " ".join(current_chunk).strip()
                chunks.append(chunk_str)

                # Overlap: keep trailing sentences whose combined length <= chunk_overlap
                overlap_chunk: list[str] = []
                overlap_len = 0
                for prev_sent in reversed(current_chunk):
                    if overlap_len + len(prev_sent) + 1 <= self.chunk_overlap:
                        overlap_chunk.insert(0, prev_sent)
                        overlap_len += len(prev_sent) + 1
                    else:
                        break

                current_chunk = overlap_chunk
                current_len = overlap_len

            current_chunk.append(sentence)
            current_len += sentence_len + 1
            i += 1

        if current_chunk:
            chunks.append(" ".join(current_chunk).strip())

        return chunks

    def split_paragraph_aware(self, text: str) -> list[str]:
        """Paragraph-aware chunking preserving paragraph boundaries."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return self.split_sentence_aware(text)

        chunks: list[str] = []
        current_chunk: list[str] = []
        current_len = 0

        for para in paragraphs:
            if len(para) > self.chunk_size:
                # Paragraph is too big, split with sentence-aware strategy
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk).strip())
                    current_chunk = []
                    current_len = 0
                sub_chunks = self.split_sentence_aware(para)
                chunks.extend(sub_chunks)
                continue

            if current_len + len(para) + 2 > self.chunk_size and current_chunk:
                chunks.append("\n\n".join(current_chunk).strip())
                current_chunk = []
                current_len = 0

            current_chunk.append(para)
            current_len += len(para) + 2

        if current_chunk:
            chunks.append("\n\n".join(current_chunk).strip())

        return chunks

    def chunk_text(self, text: str) -> list[str]:
        """Chunk a single text block according to configured strategy."""
        if self.strategy == "fixed":
            return self.split_fixed(text)
        elif self.strategy == "paragraph_aware":
            return self.split_paragraph_aware(text)
        else:  # Default to sentence_aware
            return self.split_sentence_aware(text)

    def chunk_document(
        self,
        document_id: uuid.UUID,
        pages: list[PageContent],
    ) -> list[DocumentChunkItem]:
        """Process page contents into DocumentChunkItems, preserving page numbers."""
        chunk_items: list[DocumentChunkItem] = []
        global_index = 0

        for page in pages:
            page_text = page.text.strip()
            if not page_text:
                continue

            text_chunks = self.chunk_text(page_text)
            for chunk_str in text_chunks:
                if not chunk_str.strip():
                    continue

                item = DocumentChunkItem(
                    document_id=document_id,
                    chunk_index=global_index,
                    content=chunk_str,
                    page_number=page.page_number,
                    metadata={
                        "char_count": len(chunk_str),
                        "token_estimate": max(1, len(chunk_str) // 4),
                        "page_number": page.page_number,
                        "strategy": self.strategy,
                        **page.metadata,
                    },
                )
                chunk_items.append(item)
                global_index += 1

        return chunk_items
