"""Context Orchestration package for NexaRAG.

Provides the unified ContextBundle contract, context priorities, and fusion interfaces.
"""

from app.orchestration.adapters import RAGContextAdapter
from app.orchestration.analyzer import (
    QueryAnalyzer,
    QuerySignals,
    RuleBasedQueryAnalyzer,
)
from app.orchestration.fusion import DefaultContextFusion, TokenEstimator
from app.orchestration.interfaces import ContextFusion, ContextProvider
from app.orchestration.models import (
    CachedContext,
    ContextBudgetConfig,
    ContextBundle,
    ContextDecision,
    ContextMetadata,
    ContextPlan,
    ContextPriority,
    ContextSource,
    ConversationContext,
    DroppedContext,
    MemoryContext,
    NormalizedContext,
    RAGContext,
)
from app.orchestration.orchestrator import (
    ContextOrchestrator,
    RAGContextProvider,
)
from app.orchestration.policies import (
    ContextPolicy,
    RuleBasedContextPolicy,
)

__all__ = [
    "ContextBundle",
    "ContextSource",
    "ContextPriority",
    "RAGContext",
    "CachedContext",
    "MemoryContext",
    "ConversationContext",
    "NormalizedContext",
    "DroppedContext",
    "ContextBudgetConfig",
    "ContextMetadata",
    "ContextDecision",
    "ContextPlan",
    "ContextProvider",
    "ContextFusion",
    "DefaultContextFusion",
    "TokenEstimator",
    "RAGContextAdapter",
    "QuerySignals",
    "QueryAnalyzer",
    "RuleBasedQueryAnalyzer",
    "ContextPolicy",
    "RuleBasedContextPolicy",
    "ContextOrchestrator",
    "RAGContextProvider",
]
