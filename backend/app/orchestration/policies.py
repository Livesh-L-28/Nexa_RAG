"""Context orchestration routing policy engine."""

from abc import ABC, abstractmethod

from app.orchestration.analyzer import QuerySignals
from app.orchestration.models import ContextDecision, ContextPlan, ContextSource


class ContextPolicy(ABC):
    """Abstract policy interface determining which context sources should participate."""

    @abstractmethod
    def evaluate(
        self,
        query: str,
        signals: QuerySignals,
        chat_history: list[tuple[str, str]] | None = None,
        rag_top_k: int = 5,
        memory_top_k: int = 5,
    ) -> ContextPlan:
        """Evaluate signals and construct a typed ContextPlan."""


class RuleBasedContextPolicy(ContextPolicy):
    """Deterministic, explainable routing policy based on query signals."""

    def evaluate(
        self,
        query: str,
        signals: QuerySignals,
        chat_history: list[tuple[str, str]] | None = None,
        rag_top_k: int = 5,
        memory_top_k: int = 5,
    ) -> ContextPlan:
        """Construct ContextPlan using deterministic priority and signal matching rules."""
        # 1. Chit-chat: Bypass external retrieval completely
        if signals.is_chit_chat:
            decisions = [
                ContextDecision(
                    source=ContextSource.RAG,
                    enabled=False,
                    confidence=0.95,
                    reason="Conversational greeting/filler does not require document retrieval",
                ),
                ContextDecision(
                    source=ContextSource.CAG,
                    enabled=False,
                    confidence=0.95,
                    reason="Conversational greeting/filler does not require cached knowledge",
                ),
                ContextDecision(
                    source=ContextSource.MAG,
                    enabled=False,
                    confidence=0.95,
                    reason="Conversational greeting/filler does not require long-term memory",
                ),
                ContextDecision(
                    source=ContextSource.CONVERSATION,
                    enabled=True,
                    confidence=0.95,
                    reason="Retain conversational dialogue context",
                ),
            ]
            return ContextPlan(
                use_rag=False,
                use_cag=False,
                use_mag=False,
                use_conversation=True,
                rag_top_k=rag_top_k,
                memory_top_k=memory_top_k,
                confidence=0.95,
                reason="Conversational greeting or chit-chat does not require external retrieval",
                decisions=decisions,
            )

        # 2. Evaluate specific context sources
        use_mag = False
        use_rag = False
        use_cag = False
        use_conv = True

        mag_reasons: list[str] = []
        rag_reasons: list[str] = []
        cag_reasons: list[str] = []

        if signals.memory_reference:
            use_mag = True
            mag_reasons.append("explicit reference to user memory/preferences")
        if signals.project_reference:
            use_mag = True
            mag_reasons.append("reference to ongoing project context or tech stack")
        if signals.explicit_user_reference and not signals.document_reference:
            use_mag = True
            mag_reasons.append("explicit reference to user preferences")

        if signals.document_reference:
            use_rag = True
            rag_reasons.append("explicit reference to enterprise documentation or files")

        if signals.policy_reference or signals.stable_knowledge_reference:
            use_cag = True
            cag_reasons.append("reference to organization policies or standards")

        # 3. Fallback behavior: If no retrieval source was activated, default to RAG for knowledge query
        is_fallback = not (use_mag or use_rag or use_cag)
        if is_fallback:
            use_rag = True
            rag_reasons.append("default fallback to document retrieval for knowledge-seeking query")

        # 4. Compute confidence & aggregate reasons
        active_reasons: list[str] = []
        if use_rag:
            active_reasons.extend(rag_reasons)
        if use_cag:
            active_reasons.extend(cag_reasons)
        if use_mag:
            active_reasons.extend(mag_reasons)

        if is_fallback:
            overall_confidence = 0.65
            main_reason = (
                "Default fallback to authoritative document retrieval for general knowledge query"
            )
        else:
            overall_confidence = 0.90 if len(active_reasons) > 1 else 0.88
            main_reason = "; ".join(active_reasons).capitalize()

        decisions = [
            ContextDecision(
                source=ContextSource.RAG,
                enabled=use_rag,
                confidence=overall_confidence if use_rag else 0.85,
                reason="; ".join(rag_reasons) if use_rag else "No document reference detected",
            ),
            ContextDecision(
                source=ContextSource.CAG,
                enabled=use_cag,
                confidence=overall_confidence if use_cag else 0.85,
                reason="; ".join(cag_reasons)
                if use_cag
                else "No policy or stable reference detected",
            ),
            ContextDecision(
                source=ContextSource.MAG,
                enabled=use_mag,
                confidence=overall_confidence if use_mag else 0.85,
                reason="; ".join(mag_reasons)
                if use_mag
                else "No user/project memory reference detected",
            ),
            ContextDecision(
                source=ContextSource.CONVERSATION,
                enabled=use_conv,
                confidence=0.95,
                reason="Multi-turn conversational context enabled",
            ),
        ]

        return ContextPlan(
            use_rag=use_rag,
            use_cag=use_cag,
            use_mag=use_mag,
            use_conversation=use_conv,
            rag_top_k=rag_top_k,
            memory_top_k=memory_top_k,
            confidence=overall_confidence,
            reason=main_reason,
            decisions=decisions,
        )
