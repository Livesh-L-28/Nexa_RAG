"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Project metadata
    PROJECT_NAME: str = "NexaRAG"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Security & Auth
    SECRET_KEY: str = "nexarag-insecure-dev-secret-key-change-in-production-min32chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/nexarag",
        description="Async SQLAlchemy database URL (e.g. postgresql+asyncpg://... or sqlite+aiosqlite://...)",
    )
    DATABASE_SYNC_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/nexarag",
        description="Sync SQLAlchemy database URL for Alembic",
    )
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Ingestion & Chunking
    UPLOAD_DIR: Path = Path("data/uploads")
    MAX_UPLOAD_SIZE_MB: int = 25
    ALLOWED_EXTENSIONS: list[str] = [".pdf", ".txt", ".docx"]
    DOCUMENTS_ADMIN_ONLY: bool = False

    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    CHUNKING_STRATEGY: str = "sentence_aware"  # fixed, sentence_aware, paragraph_aware

    # Embeddings
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_DEVICE: str = "cpu"

    # Retrieval & Search
    TOP_K: int = 5
    TOP_N_CANDIDATES: int = 20
    SIMILARITY_THRESHOLD: float = 0.3
    HYBRID_ALPHA: float = 0.7  # 1.0 = pure vector, 0.0 = pure BM25

    # Reranking
    RERANKING_ENABLED: bool = True
    RERANKER_MODEL_NAME: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # LLM Settings
    LLM_PROVIDER: str = "gemini"  # "gemini", "groq", "mock"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 2048
    LLM_TIMEOUT_SECONDS: float = 60.0
    LLM_MAX_RETRIES: int = 2

    # Context & Prompt Budgets (Phase 11)
    MAX_CONTEXT_TOKENS: int = 6000
    MAX_RAG_CONTEXT_TOKENS: int = 4000
    MAX_CAG_CONTEXT_TOKENS: int = 1500
    MAX_MAG_CONTEXT_TOKENS: int = 1000
    MAX_CONVERSATION_TOKENS: int = 1000
    MIN_CONTEXT_SCORE: float = 0.0

    # Guardrails Settings (NeMo Guardrails)
    GUARDRAILS_ENABLED: bool = True
    GUARDRAILS_PROVIDER: str = "nemo"  # "nemo", "mock"
    GUARDRAILS_CONFIG_PATH: Path = Path("app/guardrails/config")
    GUARDRAILS_INPUT_ENABLED: bool = True
    GUARDRAILS_RETRIEVAL_ENABLED: bool = True
    GUARDRAILS_OUTPUT_ENABLED: bool = True
    GUARDRAILS_FAIL_CLOSED: bool = True
    GUARDRAILS_TIMEOUT_SECONDS: float = 5.0

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # Aliases for flexible compatibility
    @property
    def APP_NAME(self) -> str:
        return self.PROJECT_NAME

    @property
    def JWT_SECRET(self) -> str:
        return self.SECRET_KEY

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        return self.DATABASE_URL

    @property
    def LLM_MODEL(self) -> str:
        if self.LLM_PROVIDER == "groq":
            return self.GROQ_MODEL
        if self.LLM_PROVIDER == "gemini":
            return self.GEMINI_MODEL
        return "mock-llm-v1"


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
