"""Query analysis and signal extraction for intelligent context orchestration."""

import re
from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field


class QuerySignals(BaseModel):
    """Extracted semantic and structural signals from a user query."""

    memory_reference: bool = False
    document_reference: bool = False
    policy_reference: bool = False
    project_reference: bool = False
    conversation_reference: bool = False
    stable_knowledge_reference: bool = False
    explicit_user_reference: bool = False
    is_chit_chat: bool = False
    detected_keywords: list[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class QueryAnalyzer(ABC):
    """Abstract interface for query signal analysis."""

    @abstractmethod
    def analyze(
        self,
        query: str,
        chat_history: list[tuple[str, str]] | None = None,
    ) -> QuerySignals:
        """Analyze query and extract routing signals."""


class RuleBasedQueryAnalyzer(QueryAnalyzer):
    """Deterministic, regex and phrase-based query analyzer."""

    CHIT_CHAT_EXACT = {
        "hello",
        "hi",
        "hey",
        "thanks",
        "thank you",
        "thx",
        "bye",
        "goodbye",
        "ok",
        "okay",
        "cool",
        "understood",
        "good morning",
        "good afternoon",
        "good evening",
        "how are you",
        "what's up",
        "sup",
    }

    CHIT_CHAT_PREFIXES = (
        "hello",
        "hi ",
        "hey ",
        "thanks",
        "thank you",
        "bye",
        "good morning",
        "good afternoon",
        "good evening",
    )

    MEMORY_PATTERNS = [
        re.compile(
            r"(?i)\b(what did i (tell|say)|did i (mention|tell)|do you remember|remember (that|when|this)?|"
            r"my preferences?|what do i prefer|have i told you|my previous (instruction|setting|choice))\b"
        ),
    ]

    PROJECT_PATTERNS = [
        re.compile(
            r"(?i)\b(my|our)\s+(project|stack|backend|frontend|codebase|application|app|repo|architecture)\b"
        ),
    ]

    DOCUMENT_PATTERNS = [
        re.compile(
            r"(?i)\b(document(ation|s)?|docs?|specs?|specification|manual|guide|pdf|section|chapter|whitepaper|rfc)\b"
        ),
        re.compile(
            r"(?i)(according to|what does the|in the|from the)\s+([a-zA-Z0-9_\-\s]+)?(doc(ument)?|spec|guide|manual)"
        ),
    ]

    POLICY_PATTERNS = [
        re.compile(
            r"(?i)\b(leave policy|holiday policy|vacation policy|sick leave|security standard|security policy|"
            r"company policy|hr policy|handbook|compliance|sla|protocol|regulation)\b"
        ),
        re.compile(
            r"(?i)\b(policy|policies|standards?|guidelines?|protocols?|compliance|regulations?)\b"
        ),
    ]

    CONVERSATION_PATTERNS = [
        re.compile(
            r"(?i)\b(earlier|you said|as (mentioned|discussed)|previous (question|answer|response)|"
            r"follow[- ]?up|elaborate on that|what about that|and then|what did you mean)\b"
        ),
    ]

    EXPLICIT_USER_PATTERNS = [
        re.compile(
            r"(?i)\b(i prefer|my preference|i like|i always|i usually|i want you to always)\b"
        ),
    ]

    def analyze(
        self,
        query: str,
        chat_history: list[tuple[str, str]] | None = None,
    ) -> QuerySignals:
        """Analyze query text and conversation context to extract routing signals."""
        cleaned = query.strip()
        cleaned_lower = cleaned.lower().rstrip(".!?")
        detected_keywords: list[str] = []

        # 1. Chit-chat detection
        words = cleaned_lower.split()
        if cleaned_lower in self.CHIT_CHAT_EXACT or (
            len(words) <= 3 and any(cleaned_lower.startswith(p) for p in self.CHIT_CHAT_PREFIXES)
        ):
            detected_keywords.append("chit_chat")
            return QuerySignals(is_chit_chat=True, detected_keywords=detected_keywords)

        # 2. Memory reference
        memory_ref = False
        for p in self.MEMORY_PATTERNS:
            if p.search(cleaned):
                memory_ref = True
                detected_keywords.append("memory_ref")
                break

        # 3. Project reference
        project_ref = False
        for p in self.PROJECT_PATTERNS:
            if p.search(cleaned):
                project_ref = True
                detected_keywords.append("project_ref")
                break

        # 4. Document reference
        doc_ref = False
        for p in self.DOCUMENT_PATTERNS:
            if p.search(cleaned):
                doc_ref = True
                detected_keywords.append("doc_ref")
                break

        # 5. Policy / Stable knowledge reference
        policy_ref = False
        for p in self.POLICY_PATTERNS:
            if p.search(cleaned):
                policy_ref = True
                detected_keywords.append("policy_ref")
                break

        # 6. Conversation reference
        conv_ref = False
        for p in self.CONVERSATION_PATTERNS:
            if p.search(cleaned):
                conv_ref = True
                detected_keywords.append("conv_ref")
                break
        if (
            not conv_ref
            and chat_history
            and len(words) <= 5
            and cleaned_lower.startswith(("what about", "how about", "why"))
        ):
            conv_ref = True
            detected_keywords.append("conv_followup")

        # 7. Explicit user reference
        user_ref = False
        for p in self.EXPLICIT_USER_PATTERNS:
            if p.search(cleaned):
                user_ref = True
                detected_keywords.append("user_pref")
                break

        return QuerySignals(
            memory_reference=memory_ref,
            document_reference=doc_ref,
            policy_reference=policy_ref,
            project_reference=project_ref,
            conversation_reference=conv_ref,
            stable_knowledge_reference=policy_ref,
            explicit_user_reference=user_ref,
            is_chit_chat=False,
            detected_keywords=detected_keywords,
        )
