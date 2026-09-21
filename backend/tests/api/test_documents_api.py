"""API tests for document upload, listing, and deletion."""

import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_upload_invalid_file_extension(client: AsyncClient, user_token: str):
    file_content = b"Binary content"
    files = {"file": ("malicious.exe", io.BytesIO(file_content), "application/octet-stream")}

    response = await client.post(
        "/api/v1/documents/upload",
        files=files,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_upload_empty_file(client: AsyncClient, user_token: str):
    files = {"file": ("empty.txt", io.BytesIO(b""), "text/plain")}

    response = await client.post(
        "/api/v1/documents/upload",
        files=files,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_upload_and_list_document_success(client: AsyncClient, user_token: str):
    sample_text = (
        b"NexaRAG is an enterprise Document Intelligence and RAG platform. "
        b"It supports hybrid search with dense vector embeddings and BM25 keywords."
    )
    files = {"file": ("overview.txt", io.BytesIO(sample_text), "text/plain")}

    # 1. Upload document
    upload_res = await client.post(
        "/api/v1/documents/upload",
        files=files,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert upload_res.status_code == 201
    doc_data = upload_res.json()
    assert doc_data["filename"] == "overview.txt"
    assert doc_data["status"] == "COMPLETED"
    assert doc_data["chunk_count"] >= 1
    doc_id = doc_data["id"]

    # 2. List documents
    list_res = await client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert any(d["id"] == doc_id for d in list_data["items"])

    # 3. Get document details with chunks
    detail_res = await client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert len(detail_data["chunks"]) >= 1

    # 4. Delete document
    del_res = await client.delete(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert del_res.status_code == 200
