"""Pydantic schemas for documents and chunks."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChunkResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    page_number: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DocumentResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    filename: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(DocumentResponse):
    chunks: list[ChunkResponse] = []


class DocumentListResponse(BaseModel):
    total: int
    items: list[DocumentResponse]


class ProcessDocumentResponse(BaseModel):
    document_id: uuid.UUID
    status: str
    chunk_count: int
    message: str
