"""Guardrails data models and strongly-typed definitions."""

import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GuardrailDecision(str, Enum):
    """Supported decisions for a guardrail evaluation."""

    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    SANITIZE = "SANITIZE"


class GuardrailStage(str, Enum):
    """Pipeline stage where guardrail checks are applied."""

    INPUT = "INPUT"
    RETRIEVAL = "RETRIEVAL"
    OUTPUT = "OUTPUT"


class GuardrailViolation(BaseModel):
    """Represents a specific rule or policy violation detected by a guardrail."""

    rule_name: str
    stage: GuardrailStage
    reason: str
    policy: str
    severity: str = "HIGH"
    details: dict[str, Any] = Field(default_factory=dict)


class GuardrailMetadata(BaseModel):
    """Metadata detailing guardrail execution."""

    guardrail_name: str
    stage: GuardrailStage
    decision: GuardrailDecision
    reason: str | None = None
    policy: str | None = None
    latency_ms: float = 0.0
    sanitized: bool = False
    violations: list[GuardrailViolation] = Field(default_factory=list)


class GuardrailResult(BaseModel):
    """Complete evaluation outcome from a guardrail check."""

    decision: GuardrailDecision
    stage: GuardrailStage
    text: str  # Original text or sanitized text
    sanitized_text: str | None = None
    violations: list[GuardrailViolation] = Field(default_factory=list)
    metadata: GuardrailMetadata
    error: str | None = None
    request_id: uuid.UUID | None = None

    @property
    def is_allowed(self) -> bool:
        return self.decision == GuardrailDecision.ALLOW

    @property
    def is_blocked(self) -> bool:
        return self.decision == GuardrailDecision.BLOCK

    @property
    def is_sanitized(self) -> bool:
        return self.decision == GuardrailDecision.SANITIZE

    @property
    def safe_text(self) -> str:
        """Return sanitized text if sanitized, otherwise original text."""
        if self.is_sanitized and self.sanitized_text is not None:
            return self.sanitized_text
        return self.text
