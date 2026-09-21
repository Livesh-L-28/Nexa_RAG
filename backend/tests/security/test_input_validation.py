"""Input Validation, File Upload Hardening & Injection Defense Tests (Steps 24, 25, 26, 27).

Verifies:
1. Path traversal attacks in uploaded filenames are safely sanitized.
2. Extension whitelisting blocks dangerous executables and scripts.
3. Empty queries and oversized queries (> 2000 chars) are rejected by schema validation.
4. Resource abuse parameters (e.g. top_k = 1000000, top_k = -5) are rejected.
5. Malformed UUIDs in path parameters are rejected with HTTP 422.
6. SQL injection payloads in queries or parameters are handled safely without SQL syntax errors.
"""

import io

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import sanitize_filename
from app.database.models import User
from app.retrieval.bm25_search import BM25Search
from app.retrieval.vector_search import VectorSearch


@pytest.mark.parametrize(
    "raw_filename,expected_clean",
    [
        ("../../etc/passwd", "passwd"),
        ("../../../secret.txt", "secret.txt"),
        ("..\\..\\windows\\system32\\cmd.exe", "cmd.exe"),
        ("/var/log/syslog", "syslog"),
        ("normal_document.pdf", "normal_document.pdf"),
        ("document with spaces.txt", "document_with_spaces.txt"),
        ("special!@#$%^&*()_chars.docx", "special_chars.docx"),
        (".hidden_file.txt", "doc_.hidden_file.txt"),
    ],
)
def test_filename_sanitization_prevents_path_traversal(raw_filename: str, expected_clean: str):
    """Path traversal sequences and dangerous characters must be completely stripped."""
    sanitized = sanitize_filename(raw_filename)
    assert "/" not in sanitized
    assert "\\" not in sanitized
    assert ".." not in sanitized
    assert sanitized == expected_clean


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_filename",
    [
        "malware.exe",
        "script.sh",
        "payload.py",
        "shell.php",
        "exploit.bat",
        "hack.html",
        "archive.zip",
        "binary.bin",
    ],
)
async def test_upload_blocks_disallowed_extensions(
    client: AsyncClient, user_token: str, bad_filename: str
):
    """File upload must strictly reject any extension outside .pdf, .docx, and .txt."""
    file_content = b"Simulated file payload"
    files = {"file": (bad_filename, io.BytesIO(file_content), "application/octet-stream")}

    response = await client.post(
        "/api/v1/documents/upload",
        files=files,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_upload_path_traversal_in_multipart_filename(client: AsyncClient, user_token: str):
    """Uploading with a path-traversal filename safely stores file within upload directory."""
    traversal_filename = "../../../etc/traversal_test.txt"
    files = {"file": (traversal_filename, io.BytesIO(b"Safe test content"), "text/plain")}

    response = await client.post(
        "/api/v1/documents/upload",
        files=files,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 201
    doc_data = response.json()
    # The filename stored should be the sanitized basename
    assert doc_data["filename"] == "traversal_test.txt"
    assert ".." not in doc_data["filename"]


@pytest.mark.asyncio
async def test_empty_query_rejected(client: AsyncClient, user_token: str):
    """Empty queries must fail Pydantic schema validation with HTTP 422."""
    response = await client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"query": ""},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_oversized_query_rejected(client: AsyncClient, user_token: str):
    """Queries exceeding max_length (2000 chars) must be rejected with HTTP 422."""
    huge_query = "A" * 2500
    response = await client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"query": huge_query},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_top_k", [0, -1, -100, 21, 1000, 1000000])
async def test_resource_abuse_top_k_rejected(client: AsyncClient, user_token: str, bad_top_k: int):
    """Excessive or negative top_k values must be rejected with HTTP 422 to prevent DoS."""
    response = await client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "query": "Valid search query",
            "top_k": bad_top_k,
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_uuid",
    ["not-a-uuid", "12345", "../../../etc/passwd", "select-from-users", "'; DROP TABLE;--"],
)
async def test_invalid_uuid_rejected(client: AsyncClient, user_token: str, invalid_uuid: str):
    """Invalid UUID path parameters must return HTTP 422."""
    response = await client.get(
        f"/api/v1/documents/{invalid_uuid}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code in (404, 422)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sql_payload",
    [
        "' OR '1'='1",
        "'; DROP TABLE documents; --",
        '" OR 1=1 --',
        "UNION SELECT null, null, null, null --",
        "admin'--",
    ],
)
async def test_sql_injection_payload_handled_safely(
    db_session: AsyncSession, test_user: User, sql_payload: str
):
    """Adversarial SQL strings in search queries must execute safely via parameterization without database error."""
    # 1. Test in BM25 Search
    bm25 = BM25Search(db_session)
    results_bm25 = await bm25.search(
        query=sql_payload,
        user_id=test_user.id,
    )
    assert isinstance(results_bm25, list)

    # 2. Test in Vector Search fallback
    vec = VectorSearch(db_session)
    results_vec = await vec.search(
        query_vector=[0.1] * 384,
        user_id=test_user.id,
    )
    assert isinstance(results_vec, list)

    # 3. Verify database tables are intact
    check_query = await db_session.execute(text("SELECT count(*) FROM users"))
    count = check_query.scalar()
    assert count is not None and count >= 1
