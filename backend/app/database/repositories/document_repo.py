"""Document and chunk repository for database operations."""

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Document, DocumentChunk


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_document(
        self,
        user_id: uuid.UUID,
        filename: str,
        file_type: str,
        file_size: int,
        storage_path: str,
        status: str = "PENDING",
    ) -> Document:
        doc = Document(
            user_id=user_id,
            filename=filename,
            file_type=file_type,
            file_size=file_size,
            storage_path=storage_path,
            status=status,
        )
        self.session.add(doc)
        await self.session.flush()
        await self.session.refresh(doc)
        return doc

    async def get_by_id(self, doc_id: uuid.UUID, load_chunks: bool = False) -> Document | None:
        stmt = select(Document).where(Document.id == doc_id)
        if load_chunks:
            stmt = stmt.options(selectinload(Document.chunks))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> list[Document]:
        stmt = (
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self, skip: int = 0, limit: int = 50) -> list[Document]:
        stmt = select(Document).order_by(Document.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        doc_id: uuid.UUID,
        status: str,
        chunk_count: int | None = None,
        error_message: str | None = None,
    ) -> Document | None:
        doc = await self.get_by_id(doc_id)
        if not doc:
            return None
        doc.status = status
        if chunk_count is not None:
            doc.chunk_count = chunk_count
        if error_message is not None:
            doc.error_message = error_message
        await self.session.flush()
        await self.session.refresh(doc)
        return doc

    async def delete_document(self, doc_id: uuid.UUID) -> bool:
        doc = await self.get_by_id(doc_id)
        if not doc:
            return False
        await self.session.delete(doc)
        await self.session.flush()
        return True

    async def delete_chunks_for_document(self, doc_id: uuid.UUID) -> None:
        stmt = delete(DocumentChunk).where(DocumentChunk.document_id == doc_id)
        await self.session.execute(stmt)
        await self.session.flush()

    async def add_chunks(
        self,
        chunks_data: list[dict[str, Any]],
    ) -> list[DocumentChunk]:
        """Bulk insert chunks into document_chunks table."""
        chunks = [
            DocumentChunk(
                document_id=item["document_id"],
                chunk_index=item["chunk_index"],
                content=item["content"],
                page_number=item.get("page_number"),
                metadata_=item.get("metadata", {}),
                embedding=item.get("embedding"),
            )
            for item in chunks_data
        ]
        self.session.add_all(chunks)
        await self.session.flush()
        return chunks

    async def get_chunks_by_document(
        self, doc_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[DocumentChunk]:
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == doc_id)
            .order_by(DocumentChunk.chunk_index)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_chunks_for_user(
        self, user_id: uuid.UUID, document_ids: list[uuid.UUID] | None = None
    ) -> list[DocumentChunk]:
        """Get all chunks accessible to a user, optionally filtered by document_ids."""
        stmt = (
            select(DocumentChunk)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(Document.user_id == user_id, Document.status == "COMPLETED")
        )
        if document_ids:
            stmt = stmt.where(Document.id.in_(document_ids))
        stmt = stmt.order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
