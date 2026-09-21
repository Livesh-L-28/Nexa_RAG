"""Structured JSON logging configuration for NexaRAG."""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Custom formatter outputting logs as single-line JSON objects."""

    # Fields that should never be serialized in logs
    SENSITIVE_KEYS = {
        "password",
        "password_hash",
        "token",
        "secret",
        "api_key",
        "jwt_secret",
        "authorization",
        "bearer",
        "credential",
        "raw_prompt",
        "full_prompt",
        "chunk_content",
        "memory_content",
    }

    def format(self, record: logging.LogRecord) -> str:
        log_payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add standard contextual attributes if present
        for attr in [
            "request_id",
            "user_id",
            "endpoint",
            "method",
            "status_code",
            "retrieval_latency_ms",
            "reranking_latency_ms",
            "llm_latency_ms",
            "total_latency_ms",
            "document_id",
            "status",
        ]:
            if hasattr(record, attr):
                val = getattr(record, attr)
                if val is not None:
                    log_payload[attr] = val

        # Handle exception info safely
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        # Sanitize sensitive fields in any extra dict
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            sanitized = {}
            for k, v in record.extra_data.items():
                if any(sens in k.lower() for sens in self.SENSITIVE_KEYS):
                    sanitized[k] = "[REDACTED]"
                else:
                    sanitized[k] = v
            log_payload["data"] = sanitized

        return json.dumps(log_payload)


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure root and application loggers."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    # Attach JSON handler to stdout
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(stdout_handler)

    # Suppress verbose noisy third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logger = logging.getLogger("nexarag")
    logger.setLevel(log_level)
    return logger


logger = setup_logging()
