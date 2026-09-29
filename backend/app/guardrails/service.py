"""Central GuardrailService unifying Input, Retrieval, and Output guardrails."""

from functools import lru_cache

from app.core.config import get_settings
from app.core.logging import logger
from app.guardrails.input_guard import InputGuardrail
from app.guardrails.output_guard import OutputGuardrail
from app.guardrails.provider import (
    GuardrailProvider,
    MockGuardrailProvider,
    NemoGuardrailProvider,
)
from app.guardrails.retrieval_guard import RetrievalGuardrail

settings = get_settings()


class GuardrailService:
    """Unified service coordinating three-tier guardrail validation."""

    def __init__(self, provider: GuardrailProvider | None = None):
        if provider is not None:
            self.provider = provider
        elif settings.GUARDRAILS_PROVIDER == "mock":
            self.provider = MockGuardrailProvider()
        else:
            self.provider = NemoGuardrailProvider()

        self.input_guard = InputGuardrail(self.provider)
        self.retrieval_guard = RetrievalGuardrail(self.provider)
        self.output_guard = OutputGuardrail(self.provider)
        logger.info(
            f"GuardrailService initialized with provider '{self.provider.__class__.__name__}'"
        )


@lru_cache
def get_guardrail_service() -> GuardrailService:
    """Return singleton GuardrailService instance."""
    return GuardrailService()
