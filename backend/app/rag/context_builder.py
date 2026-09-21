"""Context builder for structuring retrieved chunks into grounded prompt context."""

import uuid

from app.retrieval.vector_search import ScoredChunk
from app.schemas.chat import Citation


class BuiltContext:
    """Structured context result ready for prompt injection."""

    def __init__(
        self,
        formatted_context: str,
        citations: list[Citation],
        chunk_ids: list[uuid.UUID],
    ):
        self.formatted_context = formatted_context
        self.citations = citations
        self.chunk_ids = chunk_ids


class ContextBuilder:
    """Formats and prioritizes retrieved document chunks for the LLM prompt."""

    def __init__(self, max_context_chars: int = 12000):
        self.max_context_chars = max_context_chars

    def build_context(self, chunks: list[ScoredChunk]) -> BuiltContext:
        """Construct structured context blocks from scored chunks with citations."""
        if not chunks:
            return BuiltContext(
                formatted_context="No relevant document context found.",
                citations=[],
                chunk_ids=[],
            )

        context_blocks: list[str] = []
        citations: list[Citation] = []
        chunk_ids: list[uuid.UUID] = []
        current_chars = 0
        seen_chunk_ids = set()

        for idx, chunk in enumerate(chunks, start=1):
            if chunk.chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk.chunk_id)

            filename = getattr(chunk, "filename", None) or chunk.metadata.get(
                "filename", "Unknown Document"
            )
            page_number = chunk.page_number
            page_str = f"Page: {page_number}" if page_number is not None else "Page: N/A"

            block = f"[Source {idx}]\nDocument: {filename}\n{page_str}\nContent:\n{chunk.content}\n"

            # Check character budget
            if current_chars + len(block) > self.max_context_chars and len(context_blocks) > 0:
                break

            context_blocks.append(block)
            current_chars += len(block)
            chunk_ids.append(chunk.chunk_id)

            citations.append(
                Citation(
                    document_id=chunk.document_id,
                    filename=filename,
                    page_number=page_number,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content[:250] + ("..." if len(chunk.content) > 250 else ""),
                    relevance_score=round(chunk.score, 4) if chunk.score is not None else None,
                )
            )

        formatted_context = "\n---\n\n".join(context_blocks)
        return BuiltContext(
            formatted_context=formatted_context,
            citations=citations,
            chunk_ids=chunk_ids,
        )
