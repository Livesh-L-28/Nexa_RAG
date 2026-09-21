"""Deterministic pattern-based memory extraction with secret filtering."""

import re
from datetime import datetime, timedelta, timezone

from app.memory.models import MemoryCreate, MemoryType


class MemoryExtractor:
    """Extracts high-value user preferences, instructions, and facts from messages.

    Does not depend on LLMs; uses deterministic regex patterns and rule-based validation.
    Enforces strict security filtering to prevent secret credential leakage.
    """

    SECRET_PATTERNS = [
        re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),  # OpenAI / generic secret key
        re.compile(r"ghp_[a-zA-Z0-9]{20,}", re.IGNORECASE),  # GitHub personal token
        re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.=]{20,}", re.IGNORECASE),  # Bearer token
        re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]+"),  # JWT token
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),  # Private keys
        re.compile(
            r"(?:password|passwd|pwd|secret)\s*[:=]\s*\S+", re.IGNORECASE
        ),  # Explicit password
        re.compile(
            r"(?:postgres|mysql|mongodb|redis):\/\/[^:]+:[^@]+@", re.IGNORECASE
        ),  # DB URI with password
    ]

    TRIVIAL_PHRASES = {
        "ok",
        "okay",
        "thanks",
        "thank you",
        "hello",
        "hi",
        "hey",
        "yes",
        "no",
        "got it",
        "cool",
        "understood",
        "sure",
        "bye",
    }

    def __init__(self, min_importance: float = 0.5):
        self.min_importance = min_importance

    @classmethod
    def contains_secret(cls, text: str) -> bool:
        """Check if text contains obvious credentials, tokens, or private keys."""
        for pattern in cls.SECRET_PATTERNS:
            if pattern.search(text):
                return True
        return False

    def extract(self, text: str) -> list[MemoryCreate]:
        """Extract candidate memories from user text."""
        cleaned = text.strip()
        if not cleaned or len(cleaned) < 6:
            return []

        if cleaned.lower() in self.TRIVIAL_PHRASES:
            return []

        # Enforce security filter: Reject any input containing credentials
        if self.contains_secret(cleaned):
            return []

        candidates: list[MemoryCreate] = []

        # 1. Explicit remember instruction: "Remember that...", "Please remember this:..."
        remember_match = re.search(
            r"(?i)(?:please\s+)?remember\s+(?:that\s+|this[:\s]+)?(.+)", cleaned
        )
        if remember_match:
            detail = remember_match.group(1).strip()
            # Decide if it is an instruction or project context
            if any(w in detail.lower() for w in ("always", "never", "prefer", "brief", "concise")):
                m_type = MemoryType.INSTRUCTION
            else:
                m_type = MemoryType.PROJECT_CONTEXT
            candidates.append(
                MemoryCreate(
                    content=f"Remembered: {detail}",
                    memory_type=m_type,
                    importance=0.95,
                    metadata={"source": "explicit_remember"},
                )
            )

        # 2. General instructions: "Always format...", "Explain briefly..."
        instruction_match = re.search(
            r"(?i)\b(always|never)\s+(format|use|explain|provide|respond|do)\s+(.+)", cleaned
        )
        if instruction_match and not remember_match:
            verb = instruction_match.group(2)
            rest = instruction_match.group(3).strip()
            candidates.append(
                MemoryCreate(
                    content=f"User instruction: {instruction_match.group(1).capitalize()} {verb} {rest}",
                    memory_type=MemoryType.INSTRUCTION,
                    importance=0.9,
                    metadata={"source": "rule_instruction"},
                )
            )

        # 3. Preferences: "I prefer Python over Java", "I like using FastAPI"
        pref_match = re.search(r"(?i)\bi\s+prefer\s+(?:to\s+use\s+|using\s+)?(.+)", cleaned)
        if pref_match:
            pref = pref_match.group(1).strip().rstrip(".!?")
            candidates.append(
                MemoryCreate(
                    content=f"User prefers {pref}",
                    memory_type=MemoryType.PREFERENCE,
                    importance=0.85,
                    metadata={"source": "preference"},
                )
            )

        # 4. Project context: "I'm building a FastAPI backend", "Our stack uses PostgreSQL"
        proj_match = re.search(
            r"(?i)\b(?:i\'?m|we\'?re|i\s+am|we\s+are)\s+building\s+(.+)", cleaned
        )
        if proj_match:
            proj = proj_match.group(1).strip().rstrip(".!?")
            candidates.append(
                MemoryCreate(
                    content=f"User is building {proj}",
                    memory_type=MemoryType.PROJECT_CONTEXT,
                    importance=0.85,
                    metadata={"source": "project_context"},
                )
            )

        stack_match = re.search(
            r"(?i)\b(?:my|our)\s+(?:project|stack)\s+(?:uses|is\s+built\s+with|tech\s+stack\s+is)\s+(.+)",
            cleaned,
        )
        if stack_match:
            stack = stack_match.group(1).strip().rstrip(".!?")
            candidates.append(
                MemoryCreate(
                    content=f"User project tech stack: {stack}",
                    memory_type=MemoryType.PROJECT_CONTEXT,
                    importance=0.85,
                    metadata={"source": "tech_stack"},
                )
            )

        # 5. Temporary context: "Currently debugging authentication", "For now I am testing..."
        temp_match = re.search(
            r"(?i)\b(?:currently|for\s+now|right\s+now)\s+(?:debugging|testing|investigating|working\s+on)\s+(.+)",
            cleaned,
        )
        if temp_match:
            temp_desc = temp_match.group(1).strip().rstrip(".!?")
            expires_at = datetime.now(timezone.utc) + timedelta(days=7)
            candidates.append(
                MemoryCreate(
                    content=f"User is currently focused on {temp_desc}",
                    memory_type=MemoryType.TEMPORARY_CONTEXT,
                    importance=0.6,
                    expires_at=expires_at,
                    metadata={"source": "temporary_context"},
                )
            )

        # Filter by min_importance and return unique candidates
        filtered: list[MemoryCreate] = []
        seen_content: set[str] = set()
        for cand in candidates:
            if cand.importance >= self.min_importance and cand.content not in seen_content:
                seen_content.add(cand.content)
                filtered.append(cand)

        return filtered
