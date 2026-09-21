#!/usr/bin/env python3
"""
Automated Deployment Verification & Smoke Test Script for NexaRAG.
Tests the running Docker Compose stack (Frontend, Backend, PostgreSQL + pgvector).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import uuid

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")


def print_step(step_num: int, title: str) -> None:
    print(f"\n[STEP {step_num}] {title}...")


def assert_true(condition: bool, msg: str) -> None:
    if not condition:
        print(f"  ❌ FAILED: {msg}")
        sys.exit(1)
    print(f"  ✅ PASSED: {msg}")


def http_get(
    url: str, headers: dict | None = None, timeout: int = 15
) -> tuple[int, dict | str]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(data)
            except json.JSONDecodeError:
                return resp.status, data
    except urllib.error.HTTPError as e:
        data = e.read().decode("utf-8")
        try:
            return e.code, json.loads(data)
        except json.JSONDecodeError:
            return e.code, data


def http_post(
    url: str,
    body: dict | None = None,
    headers: dict | None = None,
    timeout: int = 15,
) -> tuple[int, dict | str]:
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    payload = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=payload, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(data)
            except json.JSONDecodeError:
                return resp.status, data
    except urllib.error.HTTPError as e:
        data = e.read().decode("utf-8")
        try:
            return e.code, json.loads(data)
        except json.JSONDecodeError:
            return e.code, data


def http_post_multipart(
    url: str, filename: str, content: bytes, headers: dict | None = None
) -> tuple[int, dict | str]:
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    hdrs = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    if headers:
        hdrs.update(headers)

    body = (
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: text/plain\r\n\r\n"
        ).encode()
        + content
        + f"\r\n--{boundary}--\r\n".encode()
    )

    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(data)
            except json.JSONDecodeError:
                return resp.status, data
    except urllib.error.HTTPError as e:
        data = e.read().decode("utf-8")
        try:
            return e.code, json.loads(data)
        except json.JSONDecodeError:
            return e.code, data


def main() -> None:
    print("=" * 70)
    print("  NexaRAG Containerized Deployment Smoke Test Suite")
    print("=" * 70)

    # 1. Backend Liveness
    print_step(1, "Testing Backend Liveness Probe (/health)")
    status, res = http_get(f"{BACKEND_URL}/health")
    assert_true(status == 200, f"Backend liveness returned status {status}")
    assert_true(
        isinstance(res, dict) and res.get("status") == "healthy",
        "Backend reports healthy status",
    )

    # 2. Database & pgvector Readiness
    print_step(2, "Testing Database Connection & pgvector Extension (/health/ready)")
    status, res = http_get(f"{BACKEND_URL}/health/ready")
    assert_true(status == 200, f"Readiness probe returned status {status}")
    assert_true(
        isinstance(res, dict) and res.get("status") == "ready", "System is marked ready"
    )
    db_check = res.get("checks", {}).get("database", {})
    assert_true(
        db_check.get("healthy") is True, f"Database health check passed: {db_check}"
    )
    assert_true(
        db_check.get("pgvector") == "installed",
        "pgvector extension is installed and active",
    )

    # 3. Frontend Static Serving
    print_step(3, "Testing Frontend Static Assets Serving (Port 3000)")
    status, res = http_get(f"{FRONTEND_URL}/")
    assert_true(status == 200, f"Frontend returned HTTP {status}")
    assert_true(
        "<title>NexaRAG" in str(res) or '<div id="root">' in str(res),
        "Frontend HTML shell served",
    )

    # 4. Frontend Nginx API Proxying
    print_step(4, "Testing Frontend Reverse Proxy Routing to Backend (/api & /health)")
    status, res = http_get(f"{FRONTEND_URL}/health")
    assert_true(status == 200, f"Nginx /health proxy returned HTTP {status}")

    # 5. User Registration & Authentication
    test_email = f"deploy_test_{uuid.uuid4().hex[:8]}@example.com"
    test_password = "SecurePassword123!"
    print_step(5, f"Testing User Registration & JWT Issuance ({test_email})")

    # Register
    reg_status, _ = http_post(
        f"{BACKEND_URL}/api/v1/auth/register",
        {"email": test_email, "password": test_password, "role": "USER"},
    )
    assert_true(reg_status in [200, 201], f"Registration returned HTTP {reg_status}")

    # Login
    login_status, login_res = http_post(
        f"{BACKEND_URL}/api/v1/auth/login",
        {"email": test_email, "password": test_password},
    )
    assert_true(login_status == 200, f"Login returned HTTP {login_status}")
    assert_true(isinstance(login_res, dict), "Login returned JSON object")
    token = login_res.get("access_token")
    assert_true(bool(token), "Received valid JWT access token")
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Verify /auth/me
    me_status, me_res = http_get(f"{BACKEND_URL}/api/v1/auth/me", headers=auth_headers)
    assert_true(me_status == 200, f"/auth/me returned HTTP {me_status}")
    assert_true(
        isinstance(me_res, dict) and me_res.get("email") == test_email,
        "Identity confirmed via JWT token",
    )

    # 6. Document Upload & Processing
    print_step(6, "Testing Document Upload & Hybrid Ingestion Pipeline")
    doc_content = (
        b"NexaRAG Deployment Architecture Verification Document.\n"
        b"Project Quantum is an advanced enterprise AI document processing initiative.\n"
        b"The primary database is PostgreSQL 16 with the pgvector extension for dense similarity search.\n"
        b"The retrieval pipeline uses BM25Okapi for keyword matching and cross-encoder for reranking.\n"
        b"All secrets are strictly environment-managed without hardcoded API keys."
    )

    up_status, up_res = http_post_multipart(
        f"{BACKEND_URL}/api/v1/documents/upload",
        filename="deployment_verification.txt",
        content=doc_content,
        headers=auth_headers,
    )
    assert_true(up_status in [200, 201], f"Document upload returned HTTP {up_status}")
    assert_true(isinstance(up_res, dict), "Upload returned JSON object")
    doc_id = up_res.get("id")
    assert_true(bool(doc_id), f"Document assigned UUID: {doc_id}")
    assert_true(
        up_res.get("chunk_count", 0) > 0,
        f"Document chunked: {up_res.get('chunk_count')} chunks",
    )

    # 7. Grounded RAG Query Execution
    print_step(7, "Testing Grounded RAG Query & Context Orchestrator")
    query_payload = {
        "query": "What database and extension does Project Quantum use according to the document?",
        "stream": False,
    }
    chat_status, chat_res = http_post(
        f"{BACKEND_URL}/api/v1/chat",
        body=query_payload,
        headers=auth_headers,
    )
    assert_true(chat_status == 200, f"Chat query returned HTTP {chat_status}")
    assert_true(isinstance(chat_res, dict), "Chat returned JSON response")
    answer = chat_res.get("answer", "")
    assert_true(len(answer) > 0, "Received generated grounded answer")
    sources = chat_res.get("sources", [])
    assert_true(
        len(sources) > 0, f"Response includes citations ({len(sources)} sources)"
    )

    # 8. Real-time SSE Token Streaming
    print_step(8, "Testing Real-time SSE Chat Streaming via Nginx Proxy")
    stream_req = urllib.request.Request(
        f"{FRONTEND_URL}/api/v1/chat/stream",
        data=json.dumps({"query": "Explain Project Quantum", "stream": True}).encode(
            "utf-8"
        ),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )

    received_types = []
    with urllib.request.urlopen(stream_req, timeout=30) as stream_resp:
        assert_true(
            stream_resp.status == 200,
            f"SSE endpoint returned HTTP {stream_resp.status}",
        )
        buffer = ""
        while True:
            chunk = stream_resp.read(256)
            if not chunk:
                break
            buffer += chunk.decode("utf-8")
            lines = buffer.split("\n")
            buffer = lines.pop()
            for line in lines:
                line = line.strip()
                if line.startswith("data: "):
                    try:
                        event = json.loads(line[6:])
                        received_types.append(event.get("type"))
                    except json.JSONDecodeError:
                        pass

    assert_true("init" in received_types, "Received SSE 'init' event")
    assert_true("token" in received_types, "Received SSE 'token' events")
    assert_true("done" in received_types, "Received SSE 'done' event with metadata")

    print("\n" + "=" * 70)
    print("  🎉 ALL 8 CONTAINER DEPLOYMENT SMOKE TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()
