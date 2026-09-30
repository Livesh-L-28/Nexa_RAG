# NexaRAG — Docker & Production Deployment Specification

## 1. System Overview & Deployment Architecture

NexaRAG is fully containerized using Docker and orchestrated via Docker Compose. The architecture separates the presentation layer (React SPA served via production Nginx reverse proxy), application synthesis layer (FastAPI backend), and the persistence layer (PostgreSQL with `pgvector`).

```text
                                Client Web Browser
                                        │
                                        │ (Port 3000 / 80)
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │            Frontend Container           │
                   │        (Alpine Nginx + React SPA)       │
                   └────────────────────┬────────────────────┘
                                        │
                                        │ Proxy (/api, /health)
                                        ▼ (Internal Docker Network)
                   ┌─────────────────────────────────────────┐
                   │            Backend Container            │
                   │           (Python 3.12-slim)            │
                   │  - FastAPI Application (Port 8000)      │
                   │  - RAG / CAG / MAG Orchestrator         │
                   │  - Hybrid Search & Reranking (CPU)      │
                   │  - Context Fusion & LLM Providers       │
                   └────────────────────┬────────────────────┘
                                        │
                                        │ Asyncpg Connection
                                        ▼ (Port 5432)
                   ┌─────────────────────────────────────────┐
                   │           Database Container            │
                   │       (pgvector/pgvector:pg16)          │
                   │  - PostgreSQL 16 + pgvector Extension   │
                   │  - Persistent Volume: pgdata            │
                   └─────────────────────────────────────────┘
```

---

## 2. Prerequisites & Hardware Requirements

### Minimum Software Requirements
- **Docker Engine**: Version 20.10.0+ (Tested on Docker 29.7.2)
- **Docker Compose**: Version 2.0.0+ (Tested on Compose v5.5.1)
- **Host OS**: macOS (Apple Silicon / Intel), Linux (Ubuntu/Debian/RHEL/Arch), or Windows 11 with WSL2.

### Resource Allocation Guidelines
- **CPU**: 2+ Cores recommended (Embedding and Cross-Encoder reranking models run locally on CPU without requiring CUDA/GPU).
- **RAM**: 4GB Minimum (8GB Recommended for multi-document indexing and concurrent embeddings).
- **Disk**: 10GB free space for container images, embeddings cache, and uploaded documents.

---

## 3. Environment Configuration Contract

Configuration is strictly environment-driven via `.env` files or container environment injection. No secrets, credentials, or environment-specific URLs are hard-coded.

| Variable | Type | Default (Local / Docker) | Description |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | string | `production` (in Docker) | Environment identifier (`development`, `test`, `production`). |
| `POSTGRES_DB` | string | `nexarag` | PostgreSQL database name. |
| `POSTGRES_USER` | string | `postgres` | PostgreSQL administrative username. |
| `POSTGRES_PASSWORD` | string | `postgres` | PostgreSQL password. |
| `DATABASE_URL` | string | `postgresql+asyncpg://...` | Async SQLAlchemy connection URI for FastAPI runtime. |
| `DATABASE_SYNC_URL` | string | `postgresql://...` | Synchronous SQLAlchemy URI for Alembic migrations. |
| `JWT_SECRET` | string | *(Random 32+ char string)* | Cryptographic HMAC secret for signing auth tokens. |
| `LLM_PROVIDER` | string | `mock` | Active provider: `mock`, `gemini`, `groq`. |
| `LLM_MODEL` | string | `gemini-2.5-flash` | LLM model identifier. |
| `GEMINI_API_KEY` | string | *(Optional)* | Google AI Studio API key (required if `LLM_PROVIDER=gemini`). |
| `GROQ_API_KEY` | string | *(Optional)* | Groq Cloud API key (required if `LLM_PROVIDER=groq`). |
| `CORS_ORIGINS` | JSON array | `["http://localhost:3000"]` | Allowed browser origins. |
| `UPLOAD_DIR` | path | `/app/data/uploads` | Path to persistent document uploads directory. |

---

## 4. Container Specifications & Health Probes

### A. Database Container (`nexarag_db`)
- **Base Image**: `pgvector/pgvector:pg16`
- **Internal Port**: `5432` (Exposed to host as `5432` for local development/inspection).
- **Persistent Volume**: `pgdata` mounted to `/var/lib/postgresql/data`.
- **Healthcheck**:
  ```yaml
  test: ["CMD-SHELL", "pg_isready -U postgres -d nexarag"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 5s
  ```

### B. Backend Container (`nexarag_backend`)
- **Base Image**: `python:3.12-slim`
- **User**: Non-root `appuser` (UID 1000).
- **Internal Port**: `8000` (Exposed to host as `8000`).
- **Storage Mount**: Host `./data/uploads` bind mounted to `/app/data/uploads`.
- **Startup Sequencing**: Depends on `db` with `condition: service_healthy`.
- **Healthcheck**:
  ```yaml
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 15s
  timeout: 5s
  retries: 3
  start_period: 10s
  ```

### C. Frontend Container (`nexarag_frontend`)
- **Build Stage**: Multi-stage Docker build via `node:20-alpine` compiling TypeScript & Vite.
- **Runtime Stage**: `nginx:alpine` serving pre-compiled static assets.
- **Port Mapping**: `3000:80` (Host port 3000 mapped to Nginx port 80).
- **Reverse Proxy**: Proxies `/api` and `/health` requests to `http://backend:8000`.
- **SSE Streaming Support**: Nginx explicitly configured with `proxy_buffering off;` and `proxy_read_timeout 600s;` to support real-time token streaming.
- **Startup Sequencing**: Depends on `backend` with `condition: service_healthy`.
- **Healthcheck**:
  ```yaml
  test: ["CMD", "wget", "-q", "--spider", "http://localhost/"]
  interval: 15s
  timeout: 5s
  retries: 3
  start_period: 5s
  ```

---

## 5. Startup & Migration Lifecycle

When Docker Compose launches:
1. `nexarag_db` initializes PostgreSQL 16 and begins executing the health probe (`pg_isready`).
2. Once `db` reaches `healthy` state, `nexarag_backend` starts.
3. During FastAPI lifespan initialization (`app/main.py`):
   - Automatically executes `CREATE EXTENSION IF NOT EXISTS vector;`.
   - Executes SQLAlchemy `Base.metadata.create_all` to initialize all tables (`users`, `documents`, `document_chunks`, `chat_sessions`, `chat_messages`, `retrieval_logs`, `memory_items`).
   - Ensures upload directories are configured.
4. Once `backend` responds with HTTP 200 on `/health`, `nexarag_frontend` becomes active and serves traffic on port `3000`.

---

## 6. Common Docker Compose Commands

### Option 1: Instant Launch with Pre-Built GHCR Images (Recommended)
```bash
# Pull the pre-built images from GitHub Container Registry
docker compose pull

# Start all services in the background
docker compose up -d
```

### Option 2: Build and Start from Local Source Code
```bash
# Build and start all services in the background
docker compose up -d --build

# View real-time aggregated logs
docker compose logs -f

# View backend logs specifically
docker compose logs -f backend

# Check container health and status
docker compose ps

# Gracefully stop running containers (preserves database and upload data)
docker compose stop

# Restart a single service (e.g. backend)
docker compose restart backend

# Stop and remove containers and network (preserves database volumes)
docker compose down
```

### Clean Database Initialization / Destructive Reset
```bash
# WARNING: This removes the persistent database volume (all data destroyed)
docker compose down -v

# Rebuild from scratch with clean database
docker compose up -d --build
```

---

## 7. Troubleshooting & Diagnostic Guide

| Issue | Root Cause | Resolution |
| :--- | :--- | :--- |
| `backend` exits immediately on startup | Database connection failure or PostgreSQL not yet ready. | Ensure `db` container has `condition: service_healthy` in compose. Check `docker compose logs db`. |
| SSE chat streaming tokens delayed or buffered | Nginx reverse proxy buffering active. | Verify `frontend/nginx.conf` contains `proxy_buffering off;` and `chunked_transfer_encoding off;`. |
| Document upload fails with `413 Request Entity Too Large` | Nginx default body size limit exceeded. | Verify `client_max_body_size 50M;` is present in `frontend/nginx.conf`. |
| `pgvector extension not found` | Using standard postgres image instead of pgvector. | Verify `db` service uses `pgvector/pgvector:pg16` image. |
| Permission denied writing to `/app/data/uploads` | Container running as non-root without folder write access. | Ensure Dockerfile creates `/app/data/uploads` and `chown`s to `appuser`. |

---

## 8. Development vs Future Cloud Production Architecture

| Dimension | Current Local / Docker Compose | Future Cloud (AWS - Phase 17+) |
| :--- | :--- | :--- |
| **Compute** | Single host Docker containers | ECS Fargate / EKS managed containers |
| **Database** | Containerized `pgvector/pgvector:pg16` | Amazon RDS PostgreSQL + pgvector extension |
| **File Storage** | Bind mounted local directory `./data/uploads` | Amazon S3 with IAM presigned upload URLs |
| **Secrets** | Local `.env` file | AWS Secrets Manager / Parameter Store |
| **Ingress & SSL** | Local Nginx on port 80/3000 | AWS Application Load Balancer + CloudFront + ACM |
| **Observability** | In-memory metrics & JSON event logs | AWS CloudWatch / OpenTelemetry Collector / Grafana |
