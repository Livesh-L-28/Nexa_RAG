"""Adapters bridging existing RAG retrieval results and ContextBundle."""

import uuid
from collections.abc import Sequence

from app.orchestration.models import ContextBundle, ConversationContext, RAGContext
from app.rag.context_builder import BuiltContext
from app.retrieval.vector_search import ScoredChunk
from app.schemas.chat import Citation


class RAGContextAdapter:
    """Adapter bridging legacy ScoredChunks and chat histories into ContextBundle models."""

    @staticmethod
    def chunks_to_rag_context(chunks: Sequence[ScoredChunk]) -> list[RAGContext]:
        """Convert retrieval ScoredChunks into strongly-typed RAGContext items."""
        rag_contexts: list[RAGContext] = []
        for chunk in chunks:
            rag_contexts.append(
                RAGContext(
                    content=chunk.content,
                    document_id=chunk.document_id,
                    chunk_id=chunk.chunk_id,
                    filename=chunk.filename,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    score=chunk.score,
                    metadata=dict(chunk.metadata),
                )
            )
        return rag_contexts

    @staticmethod
    def history_to_conversation_context(
        history: list[tuple[str, str]] | None,
    ) -> list[ConversationContext]:
        """Convert (role, content) history tuples into ConversationContext models."""
        if not history:
            return []
        return [ConversationContext(role=role, content=content) for role, content in history]

    @staticmethod
    def bundle_to_built_context(
        bundle: ContextBundle,
        max_context_chars: int = 12000,
    ) -> BuiltContext:
        """Construct BuiltContext from a ContextBundle adhering to character budgets."""
        if not bundle.rag_context:
            return BuiltContext(
                formatted_context="No relevant document context found.",
                citations=[],
                chunk_ids=[],
            )

        context_blocks: list[str] = []
        citations: list[Citation] = []
        chunk_ids: list[uuid.UUID] = []
        current_chars = 0
        seen_chunk_ids: set[uuid.UUID] = set()

        for idx, rc in enumerate(bundle.rag_context, start=1):
            if rc.chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(rc.chunk_id)

            filename = rc.filename or "Unknown Document"
            page_str = f"Page: {rc.page_number}" if rc.page_number is not None else "Page: N/A"
            block = f"[Source {idx}]\nDocument: {filename}\n{page_str}\nContent:\n{rc.content}\n"

            if current_chars + len(block) > max_context_chars and len(context_blocks) > 0:
                break

            context_blocks.append(block)
            current_chars += len(block)
            chunk_ids.append(rc.chunk_id)

            preview = rc.content[:250] + ("..." if len(rc.content) > 250 else "")
            citations.append(
                Citation(
                    document_id=rc.document_id,
                    filename=filename,
                    page_number=rc.page_number,
                    chunk_index=rc.chunk_index,
                    content=preview,
                    relevance_score=round(rc.score, 4) if rc.score is not None else None,
                )
            )

        formatted_context = "\n---\n\n".join(context_blocks)
        return BuiltContext(
            formatted_context=formatted_context,
            citations=citations,
            chunk_ids=chunk_ids,
        )
