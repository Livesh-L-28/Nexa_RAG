"""Document processing orchestrator for text extraction, cleaning, chunking, and embedding."""

import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import DocumentNotFoundError, DocumentProcessingError
from app.core.logging import logger
from app.database.repositories.document_repo import DocumentRepository
from app.documents.chunker import Chunker
from app.documents.cleaner import TextCleaner
from app.documents.extractor import DocumentExtractor, PageContent
from app.embeddings.service import EmbeddingService

settings = get_settings()


class DocumentService:
    """Orchestrates end-to-end ingestion: validate -> extract -> clean -> chunk -> embed -> persist."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService | None = None,
        chunker: Chunker | None = None,
    ):
        self.session = session
        self.doc_repo = DocumentRepository(session)
        self.embedding_service = embedding_service or EmbeddingService()
        self.chunker = chunker or Chunker()

    async def process_document(self, document_id: uuid.UUID) -> int:
        """Execute full ingestion pipeline for a stored document. Returns total chunk count."""
        doc = await self.doc_repo.get_by_id(document_id)
        if not doc:
            raise DocumentNotFoundError(f"Document {document_id} not found.")

        file_path = Path(doc.storage_path)
        if not file_path.exists():
            await self.doc_repo.update_status(
                document_id, status="FAILED", error_message="Source file not found on disk."
            )
            raise DocumentProcessingError(f"File {file_path} not found.")

        try:
            # 1. Update status to PROCESSING
            await self.doc_repo.update_status(document_id, status="PROCESSING")
            logger.info(f"Processing document {document_id} ({doc.filename})...")

            # 2. Extract raw text with page metadata
            pages: list[PageContent] = DocumentExtractor.extract(file_path, doc.file_type)

            # 3. Clean text per page
            cleaned_pages = []
            for page in pages:
                cleaned_text = TextCleaner.clean(page.text)
                cleaned_pages.append(
                    PageContent(
                        page_number=page.page_number,
                        text=cleaned_text,
                        metadata=page.metadata,
                    )
                )

            # 4. Chunk document preserving page numbers
            chunk_items = self.chunker.chunk_document(document_id, cleaned_pages)

            if not chunk_items:
                logger.warning(f"No valid text extracted from document {document_id}")
                await self.doc_repo.update_status(document_id, status="COMPLETED", chunk_count=0)
                return 0

            # 5. Generate embeddings for chunks
            chunk_texts = [item.content for item in chunk_items]
            embeddings = self.embedding_service.embed_documents(chunk_texts)

            # 6. Prepare chunks for database insertion
            chunks_data = []
            for item, emb in zip(chunk_items, embeddings):
                chunks_data.append(
                    {
                        "document_id": document_id,
                        "chunk_index": item.chunk_index,
                        "content": item.content,
                        "page_number": item.page_number,
                        "metadata": item.metadata,
                        "embedding": emb,
                    }
                )

            # 7. Remove any stale chunks and insert new ones
            await self.doc_repo.delete_chunks_for_document(document_id)
            await self.doc_repo.add_chunks(chunks_data)

            # 8. Update status to COMPLETED
            chunk_count = len(chunks_data)
            await self.doc_repo.update_status(
                document_id, status="COMPLETED", chunk_count=chunk_count
            )
            logger.info(f"Document {document_id} successfully processed with {chunk_count} chunks.")
            return chunk_count

        except Exception as e:
            logger.error(f"Failed to process document {document_id}: {e}", exc_info=True)
            await self.doc_repo.update_status(document_id, status="FAILED", error_message=str(e))
            raise DocumentProcessingError(f"Document processing failed: {e}")
