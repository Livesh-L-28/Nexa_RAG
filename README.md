# NexaRAG — Enterprise Document Intelligence & Hybrid RAG Platform

[![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18.2-61DAFB.svg?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.2+-3178C6.svg?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![pgvector](https://img.shields.io/badge/pgvector-pg16-336791.svg?style=flat&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![NeMo Guardrails](https://img.shields.io/badge/NeMo_Guardrails-0.8+-76B900.svg?style=flat&logo=nvidia&logoColor=white)](https://github.com/NVIDIA/NeMo-Guardrails)
[![Tests Passed](https://img.shields.io/badge/tests-321%20passed-brightgreen.svg?style=flat)]()
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg?style=flat)](https://github.com/astral-sh/ruff)

**NexaRAG** is a production-grade, enterprise-ready Document Intelligence and Retrieval-Augmented Generation (RAG) platform. It merges **RAG** (Retrieval-Augmented Generation), **CAG** (Cache-Augmented Generation), and **MAG** (Memory-Augmented Generation) behind a deterministic **7-tier context fusion layer**, namespaced sub-millisecond knowledge caching, multi-signal memory ranking (recency decay, lexical relevance, importance weights), and a **3-tier NVIDIA NeMo Guardrails** security pipeline with fail-closed enforcement against prompt injection, cross-tenant data leakage, and secret exfiltration.

The user interface is built on a **Linear- and Notion-inspired design system** with high-density tabular data, native dark and light themes, keyboard shortcuts (`?`), command palette (`⌘K`), citations inspector, and real-time Server-Sent Events (SSE) token streaming.

---

## 📑 Table of Contents

1. [Architecture Overview](#-architecture-overview)
2. [Core Capabilities](#-core-capabilities)
3. [User Roles & RBAC (Admin vs User)](#-user-roles--rbac-admin-vs-user)
4. [Quickstart Guide](#-quickstart-guide)
   - [Option A: Local Development (Fastest Offline Setup)](#option-a-local-development-fastest-offline-setup)
   - [Option B: Full-Stack Docker Compose & Multi-Device Setup](#option-b-full-stack-docker-compose--multi-device-setup)
   - [Option C: Exposing via Cloudflare Tunnel](#option-c-exposing-via-cloudflare-tunnel-public-url)
5. [Hosting & Cloud Deployment](#-hosting--cloud-deployment)
   - [1. Linux VPS (AWS EC2 / DigitalOcean / Hetzner)](#1-linux-vps-aws-ec2--digitalocean--hetzner)
   - [2. Managed PaaS (Render / Railway / Supabase)](#2-managed-paas-render--railway--supabase)
   - [3. Enterprise AWS Architecture (ECS + RDS + S3)](#3-enterprise-aws-architecture-ecs--rds--s3)
6. [Configuration & Environment Variables](#-configuration--environment-variables)
7. [API Reference](#-api-reference)
8. [Debugging & Troubleshooting Guide](#-debugging--troubleshooting-guide)
9. [Testing & Quality Assurance](#-testing--quality-assurance)

---

## 🏛️ Architecture Overview

```
                                  USER INTERFACE (Linear + Notion Aesthetic)
                      ┌─────────────────────────────────────────────────────────────┐
                      │ React 18 + TypeScript + Vite                                │
                      │ • 3-Panel Chat & Citations Inspector                        │
                      │ • Command Palette (⌘K) & Shortcuts Modal (?)                 │
                      │ • Dark / Light / System Themes (Zinc/Slate Palette)         │
                      │ • Real-Time Server-Sent Events (SSE) Stream Reader          │
                      └──────────────────────────────┬──────────────────────────────┘
                                                     │ HTTP / SSE / JWT Bearer
                                                     ▼
                                        FASTAPI APPLICATION GATEWAY
                      ┌─────────────────────────────────────────────────────────────┐
                      │ • HS256 Stateless JWT Authentication (Access / Expiry)      │
                      │ • RoleChecker Authorization (ADMIN vs USER)                 │
                      │ • SlowAPI Distributed Rate Limiter                          │
                      │ • Strict Tenant & User ID Scoping                           │
                      └──────────────────────────────┬──────────────────────────────┘
                                                     │
         ┌───────────────────────────────────────────┼───────────────────────────────────────────┐
         ▼                                           ▼                                           ▼
 ┌───────────────┐                          ┌─────────────────┐                         ┌─────────────────┐
 │   INGESTION   │                          │ 3-TIER SECURITY │                         │ ORCHESTRATION   │
 │ • PyMuPDF     │                          │ NVIDIA NeMo     │                         │ & ROUTING       │
 │ • python-docx │                          │ • Tier 1: Input │                         │ Dynamic Router: │
 │ • Clean/NFKC  │                          │ • Tier 2: Retr. │                         │ RAG, CAG, MAG   │
 │ • Smart Chunker│                         │ • Tier 3: Output│                         │ 6,000-Token Cap │
 │ • 384-d Embed │                          │ Fail-Closed S116│                         │ 7-Tier Fusion   │
 └───────┬───────┘                          └────────┬────────┘                         └────────┬────────┘
         │                                           │                                           │
         ▼                                           ▼                                           ▼
 ┌───────────────┐                          ┌─────────────────┐                         ┌─────────────────┐
 │ HYBRID SEARCH │                          │ KNOWLEDGE CACHE │                         │ MEMORY (MAG)    │
 │ • pgvector    │                          │ • CAG Manager   │                         │ • Recency Decay │
 │   Cosine 384-d│                          │ • Namespaced    │                         │ • Importance    │
 │ • BM25Okapi   │                          │ • Sub-ms Lookup │                         │ • BM25 Signal   │
 │ • Cross-Enc.  │                          │ • Invalidation  │                         │ • Tenant Memory │
 │   MS-MARCO    │                          │   & Preload     │                         │   Purging       │
 └───────┬───────┘                          └────────┬────────┘                         └────────┬────────┘
         │                                           │                                           │
         └───────────────────────────────────────────┴───────────────────────────────────────────┘
                                                     │
                                                     ▼
                                        LLM SYNTHESIS & INFERENCE
                      ┌─────────────────────────────────────────────────────────────┐
                      │ Multi-Provider Abstraction:                                 │
                      │ • Google Gemini (gemini-2.5-flash)                          │
                      │ • Groq Cloud (llama-3.3-70b-versatile)                      │
                      │ • Grounded Deterministic MockLLM (Offline Fallback)         │
                      │ • Anti-Hallucination Prompting & Strict Citation Generation │
                      └─────────────────────────────────────────────────────────────┘
```

---

## ⚡ Core Capabilities

### 1. Hybrid Retrieval & Cross-Encoder Reranking
- **Dense Vector Search**: Generates 384-dimensional embeddings via `sentence-transformers/all-MiniLM-L6-v2` stored in PostgreSQL with `pgvector` HNSW indexing.
- **Sparse BM25 Search**: In-memory tokenized `BM25Okapi` index for precise keyword and code/symbol recall.
- **Weighted Reciprocal Fusion**: Blends dense and sparse signals:
  $$\text{Score} = \alpha \cdot S_{\text{vector}} + (1 - \alpha) \cdot S_{\text{BM25}} \quad (\alpha = 0.7)$$
- **Cross-Encoder Reranking**: Re-scores top candidate passages using `cross-encoder/ms-marco-MiniLM-L-6-v2` to eliminate false positives before prompt insertion.

### 2. Multi-Strategy Dynamic Query Routing
Before hitting the vector database or LLM, each query is analyzed by the Query Router to classify intent across 6 deterministic routes:
1. `RAG`: Unseen factual documents required.
2. `CAG`: High-confidence cached knowledge match (< 1ms).
3. `MAG`: User personal context, conversation history, or preference retrieval.
4. `RAG + CAG`: Partial cache hit supplemented by live document retrieval.
5. `RAG + MAG`: Document search contextualized with user identity and past interactions.
6. `RAG + CAG + MAG`: Full 3-engine synthesis for complex analytical queries.

### 3. Context Orchestration & 6,000-Token Budgeting
Context is assembled using a strict 7-tier priority hierarchy enforced under a 6,000-token hard budget ceiling:
* **Tier 1**: System safety instructions and ground rules.
* **Tier 2**: Security invariants and anti-exfiltration filters.
* **Tier 3**: High-priority user memory (MAG).
* **Tier 4**: Reranked document chunks (RAG) with page and chunk metadata.
* **Tier 5**: Pre-computed cached context (CAG).
* **Tier 6**: Recent conversation history.
* **Tier 7**: General workspace context (truncated gracefully when ceiling is reached).

### 4. 3-Tier NVIDIA NeMo Guardrails
Enforces 16 platform security invariants (S1–S16) across the entire generation lifecycle:
* **Input Guardrail**: Detects and aborts prompt injections, jailbreaks, and roleplay bypasses.
* **Retrieval Guardrail**: Validates retrieved passages against unauthorized cross-tenant leakage.
* **Output Guardrail**: Sanitizes output tokens to prevent system prompt leakage and secret exfiltration.

---

## 👥 User Roles & RBAC (Admin vs User)

NexaRAG implements strict Role-Based Access Control:

```
                            PLATFORM USER ROLES
         ┌─────────────────────────────────────────────────────────┐
         │                                                         │
         ▼                                                         ▼
   STANDARD USER (Analyst)                         PLATFORM ADMIN
• Document Ingestion (PDF/DOCX/TXT)      • Everything available to USER
• Hybrid Search & Real-time Chat         • User Registry & Role Promotion/Demotion
• Strict Citation Verification           • 3-Tier NeMo Guardrails Center
• Personal Memory (MAG) Management       • Infrastructure Liveness/Readiness Probes
• Collection Workspace Scoping           • Tamper-Evident Corporate Audit Logs
• Explainable Retrieval Diagnostics      • System-Wide Cache Invalidation & Preload
```

### Pre-Seeded Default Accounts

| Email | Password | Role | Operational Purpose |
|---|---|:---:|---|
| **`admin@nexarag.ai`** | `adminpassword123` | **`ADMIN`** | Platform Administrator with full governance access |
| **`demo@nexarag.ai`** | `password123` | **`USER`** | Knowledge Analyst / Researcher account |

*(Users can also self-register with any email via the "Create Account" tab on the login screen; new registrations receive the `USER` role by default).*

---

## 🚀 Quickstart Guide

### Option A: Local Development (Fastest Offline Setup)

NexaRAG includes an automatic SQLite and deterministic in-memory vector fallback, allowing instant execution without requiring Docker or a local PostgreSQL instance.

#### 1. Start the Backend API Server

```bash
# Navigate to backend directory
cd backend

# Create and activate Python 3.12 virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt

# Start FastAPI server on port 8000
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

*The server will initialize the database, verify default accounts, and listen at `http://127.0.0.1:8000`.*

#### 2. Start the Frontend Dev Server

Open a second terminal window:

```bash
# Navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start Vite development server
npm run dev
```

*Open **`http://localhost:5173`** in your browser. Vite proxies `/api` and `/health` requests directly to `http://127.0.0.1:8000`.*

---

### Option B: Full-Stack Docker Compose & Multi-Device Setup

Run the entire production stack (PostgreSQL 16 with `pgvector`, FastAPI backend, and Nginx frontend). Pre-built production images are hosted publicly on **GitHub Container Registry (GHCR)**.

#### 🐳 Container Stack Specifications

| Service / Container | Image / Source | Port Mapping | Storage & Volumes | Role & Internal Configuration |
|---|---|---|---|---|
| **`nexarag_db`** | `pgvector/pgvector:pg16` | `5432` *(internal)* | `pgdata:/var/lib/postgresql/data` | PostgreSQL 16 relational database with native 384-d vector embeddings index (`pgvector` HNSW). Health checked via `pg_isready`. |
| **`nexarag_backend`** | `ghcr.io/livesh-l-28/nexa-rag-backend:latest` *(or `./backend`)* | `8000:8000` | `./data/uploads:/app/data/uploads` | FastAPI API gateway, hybrid search (pgvector + BM25Okapi), Cross-Encoder reranker, 3-tier NeMo guardrails, and context orchestrator. Runs as non-root `appuser` (UID 1000). |
| **`nexarag_frontend`** | `ghcr.io/livesh-l-28/nexa-rag-frontend:latest` *(or `./frontend`)* | `${FRONTEND_PORT:-3001}:80` | None *(Stateless)* | Nginx Alpine serving compiled React 18 SPA. Configured with `proxy_buffering off;` and `proxy_read_timeout 600s;` for real-time SSE token streaming and 50MB file uploads. |

**Startup Dependency Sequence**:
`nexarag_db` (becomes `healthy`) ➔ `nexarag_backend` (initializes database schemas, seeds accounts, reaches `healthy`) ➔ `nexarag_frontend` (starts proxying).

---

#### 💻 Step-by-Step Installation on Another Device (Laptop / Desktop / VPS)

Follow these steps to deploy NexaRAG onto a fresh laptop or another computer without needing Python, Node.js, or local compilers installed:

##### 1. Prerequisites on the Target Device
- **Docker Engine**: Version 20.10.0+ (or [Docker Desktop](https://www.docker.com/products/docker-desktop/) on macOS / Windows with WSL2).
- **Docker Compose**: Version 2.0.0+ (included with Docker Desktop or `docker compose` plugin on Linux).
- **Hardware Specs**: Minimum 4 GB RAM (8 GB recommended for embeddings & reranking inference); 10 GB available disk space.

##### 2. Obtain Project Files on the Target Device
Open a terminal on the new machine:
```bash
# Clone the repository
git clone https://github.com/Livesh-L-28/Nexa_RAG.git
cd Nexa_RAG
```
*(Tip: If transferring to an air-gapped or minimal system, you only need `docker-compose.yml` and `.env.example` from the repository).*

##### 3. Configure Environment Variables (`.env`)
Create your `.env` configuration from the provided template:
```bash
cp .env.example .env
```
Open `.env` in any text editor. If you plan to use cloud LLMs, add your API keys:
```env
# Optional: Set to 'gemini' or 'groq' (defaults to 'mock' for fully offline execution)
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIzaSy...

# Or for Groq Cloud:
# LLM_PROVIDER=groq
# GROQ_API_KEY=gsk_...
```

##### 4. Pull Pre-Built GHCR Images
Pull the pre-compiled container images directly from GitHub Container Registry:
```bash
docker compose pull
```
*(Alternatively, you can pull each image manually:)*
```bash
docker pull ghcr.io/livesh-l-28/nexa-rag-backend:latest
docker pull ghcr.io/livesh-l-28/nexa-rag-frontend:latest
docker pull pgvector/pgvector:pg16
```

##### 5. Launch the Application Stack
Start all three containers in detached (background) mode:
```bash
docker compose up -d
```

##### 6. Verify Deployment Health
Check that all services started and passed their automated health probes:
```bash
docker compose ps
```
You should see all three services reporting `healthy` or `running`:
- `nexarag_db` (healthy)
- `nexarag_backend` (healthy)
- `nexarag_frontend` (running)

To verify the backend health probe directly:
```bash
curl http://localhost:8000/health
```

To tail live server logs:
```bash
docker compose logs -f backend
```

##### 7. Access NexaRAG in Your Browser
- **Web User Interface**: Open **`http://localhost:3001`**
- **Backend API & Swagger Docs**: Open **`http://localhost:8000/docs`**

**Accessing from other devices on the same Local Network (LAN)**:
If you want other phones, tablets, or computers on your local Wi-Fi/LAN to access NexaRAG, find the host machine's local IP (e.g. via `ipconfig` on Windows or `ip a` / `ifconfig` on Linux/Mac) and open:
```text
http://<HOST_LOCAL_IP>:3001
```
*(Ensure incoming connections on port 3001 are permitted through your firewall).*

**Default Pre-Seeded Accounts**:
| Role | Email | Password | Access Level |
|---|---|---|---|
| **Admin** | `admin@nexarag.ai` | `adminpassword123` | Full governance, NeMo guardrails, user registry, system analytics |
| **Analyst** | `demo@nexarag.ai` | `password123` | Document ingestion, hybrid search, citations inspector, personal memory |

---

#### 🔄 Container Maintenance & Lifecycle

- **Update to the Latest Images on Target Device**:
  ```bash
  docker compose pull
  docker compose up -d --remove-orphans
  ```
- **Stop Containers Gracefully** *(Preserves database and uploaded files)*:
  ```bash
  docker compose stop
  ```
- **Resume Containers**:
  ```bash
  docker compose start
  ```
- **Tear Down Containers & Networks** *(Preserves database volume)*:
  ```bash
  docker compose down
  ```
- **Clean Database Reset / Complete Wipe** *(Destructive — drops all indexed data and users)*:
  ```bash
  docker compose down -v
  ```

---

#### 🛠️ Developer Alternative: Building Locally from Source
If you are developing custom code on backend Python files or frontend React components, rebuild the container images from local source code instead of pulling from GHCR:
```bash
docker compose up -d --build
```

---

### Option C: Exposing via Cloudflare Tunnel (Public URL)

If you want to share your running NexaRAG instance publicly or test on mobile/remote devices without port forwarding:

#### If running via Docker Compose (Port 3001):
```bash
cloudflared tunnel --url http://localhost:3001
```

#### If running via Vite Dev Server (Port 5173):
```bash
cloudflared tunnel --url http://localhost:5173
```

Cloudflare will output a public HTTPS URL (e.g., `https://random-words.trycloudflare.com`). Anyone with the URL can access your live application with full HTTPS and SSE streaming supported!

---

## 🌐 Hosting & Cloud Deployment

### 1. Linux VPS (AWS EC2 / DigitalOcean / Hetzner)

1. Provision an Ubuntu 22.04 / 24.04 server (minimum 4GB RAM, e.g. AWS `t3.medium` or a $24/mo DigitalOcean Droplet).
2. Install Docker and Docker Compose:
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER
   ```
3. Clone and configure:
   ```bash
   git clone https://github.com/Livesh-L-28/Nexa_RAG.git
   cd Nexa_RAG
   cp .env.example .env
   # Edit .env with your production SECRET_KEY and LLM keys
   docker compose up -d --build
   ```
4. Configure HTTPS using **Caddy** (automatic SSL):
   ```caddyfile
   rag.yourdomain.com {
       reverse_proxy localhost:3001
   }
   ```

---

### 2. Managed PaaS (Render / Railway / Supabase)

- **Database**: Spin up a PostgreSQL 16 database on **Supabase**, **Neon**, or **Railway** (all support `pgvector` natively). Copy the connection URI into `DATABASE_URL`.
- **Backend**: Connect your GitHub repository to **Render** or **Railway**. Choose `Docker` environment, pointing to `backend/Dockerfile`. Add your environment variables (`DATABASE_URL`, `SECRET_KEY`, `GEMINI_API_KEY`, etc.).
- **Frontend**: Deploy `frontend/` on **Vercel** or **Cloudflare Pages**. Set rewrite rules in `vercel.json` or configure the backend URL proxy.

---

### 3. Enterprise AWS Architecture (ECS + RDS + S3)

```
[ Route 53 ] ──► [ CloudFront CDN ] ──► [ ALB (Application Load Balancer) ]
                                                │
                                       ┌────────┴────────┐
                                       ▼                 ▼
                              [ ECS Fargate ]    [ ECS Fargate ]
                              (NexaRAG Backend)  (Nginx Frontend)
                                       │
                        ┌──────────────┴──────────────┐
                        ▼                             ▼
              [ AWS RDS PG16 ]                  [ AWS S3 ]
                (pgvector)                   (Document Store)
```

1. **Database:** AWS RDS PostgreSQL 16 with `CREATE EXTENSION vector;`.
2. **Compute:** ECS Fargate tasks running `backend/Dockerfile`.
3. **Storage:** AWS S3 for document ingestion persistence.
4. **Secrets:** AWS Secrets Manager for LLM API keys and JWT signing secrets.

---

## ⚙️ Configuration & Environment Variables

Create a `.env` file in the root directory:

| Variable | Default | Production Recommendation | Description |
|---|---|---|---|
| `ENVIRONMENT` | `development` | `production` | Runtime mode (`development` / `production`) |
| `SECRET_KEY` | `nexarag-insecure-dev...` | `openssl rand -hex 32` | 32+ character key for HS256 JWT signing |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | `1440` (24h) | JWT validity duration |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Production PostgreSQL URI | Async SQLAlchemy database URL |
| `DATABASE_SYNC_URL` | `postgresql://...` | Production PostgreSQL URI | Sync SQLAlchemy URL for Alembic migrations |
| `LLM_PROVIDER` | `mock` | `gemini` or `groq` | Inference backend (`gemini`, `groq`, `mock`) |
| `GEMINI_API_KEY` | `""` | `AIzaSy...` | Google Gemini API key |
| `GROQ_API_KEY` | `""` | `gsk_...` | Groq Cloud API key |
| `LLM_MODEL` | `gemini-2.5-flash` | `gemini-2.5-flash` | Primary model identifier |
| `EMBEDDING_MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | Same | HuggingFace embedding model (dim 384) |
| `MAX_UPLOAD_SIZE_MB` | `25` | `25` | Document upload size ceiling |
| `DOCUMENTS_ADMIN_ONLY` | `false` | `false` | When true, only Admins can upload docs |
| `CORS_ORIGINS` | `["http://localhost:5173", ...]` | `["https://rag.yourdomain.com"]` | Authorized client origins |

---

## 📡 API Reference

### Authentication & Users
- `POST /api/v1/auth/register` — Register a new account (`USER` role assigned).
- `POST /api/v1/auth/login` — Authenticate with email/password; returns JWT access token.
- `GET /api/v1/auth/me` — Retrieve active profile and granted permissions.

### Documents & Ingestion
- `POST /api/v1/documents/upload` — Ingest PDF, DOCX, or TXT (multi-part upload, max 25MB).
- `GET /api/v1/documents` — List uploaded documents with status and chunk counts.
- `GET /api/v1/documents/{id}` — Inspect document metadata and chunk vector distributions.
- `POST /api/v1/documents/{id}/process` — Trigger document reprocessing and re-chunking.
- `DELETE /api/v1/documents/{id}` — Delete document and cascade chunks from vector store.

### Chat & SSE Stream
- `POST /api/v1/chat` — Synchronous grounded query execution.
- `POST /api/v1/chat/stream` — Real-time Server-Sent Events (SSE) stream (`init`, `token`, `citation`, `done`, `error`).
- `GET /api/v1/chat/sessions` — List user's conversation sessions.
- `GET /api/v1/chat/sessions/{id}` — Retrieve conversation messages and citations.
- `DELETE /api/v1/chat/sessions/{id}` — Delete chat session.

### Memory (MAG) & Cache (CAG)
- `GET /api/v1/memory` — Query episodic memories with relevance and decay signals.
- `GET /api/v1/memory/stats` — Retrieve memory distribution stats.
- `POST /api/v1/memory` — Insert explicit user or workspace memory.
- `DELETE /api/v1/memory/{id}` — Delete memory record.
- `GET /api/v1/cache` — Query CAG cache stats and hit rates.
- `POST /api/v1/cache/invalidate` — Invalidate specific cache key or prefix.
- `POST /api/v1/cache/preload` — Pre-warm cache namespace.
- `POST /api/v1/cache/clear` — Purge cache namespace *(Admin only)*.

### Administration & Observability *(Admin Only)*
- `GET /api/v1/admin/users` — List platform users with status and roles.
- `PATCH /api/v1/admin/users/{id}` — Promote/demote role or disable user account.
- `GET /api/v1/admin/system-config` — View active system configuration.
- `GET /api/v1/analytics/overview` — System operational telemetry (TTFT, p50/p95 latencies).
- `GET /api/v1/analytics/audit-logs` — Tamper-evident corporate audit trail.
- `GET /health` — Liveness probe.
- `GET /health/ready` — Readiness probe (PostgreSQL, pgvector, LLM provider).

---

## 🛠️ Debugging & Troubleshooting Guide

### 1. `HTTP 500: Internal Server Error` on Login
* **Symptom:** You click "Sign In" in the browser and see a red box: `HTTP 500: Internal Server Error` (or `Backend server is unreachable`).
* **Root Cause:** The Vite development server on port 5173 is running, but the FastAPI backend on port 8000 is stopped. Vite's proxy receives `ECONNREFUSED` and returns a 500 status.
* **Resolution:**
  ```bash
  # Check if port 8000 is running
  curl http://127.0.0.1:8000/health
  
  # If not running, start the backend:
  cd backend && source .venv/bin/activate
  uvicorn app.main:app --port 8000
  ```

---

### 2. Port Conflict (`Address already in use`)
* **Symptom:** Starting uvicorn or Vite fails with `OSError: [Errno 48] Address already in use`.
* **Resolution:**
  ```bash
  # Find process occupying port 8000
  lsof -i :8000
  # Terminate the process
  kill -9 <PID>

  # Find process occupying port 5173
  lsof -i :5173
  kill -9 <PID>
  ```

---

### 3. Cloudflare Tunnel Returns `502 Bad Gateway`
* **Symptom:** Cloudflare tunnel opens in the browser, but displays `502 Bad Gateway`.
* **Root Cause:** The tunnel was started pointing to port 3001 (Docker container port), but you are running the Vite development server on port 5173.
* **Resolution:**
  ```bash
  # Point tunnel to the active port:
  # For local Vite dev:
  cloudflared tunnel --url http://localhost:5173

  # For Docker Compose:
  cloudflared tunnel --url http://localhost:3001
  ```

---

### 4. Database Connection Refused / Missing PostgreSQL
* **Symptom:** Backend logs show `ConnectionRefusedError: [Errno 61] Connect call failed ('127.0.0.1', 5432)`.
* **Resolution:**
  - **Quick Fix:** NexaRAG automatically falls back to an in-memory SQLite and cosine search layer if PostgreSQL is unreachable.
  - **Docker Fix:** Start the PostgreSQL container:
    ```bash
    docker compose up -d db
    ```

---

### 5. LLM Synthesis Fallback / Missing API Key
* **Symptom:** Chat returns deterministic mock answers instead of generative model outputs.
* **Root Cause:** `GEMINI_API_KEY` or `GROQ_API_KEY` is empty, or `LLM_PROVIDER` is set to `mock`.
* **Resolution:**
  Add your API key to `.env`:
  ```ini
  LLM_PROVIDER=gemini
  GEMINI_API_KEY=AIzaSy...
  ```
  Restart the backend server.

---

## 🧪 Testing & Quality Assurance

NexaRAG contains an automated test suite verifying 100% of unit, integration, security, and API specifications.

```bash
# 1. Run full backend test suite (321 tests)
backend/.venv/bin/pytest backend/tests -q

# 2. Run security and NeMo guardrail tests
backend/.venv/bin/pytest backend/tests/security backend/tests/integration/test_guardrail_pipeline.py -v

# 3. Run Python code quality & linter
backend/.venv/bin/ruff check backend
backend/.venv/bin/ruff format --check backend

# 4. Verify TypeScript build and bundling
npm --prefix frontend run build
```

---

## 📄 License

This project is licensed under the **MIT License**.
