"""Retrieval Guardrail implementation for retrieved context validation."""

import uuid
from typing import Any

from app.core.config import get_settings
from app.core.logging import logger
from app.guardrails.models import (
    GuardrailDecision,
    GuardrailMetadata,
    GuardrailResult,
    GuardrailStage,
    GuardrailViolation,
)
from app.guardrails.provider import GuardrailProvider

settings = get_settings()


class RetrievalGuardrail:
    """Validates retrieved context items from RAG, CAG, and MAG against indirect injection and isolation leaks."""

    def __init__(self, provider: GuardrailProvider):
        self.provider = provider
        self.enabled = settings.GUARDRAILS_RETRIEVAL_ENABLED

    async def evaluate(
        self,
        query: str,
        contexts: list[dict[str, Any]],
        user_id: uuid.UUID | None = None,
        request_id: uuid.UUID | None = None,
    ) -> GuardrailResult:
        if not self.enabled or not settings.GUARDRAILS_ENABLED or not contexts:
            return GuardrailResult(
                decision=GuardrailDecision.ALLOW,
                stage=GuardrailStage.RETRIEVAL,
                text=f"{len(contexts)} contexts",
                metadata=GuardrailMetadata(
                    guardrail_name="RetrievalGuardrail",
                    stage=GuardrailStage.RETRIEVAL,
                    decision=GuardrailDecision.ALLOW,
                    reason="Retrieval guardrail disabled or no contexts to evaluate",
                ),
                request_id=request_id,
            )

        try:
            return await self.provider.check_retrieval(
                query=query,
                contexts=contexts,
                user_id=user_id,
                request_id=request_id,
            )
        except Exception as e:
            logger.error(f"RetrievalGuardrail provider error: {e}")
            if settings.GUARDRAILS_FAIL_CLOSED:
                violation = GuardrailViolation(
                    rule_name="retrieval_fail_closed_policy",
                    stage=GuardrailStage.RETRIEVAL,
                    reason="Guardrail service error during retrieval inspection; blocked by fail-closed policy",
                    policy="system/fail_closed",
                    severity="CRITICAL",
                )
                return GuardrailResult(
                    decision=GuardrailDecision.BLOCK,
                    stage=GuardrailStage.RETRIEVAL,
                    text="retrieved_contexts",
                    violations=[violation],
                    metadata=GuardrailMetadata(
                        guardrail_name="RetrievalGuardrail",
                        stage=GuardrailStage.RETRIEVAL,
                        decision=GuardrailDecision.BLOCK,
                        reason=violation.reason,
                        policy=violation.policy,
                        violations=[violation],
                    ),
                    error=str(e),
                    request_id=request_id,
                )
            return GuardrailResult(
                decision=GuardrailDecision.ALLOW,
                stage=GuardrailStage.RETRIEVAL,
                text="retrieved_contexts",
                metadata=GuardrailMetadata(
                    guardrail_name="RetrievalGuardrail",
                    stage=GuardrailStage.RETRIEVAL,
                    decision=GuardrailDecision.ALLOW,
                    reason="Retrieval guardrail error ignored (fail-open mode)",
                ),
                error=str(e),
                request_id=request_id,
            )
