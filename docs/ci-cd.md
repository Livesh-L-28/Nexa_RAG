# NexaRAG — GitHub Actions CI/CD Pipeline Specification

## 1. Pipeline Overview

The NexaRAG Continuous Integration (CI) pipeline automates quality control, security checks, test execution, static analysis, type-checking, Docker image builds, and containerized smoke testing for every commit and pull request against the `main` branch.

```text
                                 Developer Push / PR
                                         │
                                         ▼
                                 GitHub Actions CI
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
          [ Backend Checks ]                         [ Frontend Checks ]
          - Python 3.12 Setup                        - Node.js 20 Setup
          - Pip Cache & Dependency Install          - Npm Cache & npm ci
          - Ruff Lint (`ruff check`)                 - TypeScript Verification
          - Ruff Format (`ruff format --check`)      - Production Vite Build
          - Pytest Suite (295 tests)                 └──────────┬──────────────┘
          └──────────────────┬──────────────────────────────────┘
                             ▼
                    [ Docker Validation ]
                    - Docker Compose Config Validation
                    - Multi-stage Build & Layer Caching (gha)
                    - Non-root Container Verification
                             │
                             ▼
                    [ Integration Smoke Test ]
                    - Docker Compose Stack Launch (`db`, `backend`, `frontend`)
                    - PostgreSQL 16 + pgvector Health Polling
                    - End-to-End Test (`scripts/verify_deployment.py`)
                    - Graceful Container Teardown
```

---

## 2. Trigger Strategy & Concurrency

- **Triggers**:
  - `push` to `main`
  - `pull_request` against `main`
- **Concurrency Control**:
  - Automatically cancels out-of-date in-progress runs when new commits are pushed to the same branch/PR (`cancel-in-progress: true`).

---

## 3. Job Breakdown & Execution Stages

### Stage 1: Backend Quality & Automated Testing (`backend-checks`)
- **Runner**: `ubuntu-latest`
- **Runtime**: Python 3.12
- **Dependency Caching**: GitHub Actions pip cache keyed on `backend/requirements.txt`.
- **Validation**:
  1. `ruff check backend scripts`: Validates PEP 8, flake8, imports, and security rules.
  2. `ruff format --check backend scripts`: Enforces consistent formatting across Python code.
  3. `pytest backend/tests`: Runs 295 unit, API, integration, and tenant isolation security tests with code coverage reporting.
  4. **Mock Mode Guarantee**: Tests execute with `LLM_PROVIDER=mock` and SQLite in-memory engine, requiring zero external API keys or cloud credentials.

### Stage 2: Frontend Verification & Production Build (`frontend-checks`)
- **Runner**: `ubuntu-latest`
- **Runtime**: Node.js 20
- **Dependency Caching**: GitHub Actions npm cache keyed on `frontend/package-lock.json`.
- **Validation**:
  1. `npm ci`: Deterministic, clean installation of exact dependencies.
  2. `npm run build`: Type-checks TypeScript code (`tsc`) and compiles static production bundle (`vite build`).

### Stage 3: Containerization & Compose Validation (`docker-checks`)
- **Runner**: `ubuntu-latest`
- **Dependencies**: Requires both `backend-checks` and `frontend-checks` to pass.
- **Validation**:
  1. `docker compose config`: Validates Compose syntax, volume bindings, environment wiring, and service definitions.
  2. `docker/build-push-action`: Validates building backend and frontend container images using Docker Buildx and GitHub Actions cache (`type=gha`).

### Stage 4: Containerized End-to-End Smoke Test (`smoke-test`)
- **Runner**: `ubuntu-latest`
- **Dependencies**: Requires `docker-checks` to pass.
- **Validation**:
  1. Launches the full multi-container stack (`db` with pgvector, `backend`, and `frontend`).
  2. Polls `http://localhost:8000/health/ready` until PostgreSQL and pgvector report healthy.
  3. Executes `scripts/verify_deployment.py` to validate:
     - User registration & JWT authentication
     - Document upload, text extraction, chunking, and embedding generation
     - Grounded RAG query synthesis and citations
     - Real-time SSE token streaming via Nginx reverse proxy
  4. Automatically dumps container logs if failures occur and performs graceful teardown (`docker compose down`).

---

## 4. Security & Environment Invariants in CI

1. **Zero Secret Leakage**: No live API keys (`GEMINI_API_KEY`, `GROQ_API_KEY`), database passwords, or production JWT secrets are stored in Git or GitHub Actions workflows.
2. **Provider Agnostic**: All tests and smoke validations run against offline deterministic mocks (`LLM_PROVIDER=mock`).
3. **No GPU Requirement**: All embedding, reranking, and search pipelines execute in CPU-only mode.
4. **Deterministic Failures**: Any lint failure, format discrepancy, type error, broken test, or unhealthy container immediately halts the pipeline with an error code.
