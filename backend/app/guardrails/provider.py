"""Guardrail Provider interface and implementations (NeMo and Mock)."""

import asyncio
import re
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any

from app.core.config import get_settings
from app.core.logging import logger
from app.guardrails.config import GuardrailConfigLoader
from app.guardrails.models import (
    GuardrailDecision,
    GuardrailMetadata,
    GuardrailResult,
    GuardrailStage,
    GuardrailViolation,
)

settings = get_settings()

# Known high-risk prompt injection & jailbreak patterns
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"reveal\s+(your\s+)?system\s+prompt",
    r"show\s+(me\s+)?(your\s+)?(initial\s+|system\s+)?(prompt|instructions)",
    r"what\s+(is|are)\s+your\s+(initial\s+|system\s+)?(prompt|instructions)",
    r"disable\s+(all\s+)?safety\s+rules",
    r"act\s+as\s+an\s+unrestricted\s+model",
    r"dan\s+mode\s+enabled",
    r"developer\s+mode\s+enabled",
    r"bypass\s+all\s+(filters|restrictions|guardrails)",
]

# Denied topics
DENIED_TOPIC_PATTERNS = [
    r"how\s+to\s+(make|build|create|assemble)\s+(a\s+)?(bomb|explosive|weapon)",
    r"(create|write|deploy)\s+(a\s+)?(malware|virus|ransomware|keylogger)",
    r"exploit\s+vulnerabilit(y|ies)\s+to\s+hack",
]

# Sensitive Information (PII) patterns
SSN_PATTERN = r"\b\d{3}-\d{2}-\d{4}\b"
CREDIT_CARD_PATTERN = r"\b(?:\d{4}[-\s]?){3}\d{4}\b"


class GuardrailProvider(ABC):
    """Abstract provider interface for evaluating safety guardrails."""

    @abstractmethod
    async def check_input(
        self,
        query: str,
        user_id: uuid.UUID | None = None,
        session_id: uuid.UUID | None = None,
        request_id: uuid.UUID | None = None,
    ) -> GuardrailResult:
        """Evaluate user input for injection, jailbreaks, PII, and denied topics."""

    @abstractmethod
    async def check_retrieval(
        self,
        query: str,
        contexts: list[dict[str, Any]],
        user_id: uuid.UUID | None = None,
        request_id: uuid.UUID | None = None,
    ) -> GuardrailResult:
        """Evaluate retrieved contexts for indirect prompt injection, cross-user leakage, or secrets."""

    @abstractmethod
    async def check_output(
        self,
        query: str,
        response_text: str,
        contexts: list[dict[str, Any]] | None = None,
        request_id: uuid.UUID | None = None,
    ) -> GuardrailResult:
        """Evaluate LLM generated response for prompt leakage, unsafe content, or grounding issues."""


class MockGuardrailProvider(GuardrailProvider):
    """Deterministic, local regex and heuristic-based guardrail provider for testing and offline environments."""

    def __init__(
        self,
        simulate_failure: bool = False,
        simulate_timeout: bool = False,
        timeout_seconds: float = 0.1,
    ):
        self.simulate_failure = simulate_failure
        self.simulate_timeout = simulate_timeout
        self.timeout_seconds = timeout_seconds

    async def _simulate_error_or_delay(self):
        if self.simulate_timeout:
            await asyncio.sleep(self.timeout_seconds)
            raise TimeoutError("Guardrail check timed out")
        if self.simulate_failure:
            raise RuntimeError("Simulated Guardrail Provider Failure")

    async def check_input(
        self,
        query: str,
        user_id: uuid.UUID | None = None,
        session_id: uuid.UUID | None = None,
        request_id: uuid.UUID | None = None,
    ) -> GuardrailResult:
        start_time = time.perf_counter()
        req_id = request_id or uuid.uuid4()
        await self._simulate_error_or_delay()

        q_lower = query.lower()
        violations: list[GuardrailViolation] = []

        # 1. Prompt Injection Checks
        for pat in PROMPT_INJECTION_PATTERNS:
            if re.search(pat, q_lower):
                violations.append(
                    GuardrailViolation(
                        rule_name="prompt_injection_detection",
                        stage=GuardrailStage.INPUT,
                        reason="Prompt injection pattern detected in input",
                        policy="security/anti_injection",
                        severity="CRITICAL",
                    )
                )
                break

        # 2. Denied Topics
        for pat in DENIED_TOPIC_PATTERNS:
            if re.search(pat, q_lower):
                violations.append(
                    GuardrailViolation(
                        rule_name="denied_topic_restriction",
                        stage=GuardrailStage.INPUT,
                        reason="Prohibited or dangerous topic requested",
                        policy="safety/denied_topics",
                        severity="HIGH",
                    )
                )
                break

        # 3. Sensitive Information / PII (Sanitization or Block)
        sanitized_text = query
        has_ssn = bool(re.search(SSN_PATTERN, query))
        has_cc = bool(re.search(CREDIT_CARD_PATTERN, query))
        if has_ssn or has_cc:
            sanitized_text = re.sub(SSN_PATTERN, "[REDACTED_SSN]", sanitized_text)
            sanitized_text = re.sub(CREDIT_CARD_PATTERN, "[REDACTED_CC]", sanitized_text)
            violations.append(
                GuardrailViolation(
                    rule_name="pii_detection",
                    stage=GuardrailStage.INPUT,
                    reason="Sensitive PII detected and redacted",
                    policy="privacy/pii_protection",
                    severity="MEDIUM",
                )
            )

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if any(v.severity in ("CRITICAL", "HIGH") for v in violations):
            decision = GuardrailDecision.BLOCK
            reason = violations[0].reason
            policy = violations[0].policy
        elif sanitized_text != query:
            decision = GuardrailDecision.SANITIZE
            reason = "Input sanitized to remove sensitive information"
            policy = "privacy/pii_protection"
        else:
            decision = GuardrailDecision.ALLOW
            reason = None
            policy = None

        metadata = GuardrailMetadata(
            guardrail_name="MockGuardrailProvider",
            stage=GuardrailStage.INPUT,
            decision=decision,
            reason=reason,
            policy=policy,
            latency_ms=round(latency_ms, 2),
            sanitized=decision == GuardrailDecision.SANITIZE,
            violations=violations,
        )

        return GuardrailResult(
            decision=decision,
            stage=GuardrailStage.INPUT,
            text=query,
            sanitized_text=sanitized_text if decision == GuardrailDecision.SANITIZE else None,
            violations=violations,
            metadata=metadata,
            request_id=req_id,
        )

    async def check_retrieval(
        self,
        query: str,
        contexts: list[dict[str, Any]],
        user_id: uuid.UUID | None = None,
        request_id: uuid.UUID | None = None,
    ) -> GuardrailResult:
        start_time = time.perf_counter()
        req_id = request_id or uuid.uuid4()
        await self._simulate_error_or_delay()

        violations: list[GuardrailViolation] = []
        user_id_str = str(user_id) if user_id else None

        for idx, ctx in enumerate(contexts):
            content = ctx.get("content", "")
            c_lower = content.lower()

            # Check cross-user leakage
            ctx_user = ctx.get("user_id") or ctx.get("metadata", {}).get("user_id")
            if user_id_str and ctx_user and str(ctx_user) != user_id_str:
                violations.append(
                    GuardrailViolation(
                        rule_name="cross_user_isolation",
                        stage=GuardrailStage.RETRIEVAL,
                        reason=f"Retrieved item at index {idx} belongs to a different user",
                        policy="security/user_isolation",
                        severity="CRITICAL",
                        details={
                            "item_index": idx,
                            "expected_user": user_id_str,
                            "found_user": str(ctx_user),
                        },
                    )
                )

            # Check indirect prompt injection in retrieved document
            if (
                "system instruction:" in c_lower
                or "disregard instructions" in c_lower
                or "ignore previous instructions" in c_lower
                or "reveal your system prompt" in c_lower
            ):
                violations.append(
                    GuardrailViolation(
                        rule_name="indirect_prompt_injection",
                        stage=GuardrailStage.RETRIEVAL,
                        reason=f"Retrieved document at index {idx} contains malicious prompt override",
                        policy="security/anti_indirect_injection",
                        severity="CRITICAL",
                        details={"item_index": idx},
                    )
                )

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if violations:
            decision = GuardrailDecision.BLOCK
            reason = violations[0].reason
            policy = violations[0].policy
        else:
            decision = GuardrailDecision.ALLOW
            reason = None
            policy = None

        metadata = GuardrailMetadata(
            guardrail_name="MockGuardrailProvider",
            stage=GuardrailStage.RETRIEVAL,
            decision=decision,
            reason=reason,
            policy=policy,
            latency_ms=round(latency_ms, 2),
            sanitized=False,
            violations=violations,
        )

        return GuardrailResult(
            decision=decision,
            stage=GuardrailStage.RETRIEVAL,
            text=f"{len(contexts)} contexts inspected",
            violations=violations,
            metadata=metadata,
            request_id=req_id,
        )

    async def check_output(
        self,
        query: str,
        response_text: str,
        contexts: list[dict[str, Any]] | None = None,
        request_id: uuid.UUID | None = None,
    ) -> GuardrailResult:
        start_time = time.perf_counter()
        req_id = request_id or uuid.uuid4()
        await self._simulate_error_or_delay()

        violations: list[GuardrailViolation] = []
        resp_lower = response_text.lower()

        # Check for system prompt leakage
        if (
            "you are nexarag" in resp_lower
            or "developer system instructions" in resp_lower
            or "system prompt:" in resp_lower
        ):
            violations.append(
                GuardrailViolation(
                    rule_name="system_prompt_leakage",
                    stage=GuardrailStage.OUTPUT,
                    reason="Model output contains internal system prompt instructions",
                    policy="security/anti_leakage",
                    severity="CRITICAL",
                )
            )

        # Check for dangerous advice
        for pat in DENIED_TOPIC_PATTERNS:
            if re.search(pat, resp_lower):
                violations.append(
                    GuardrailViolation(
                        rule_name="unsafe_output_content",
                        stage=GuardrailStage.OUTPUT,
                        reason="Model output contains prohibited unsafe instructions",
                        policy="safety/denied_topics",
                        severity="CRITICAL",
                    )
                )
                break

        # Check for credit card / SSN leakage in output
        sanitized_output = response_text
        if re.search(SSN_PATTERN, response_text) or re.search(CREDIT_CARD_PATTERN, response_text):
            sanitized_output = re.sub(SSN_PATTERN, "[REDACTED_SSN]", sanitized_output)
            sanitized_output = re.sub(CREDIT_CARD_PATTERN, "[REDACTED_CC]", sanitized_output)
            violations.append(
                GuardrailViolation(
                    rule_name="pii_output_leakage",
                    stage=GuardrailStage.OUTPUT,
                    reason="Output contains sensitive PII; redacted",
                    policy="privacy/pii_protection",
                    severity="MEDIUM",
                )
            )

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if any(v.severity in ("CRITICAL", "HIGH") for v in violations):
            decision = GuardrailDecision.BLOCK
            reason = violations[0].reason
            policy = violations[0].policy
        elif sanitized_output != response_text:
            decision = GuardrailDecision.SANITIZE
            reason = "Output sanitized to redact sensitive information"
            policy = "privacy/pii_protection"
        else:
            decision = GuardrailDecision.ALLOW
            reason = None
            policy = None

        metadata = GuardrailMetadata(
            guardrail_name="MockGuardrailProvider",
            stage=GuardrailStage.OUTPUT,
            decision=decision,
            reason=reason,
            policy=policy,
            latency_ms=round(latency_ms, 2),
            sanitized=decision == GuardrailDecision.SANITIZE,
            violations=violations,
        )

        return GuardrailResult(
            decision=decision,
            stage=GuardrailStage.OUTPUT,
            text=response_text,
            sanitized_text=sanitized_output if decision == GuardrailDecision.SANITIZE else None,
            violations=violations,
            metadata=metadata,
            request_id=req_id,
        )


class NemoGuardrailProvider(GuardrailProvider):
    """NVIDIA NeMo Guardrails production provider wrapping LLMRails and Colang policies."""

    def __init__(self, config_path: str | None = None):
        self.config_dir = config_path or str(GuardrailConfigLoader.get_config_dir())
        self._rails = None
        self._mock_fallback = MockGuardrailProvider()
        self._init_nemo()

    def _init_nemo(self):
        """Lazy/Safe initialize NeMo LLMRails."""
        try:
            from nemoguardrails import LLMRails, RailsConfig

            rails_config = RailsConfig.from_path(self.config_dir)
            self._rails = LLMRails(rails_config)
            logger.info("NVIDIA NeMo Guardrails successfully initialized.")
        except Exception as e:
            logger.warning(
                f"Failed to initialize NeMo LLMRails: {e}. Falling back to internal engine."
            )
            self._rails = None

    async def check_input(
        self,
        query: str,
        user_id: uuid.UUID | None = None,
        session_id: uuid.UUID | None = None,
        request_id: uuid.UUID | None = None,
    ) -> GuardrailResult:
        start_time = time.perf_counter()
        req_id = request_id or uuid.uuid4()

        # First run fast pattern validation
        mock_res = await self._mock_fallback.check_input(
            query=query, user_id=user_id, session_id=session_id, request_id=req_id
        )
        if mock_res.is_blocked:
            return mock_res

        if not self._rails:
            return mock_res

        # If NeMo rails is loaded, evaluate input rails with timeout
        try:

            async def _run_nemo():
                return await self._rails.generate_async(
                    messages=[{"role": "user", "content": query}]
                )

            res = await asyncio.wait_for(_run_nemo(), timeout=settings.GUARDRAILS_TIMEOUT_SECONDS)
            bot_text = ""
            if isinstance(res, dict):
                bot_text = res.get("content", "")
            elif isinstance(res, str):
                bot_text = res

            latency_ms = (time.perf_counter() - start_time) * 1000.0

            # If NeMo refused or triggered refusal flow
            if (
                "I cannot fulfill this request" in bot_text
                or "violates safety guidelines" in bot_text
            ):
                violation = GuardrailViolation(
                    rule_name="nemo_input_rail",
                    stage=GuardrailStage.INPUT,
                    reason="Input blocked by NeMo Guardrails policy",
                    policy="nemo/input_rails",
                    severity="HIGH",
                )
                metadata = GuardrailMetadata(
                    guardrail_name="NemoGuardrailProvider",
                    stage=GuardrailStage.INPUT,
                    decision=GuardrailDecision.BLOCK,
                    reason=violation.reason,
                    policy=violation.policy,
                    latency_ms=round(latency_ms, 2),
                    violations=[violation],
                )
                return GuardrailResult(
                    decision=GuardrailDecision.BLOCK,
                    stage=GuardrailStage.INPUT,
                    text=query,
                    violations=[violation],
                    metadata=metadata,
                    request_id=req_id,
                )

            return mock_res
        except Exception as e:
            logger.error(f"Error in NeMo check_input: {e}")
            if settings.GUARDRAILS_FAIL_CLOSED:
                raise
            return mock_res

    async def check_retrieval(
        self,
        query: str,
        contexts: list[dict[str, Any]],
        user_id: uuid.UUID | None = None,
        request_id: uuid.UUID | None = None,
    ) -> GuardrailResult:
        # Retrieval checks enforce document & memory safety
        return await self._mock_fallback.check_retrieval(
            query=query,
            contexts=contexts,
            user_id=user_id,
            request_id=request_id,
        )

    async def check_output(
        self,
        query: str,
        response_text: str,
        contexts: list[dict[str, Any]] | None = None,
        request_id: uuid.UUID | None = None,
    ) -> GuardrailResult:
        # Output checks enforce non-leakage and topic safety
        return await self._mock_fallback.check_output(
            query=query,
            response_text=response_text,
            contexts=contexts,
            request_id=request_id,
        )
