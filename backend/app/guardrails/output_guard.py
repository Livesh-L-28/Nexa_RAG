"""Output Guardrail implementation for LLM generation validation."""

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


class OutputGuardrail:
    """Enforces prompt leakage protection, safety policies, and output sanitization on LLM responses."""

    def __init__(self, provider: GuardrailProvider):
        self.provider = provider
        self.enabled = settings.GUARDRAILS_OUTPUT_ENABLED

    async def evaluate(
        self,
        query: str,
        response_text: str,
        contexts: list[dict[str, Any]] | None = None,
        request_id: uuid.UUID | None = None,
    ) -> GuardrailResult:
        if not self.enabled or not settings.GUARDRAILS_ENABLED:
            return GuardrailResult(
                decision=GuardrailDecision.ALLOW,
                stage=GuardrailStage.OUTPUT,
                text=response_text,
                metadata=GuardrailMetadata(
                    guardrail_name="OutputGuardrail",
                    stage=GuardrailStage.OUTPUT,
                    decision=GuardrailDecision.ALLOW,
                    reason="Output guardrail is disabled by configuration",
                ),
                request_id=request_id,
            )

        try:
            return await self.provider.check_output(
                query=query,
                response_text=response_text,
                contexts=contexts,
                request_id=request_id,
            )
        except Exception as e:
            logger.error(f"OutputGuardrail provider error: {e}")
            if settings.GUARDRAILS_FAIL_CLOSED:
                violation = GuardrailViolation(
                    rule_name="output_fail_closed_policy",
                    stage=GuardrailStage.OUTPUT,
                    reason="Guardrail service error during output inspection; blocked by fail-closed policy",
                    policy="system/fail_closed",
                    severity="CRITICAL",
                )
                return GuardrailResult(
                    decision=GuardrailDecision.BLOCK,
                    stage=GuardrailStage.OUTPUT,
                    text=response_text,
                    violations=[violation],
                    metadata=GuardrailMetadata(
                        guardrail_name="OutputGuardrail",
                        stage=GuardrailStage.OUTPUT,
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
                stage=GuardrailStage.OUTPUT,
                text=response_text,
                metadata=GuardrailMetadata(
                    guardrail_name="OutputGuardrail",
                    stage=GuardrailStage.OUTPUT,
                    decision=GuardrailDecision.ALLOW,
                    reason="Output guardrail error ignored (fail-open mode)",
                ),
                error=str(e),
                request_id=request_id,
            )
