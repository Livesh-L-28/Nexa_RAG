import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from app.orchestration.models import (
    CachedContext,
    ContextBudgetConfig,
    ContextBundle,
    ContextMetadata,
    ConversationContext,
    MemoryContext,
    RAGContext,
)


class ContextProvider(ABC):
    """Abstract interface for context providers (RAG, CAG, MAG, Conversation)."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the context source (e.g. 'rag', 'cag', 'mag', 'conversation')."""

    @abstractmethod
    async def retrieve(self, query: str, **kwargs: Any) -> Sequence[Any]:
        """Retrieve contextual information relevant to the provided query."""


class ContextFusion(ABC):
    """Abstract interface for deterministic fusion of multiple context streams into a ContextBundle."""

    @abstractmethod
    def fuse(
        self,
        query: str,
        rag_context: list[RAGContext] | None = None,
        cached_context: list[CachedContext] | None = None,
        memories: list[MemoryContext] | None = None,
        conversation_history: list[ConversationContext] | None = None,
        metadata: ContextMetadata | None = None,
        budget_config: ContextBudgetConfig | None = None,
        current_user_id: uuid.UUID | str | None = None,
        **kwargs: Any,
    ) -> ContextBundle:
        """Fuse provided context streams into a unified ContextBundle."""
