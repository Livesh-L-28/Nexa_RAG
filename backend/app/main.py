"""Main FastAPI application entry point for NexaRAG."""

import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.routes.admin import router as admin_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.auth import router as auth_router
from app.api.routes.cache import router as cache_router
from app.api.routes.chat import router as chat_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.memory import router as memory_router
from app.core.config import get_settings
from app.core.exceptions import AppException
from app.core.logging import logger
from app.database.connection import init_db

settings = get_settings()

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown routines."""
    logger.info(f"Starting {settings.APP_NAME} in '{settings.ENVIRONMENT}' environment...")
    # Ensure upload directory exists
    upload_path = Path(settings.UPLOAD_DIR)
    upload_path.mkdir(parents=True, exist_ok=True)

    # Initialize database tables
    try:
        await init_db()
        logger.info("Database initialized successfully.")

        # Verify and seed default accounts
        from sqlalchemy import select

        from app.core.security import hash_password
        from app.database.connection import AsyncSessionLocal
        from app.database.models import User

        async with AsyncSessionLocal() as db:
            # Verify or create Admin
            admin_res = await db.execute(select(User).where(User.email == "admin@nexarag.ai"))
            admin_user = admin_res.scalar_one_or_none()
            if not admin_user:
                db.add(
                    User(
                        email="admin@nexarag.ai",
                        password_hash=hash_password("adminpassword123"),
                        role="ADMIN",
                        is_active=True,
                    )
                )
            else:
                admin_user.role = "ADMIN"
                admin_user.password_hash = hash_password("adminpassword123")
                admin_user.is_active = True

            # Verify or create Demo User
            demo_res = await db.execute(select(User).where(User.email == "demo@nexarag.ai"))
            demo_user = demo_res.scalar_one_or_none()
            if not demo_user:
                db.add(
                    User(
                        email="demo@nexarag.ai",
                        password_hash=hash_password("password123"),
                        role="USER",
                        is_active=True,
                    )
                )
            else:
                demo_user.role = "USER"
                demo_user.password_hash = hash_password("password123")
                demo_user.is_active = True
            await db.commit()
            logger.info("Verified default admin and user accounts.")
    except Exception as e:
        logger.error(f"Error during database initialization/seeding: {e}")

    yield

    logger.info(f"Shutting down {settings.APP_NAME}...")


app = FastAPI(
    title=settings.APP_NAME,
    description="Enterprise AI Document Intelligence & Retrieval-Augmented Generation (RAG) Platform",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Attach rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_correlation_middleware(request: Request, call_next):
    """Correlate requests using client-provided X-Request-ID or a server-generated UUID."""
    raw_req_id = request.headers.get("X-Request-ID")
    req_id = None
    if raw_req_id:
        try:
            req_id = uuid.UUID(raw_req_id)
        except (ValueError, TypeError, AttributeError):
            req_id = uuid.uuid4()
    else:
        req_id = uuid.uuid4()

    request.state.request_id = req_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = str(req_id)
    return response


# Exception Handlers
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Structured handler for application business exceptions."""
    logger.warning(
        f"AppException on {request.method} {request.url.path}: [{exc.code}] {exc.message}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Clean JSON formatting for Pydantic input validation failures."""
    logger.warning(f"Validation error on {request.method} {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Input validation failed",
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all handler for unhandled internal exceptions."""
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please contact support.",
            }
        },
    )


# Register API routers with versioned prefix /api/v1
app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(memory_router, prefix="/api/v1")
app.include_router(cache_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")

# Also mount health probes directly at root for standard k8s/Docker health checks
app.include_router(health_router)


@app.get("/", tags=["Root"])
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs",
    }
