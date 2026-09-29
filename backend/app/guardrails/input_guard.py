"""Input Guardrail implementation for pre-retrieval validation."""

import uuid

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


class InputGuardrail:
    """Enforces prompt injection, jailbreak, sensitive info, and topic safety on user inputs."""

    def __init__(self, provider: GuardrailProvider):
        self.provider = provider
        self.enabled = settings.GUARDRAILS_INPUT_ENABLED

    async def evaluate(
        self,
        query: str,
        user_id: uuid.UUID | None = None,
        session_id: uuid.UUID | None = None,
        request_id: uuid.UUID | None = None,
    ) -> GuardrailResult:
        if not self.enabled or not settings.GUARDRAILS_ENABLED:
            return GuardrailResult(
                decision=GuardrailDecision.ALLOW,
                stage=GuardrailStage.INPUT,
                text=query,
                metadata=GuardrailMetadata(
                    guardrail_name="InputGuardrail",
                    stage=GuardrailStage.INPUT,
                    decision=GuardrailDecision.ALLOW,
                    reason="Input guardrail is disabled by configuration",
                ),
                request_id=request_id,
            )

        try:
            return await self.provider.check_input(
                query=query,
                user_id=user_id,
                session_id=session_id,
                request_id=request_id,
            )
        except Exception as e:
            logger.error(f"InputGuardrail provider error: {e}")
            if settings.GUARDRAILS_FAIL_CLOSED:
                violation = GuardrailViolation(
                    rule_name="fail_closed_policy",
                    stage=GuardrailStage.INPUT,
                    reason="Guardrail service unavailable or failed; request blocked by fail-closed policy",
                    policy="system/fail_closed",
                    severity="CRITICAL",
                )
                return GuardrailResult(
                    decision=GuardrailDecision.BLOCK,
                    stage=GuardrailStage.INPUT,
                    text=query,
                    violations=[violation],
                    metadata=GuardrailMetadata(
                        guardrail_name="InputGuardrail",
                        stage=GuardrailStage.INPUT,
                        decision=GuardrailDecision.BLOCK,
                        reason=violation.reason,
                        policy=violation.policy,
                        violations=[violation],
                    ),
                    error=str(e),
                    request_id=request_id,
                )
            # Fail open fallback if explicitly configured
            return GuardrailResult(
                decision=GuardrailDecision.ALLOW,
                stage=GuardrailStage.INPUT,
                text=query,
                metadata=GuardrailMetadata(
                    guardrail_name="InputGuardrail",
                    stage=GuardrailStage.INPUT,
                    decision=GuardrailDecision.ALLOW,
                    reason="Guardrail provider error ignored (fail-open mode)",
                ),
                error=str(e),
                request_id=request_id,
            )
