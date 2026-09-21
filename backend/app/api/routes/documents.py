"""Document ingestion, retrieval, chunk inspection, and deletion endpoints."""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.core.config import get_settings
from app.core.exceptions import (
    AuthorizationException,
    DocumentNotFoundError,
    FileValidationException,
)
from app.core.logging import logger
from app.database.models import User, UserRole
from app.database.repositories.document_repo import DocumentRepository
from app.documents.service import DocumentService
from app.schemas.documents import (
    ChunkResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentResponse,
    ProcessDocumentResponse,
)

router = APIRouter(prefix="/documents", tags=["Documents"])
settings = get_settings()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a new document (PDF, DOCX, TXT) and trigger RAG ingestion",
)
async def upload_document(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    # 1. Validate file extension
    filename = Path(file.filename or "unknown").name  # Sanitize against path traversal
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationException(
            f"Unsupported file type '{ext}'. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # 2. Read content and validate file size
    contents = await file.read()
    file_size = len(contents)
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        raise FileValidationException(
            f"File size exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB"
        )
    if file_size == 0:
        raise FileValidationException("Uploaded file is empty.")

    # 3. Save file safely to storage directory
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_uuid = uuid.uuid4()
    storage_filename = f"{file_uuid}{ext}"
    storage_path = upload_dir / storage_filename

    with open(storage_path, "wb") as f:
        f.write(contents)

    # 4. Create document record in database
    doc_repo = DocumentRepository(session)
    document = await doc_repo.create_document(
        user_id=current_user.id,
        filename=filename,
        file_type=ext.lstrip("."),
        file_size=file_size,
        storage_path=str(storage_path),
        status="PENDING",
    )
    await session.commit()

    # 5. Process document ingestion (extract, clean, chunk, embed)
    doc_service = DocumentService(session)
    try:
        await doc_service.process_document(document.id)
        await session.commit()
        await session.refresh(document)
    except Exception as e:
        logger.error(f"Error processing uploaded document {document.id}: {e}")
        await session.refresh(document)

    return DocumentResponse.model_validate(document)


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List uploaded documents for the current user",
)
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentListResponse:
    doc_repo = DocumentRepository(session)
    if current_user.role == UserRole.ADMIN:
        docs = await doc_repo.list_all(skip=skip, limit=limit)
    else:
        docs = await doc_repo.list_by_user(user_id=current_user.id, skip=skip, limit=limit)

    return DocumentListResponse(
        total=len(docs),
        items=[DocumentResponse.model_validate(d) for d in docs],
    )


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Retrieve document metadata and extracted chunks",
)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentDetailResponse:
    doc_repo = DocumentRepository(session)
    doc = await doc_repo.get_by_id(document_id, load_chunks=True)
    if not doc:
        raise DocumentNotFoundError(f"Document with ID {document_id} not found")

    if doc.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise AuthorizationException("You do not have permission to view this document")

    chunks = await doc_repo.get_chunks_by_document(document_id)
    return DocumentDetailResponse(
        id=doc.id,
        user_id=doc.user_id,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        status=doc.status,
        chunk_count=doc.chunk_count,
        error_message=doc.error_message,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        chunks=[
            ChunkResponse(
                id=c.id,
                document_id=c.document_id,
                chunk_index=c.chunk_index,
                content=c.content,
                page_number=c.page_number,
                metadata=c.metadata_ or {},
                created_at=c.created_at,
            )
            for c in chunks
        ],
    )


@router.delete(
    "/{document_id}",
    summary="Delete a document and all associated chunk embeddings",
)
async def delete_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    doc_repo = DocumentRepository(session)
    doc = await doc_repo.get_by_id(document_id)
    if not doc:
        raise DocumentNotFoundError(f"Document with ID {document_id} not found")

    if doc.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise AuthorizationException("You do not have permission to delete this document")

    # Remove file from disk
    if doc.storage_path and os.path.exists(doc.storage_path):
        try:
            os.remove(doc.storage_path)
        except OSError as e:
            logger.warning(f"Could not remove file {doc.storage_path}: {e}")

    await doc_repo.delete_document(document_id)
    await session.commit()

    return {"message": "Document and associated chunks deleted successfully"}


@router.post(
    "/{document_id}/process",
    response_model=ProcessDocumentResponse,
    summary="Re-trigger ingestion and embedding for an existing document",
)
async def reprocess_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProcessDocumentResponse:
    doc_repo = DocumentRepository(session)
    doc = await doc_repo.get_by_id(document_id)
    if not doc:
        raise DocumentNotFoundError(f"Document with ID {document_id} not found")

    if doc.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise AuthorizationException("You do not have permission to process this document")

    doc_service = DocumentService(session)
    chunk_count = await doc_service.process_document(document_id)
    await session.commit()

    return ProcessDocumentResponse(
        document_id=document_id,
        status="COMPLETED",
        chunk_count=chunk_count,
        message=f"Successfully processed and generated {chunk_count} chunks.",
    )
