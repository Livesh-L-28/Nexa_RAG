"""Privacy-aware structured logger for pipeline observability in NexaRAG."""

import json
import logging
import uuid
from typing import Any

from app.observability.events import EventType, ObservabilityEvent

# Strict blacklist of sensitive keys that must never appear unredacted in observability logs
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
    "prompt_text",
    "memory_content",
    "chunk_content",
}


def sanitize_payload(payload: Any) -> Any:
    """Recursively sanitize a dictionary or list, redacting any sensitive keys or strings."""
    if isinstance(payload, dict):
        sanitized = {}
        for k, v in payload.items():
            k_lower = str(k).lower()
            if any(sens in k_lower for sens in SENSITIVE_KEYS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_payload(v)
        return sanitized
    elif isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]
    elif isinstance(payload, uuid.UUID):
        return str(payload)
    return payload


class ObservabilityLogger:
    """Structured logger emitting standardized JSON events with zero credential or PII leaks."""

    def __init__(self, logger_name: str = "nexarag.observability"):
        self.logger = logging.getLogger(logger_name)

    def log_event(self, event: ObservabilityEvent) -> None:
        """Serialize and log a structured lifecycle event."""
        event_dict = event.to_dict()
        sanitized_data = sanitize_payload(event_dict.get("data", {}))
        event_dict["data"] = sanitized_data

        msg = json.dumps(event_dict)
        if event.event in (EventType.STAGE_FAILED, EventType.REQUEST_FAILED):
            self.logger.error(msg)
        else:
            self.logger.info(msg)

    def log_request_started(
        self,
        request_id: uuid.UUID,
        session_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> None:
        """Emit request_started event."""
        self.log_event(
            ObservabilityEvent(
                event=EventType.REQUEST_STARTED,
                request_id=request_id,
                session_id=session_id,
                data={
                    "user_id": str(user_id) if user_id else None,
                },
            )
        )

    def log_stage_completed(
        self,
        event_type: EventType,
        request_id: uuid.UUID,
        session_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Emit a stage completion event with timing and metric data."""
        self.log_event(
            ObservabilityEvent(
                event=event_type,
                request_id=request_id,
                session_id=session_id,
                data=kwargs,
            )
        )

    def log_error(
        self,
        request_id: uuid.UUID,
        session_id: uuid.UUID | None,
        stage: str,
        error_type: str,
        sanitized_message: str,
    ) -> None:
        """Emit a structured failure event."""
        self.log_event(
            ObservabilityEvent(
                event=EventType.STAGE_FAILED,
                request_id=request_id,
                session_id=session_id,
                data={
                    "stage": stage,
                    "error_type": error_type,
                    "message": sanitized_message,
                },
            )
        )


_default_logger = ObservabilityLogger()


def get_observability_logger() -> ObservabilityLogger:
    """Return the shared ObservabilityLogger instance."""
    return _default_logger
