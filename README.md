# NexaRAG — Enterprise AI Document Intelligence & RAG Platform

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB.svg)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.2+-3178C6.svg)](https://www.typescriptlang.org/)
[![pgvector](https://img.shields.io/badge/pgvector-pg16-336791.svg)](https://github.com/pgvector/pgvector)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-39%20passed-brightgreen.svg)]()

**NexaRAG** is a production-grade, modular, testable, and secure AI-powered Document Intelligence and Retrieval-Augmented Generation (RAG) platform. NexaRAG ingests heterogeneous business documents (PDF, DOCX, TXT), extracts structural text while preserving page numbers, generates dense vector representations (`sentence-transformers/all-MiniLM-L6-v2`, dim 384), performs weighted hybrid fusion retrieval (dense vector + sparse BM25Okapi), reranks candidates via a cross-encoder model (`cross-encoder/ms-marco-MiniLM-L-6-v2`), and synthesizes grounded answers with strict citation badges and real-time SSE streaming.

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    subgraph Client ["Client Layer"]
        UI["React 18 + Vite Web App (Glassmorphism Dark Mode)"]
    end

    subgraph API ["FastAPI Backend Gateway"]
        AuthRoute["Auth Routes (/api/v1/auth)"]
        DocRoute["Documents Routes (/api/v1/documents)"]
        ChatRoute["Chat & SSE Routes (/api/v1/chat)"]
        HealthRoute["Health & Probes (/health)"]
    end

    subgraph Ingestion ["Ingestion & Document Processing"]
        Extract["PyMuPDF / docx / txt Extractor"]
        Clean["Text Cleaner (NFKC, Whitespace, Zero-width)"]
        Chunk["Sentence-aware & Paragraph Chunker"]
        Embed["EmbeddingService (all-MiniLM-L6-v2, 384-d)"]
    end

    subgraph Storage ["Storage & Persistence"]
        PG[("PostgreSQL 16 + pgvector")]
        SQLite[("In-Memory SQLite (Dev & Test Fallback)")]
        Disk[("Uploads Disk Storage")]
    end

    subgraph Retrieval ["Hybrid Retrieval & Reranking"]
        VS["pgvector Cosine Search (1 - distance)"]
        BM25["In-Memory BM25Okapi Token Index"]
        Fusion["Weighted Hybrid Fusion (Alpha=0.7)"]
        Rerank["Cross-Encoder MS-MARCO Reranker"]
    end

    subgraph LLM ["Synthesis Layer"]
        PromptBuilder["Anti-Hallucination Prompt Builder"]
        ContextBuilder["Context Builder ([Source X] with Page No.)"]
        Groq["Groq Adapter (llama-3.3-70b-versatile)"]
        Gemini["Gemini Adapter (gemini-2.0-flash)"]
        MockLLM["Deterministic Grounded MockLLM (Offline)"]
    end

    UI -->|JWT Auth & REST API| API
    UI -->|Server-Sent Events (SSE)| ChatRoute

    DocRoute --> Extract --> Clean --> Chunk --> Embed
    Embed -->|Vectors & Metadata| PG
    Embed -->|Vectors & Metadata| SQLite
    DocRoute --> Disk

    ChatRoute --> Retrieval
    Retrieval --> VS
    Retrieval --> BM25
    VS --> Fusion
    BM25 --> Fusion
    Fusion --> Rerank

    Rerank --> ContextBuilder --> PromptBuilder
    PromptBuilder --> Groq & Gemini & MockLLM
    Groq & Gemini & MockLLM -->|Streamed Tokens & Citations| ChatRoute
```

---

## ✨ Key Features

1. **Heterogeneous Document Extraction**:
   - PDF ingestion with exact page number tracking using PyMuPDF (`fitz`).
   - Microsoft Word `.docx` parsing with paragraph preservation.
   - Plain text UTF-8 normalization and sanitization.
2. **Text Normalization & Smart Chunking**:
   - NFKC ligature normalization (e.g. `ﬁ` $\to$ `fi`), removal of zero-width and control characters.
   - Sentence-boundary aware chunking with sliding window character overlap, paragraph-aware splitting, and fixed-size chunking.
3. **High-Performance Hybrid Retrieval**:
   - Dense vector retrieval with 384-dimensional cosine distance via `pgvector` or in-memory cosine fallback.
   - Sparse keyword search using BM25Okapi with min-max normalized scoring.
   - Weighted alpha linear combination: $\text{Score} = \alpha \cdot S_{\text{vector}} + (1 - \alpha) \cdot S_{\text{BM25}}$.
4. **Cross-Encoder Reranking**:
   - Local CPU reranking with `cross-encoder/ms-marco-MiniLM-L-6-v2`.
   - Lazy model initialization and configurable toggle (`RERANKING_ENABLED=True/False`).
5. **Anti-Hallucination Grounding & Citations**:
   - System prompts strictly enforcing that only facts stated in the context are cited.
   - Inline citation tags `[Source 1]`, `[Source 2]` mapping directly to document name, chunk index, page number, and similarity score.
6. **Real-Time Token Streaming**:
   - Server-Sent Events (SSE) streaming tokens to the client with animated live indicators.
7. **Observability & Latency Tracking**:
   - Comprehensive telemetry tracking retrieval latency, reranker latency, and LLM synthesis latency.
8. **Modern Glassmorphic React SPA**:
   - Custom vanilla CSS design system with deep dark-mode palette, glowing violet/indigo/cyan accents.
   - Document drag-and-drop dropzone, interactive chunk inspector modal, and multi-session chat sidebar.

---

## 🚀 Quickstart Guide

### Option 1: Docker Compose (Full Stack with PostgreSQL + pgvector)

Ensure Docker and Docker Compose are running:

```bash
# 1. Clone repository
cd /Users/livesh/NexaRAG

# 2. Configure environment
cp .env.example .env

# 3. Launch database, FastAPI backend, and React frontend
docker compose up --build
```

- **Frontend Application**: [http://localhost:3000](http://localhost:3000)
- **FastAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Readiness Probe**: [http://localhost:8000/health/ready](http://localhost:8000/health/ready)

---

### Option 2: Local Development (Without Docker)

NexaRAG features an automatic SQLite fallback for instant offline development without requiring a live PostgreSQL container.

#### 1. Backend Setup

```bash
cd backend

# Create and activate Python 3.12 virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the backend server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Frontend Setup

In a new terminal window:

```bash
cd frontend

# Install npm dependencies
npm install

# Start Vite dev server with proxying
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 🧪 Test Suite & Verification

NexaRAG includes a comprehensive automated test suite covering unit, integration, and API layers with 100% pass rates.

```bash
# Activate virtual environment
source backend/.venv/bin/activate

# Run test suite
pytest backend/tests -v

# Run with test coverage report
pytest backend/tests --cov=app --cov-report=term-missing

# Lint and format checks
ruff check backend
ruff format --check backend

# Build frontend production bundle
npm --prefix frontend run build
```

---

## 📡 API Reference Overview

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Register new user account | No |
| `POST` | `/api/v1/auth/login` | Authenticate and issue JWT token | No |
| `GET` | `/api/v1/auth/me` | Fetch active user profile | Yes (Bearer) |
| `POST` | `/api/v1/documents/upload` | Ingest PDF, DOCX, TXT document | Yes (Bearer) |
| `GET` | `/api/v1/documents` | List uploaded documents | Yes (Bearer) |
| `GET` | `/api/v1/documents/{id}` | Retrieve document chunks & metadata | Yes (Bearer) |
| `DELETE` | `/api/v1/documents/{id}` | Delete document and cascade chunks | Yes (Bearer) |
| `POST` | `/api/v1/documents/{id}/process` | Re-trigger ingestion pipeline | Yes (Bearer) |
| `POST` | `/api/v1/chat` | Execute grounded RAG query | Yes (Bearer) |
| `POST` | `/api/v1/chat/stream` | Stream RAG synthesis via SSE | Yes (Bearer) |
| `GET` | `/api/v1/chat/sessions` | List user's chat sessions | Yes (Bearer) |
| `GET` | `/api/v1/chat/sessions/{id}` | Fetch session history & citations | Yes (Bearer) |
| `DELETE` | `/api/v1/chat/sessions/{id}` | Delete chat session | Yes (Bearer) |
| `GET` | `/health` | Server liveness probe | No |
| `GET` | `/health/ready` | Database & vector engine probe | No |

---

## 🔒 Security & Hardening

- **JWT Authentication & Passlib/Bcrypt**: Passwords securely hashed with bcrypt salt rounds.
- **Path Traversal Protection**: Uploaded filenames sanitized using basename isolation and alphanumeric filtering.
- **Role-Based Access Control (RBAC)**: `RoleChecker(["ADMIN"])` dependencies guarding administrative and multi-tenant actions.
- **Data Isolation**: Multi-tenant database queries strictly scoped to `user_id` preventing cross-tenant data leakage.
- **Rate Limiting**: Built-in slowapi rate limiter throttling requests by remote IP address.
