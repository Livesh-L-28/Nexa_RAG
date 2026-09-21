"""Context Orchestrator coordinating query analysis, policy planning, and concurrent execution."""

import asyncio
import time
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationException, AuthorizationException
from app.core.logging import logger
from app.orchestration.adapters import RAGContextAdapter
from app.orchestration.analyzer import QueryAnalyzer, RuleBasedQueryAnalyzer
from app.orchestration.fusion import DefaultContextFusion
from app.orchestration.interfaces import ContextFusion, ContextProvider
from app.orchestration.models import (
    CachedContext,
    ContextBundle,
    ContextPlan,
    ConversationContext,
    MemoryContext,
    RAGContext,
)
from app.orchestration.policies import ContextPolicy, RuleBasedContextPolicy


class RAGContextProvider(ContextProvider):
    """Bridge conforming existing RAG search/reranking to the ContextProvider interface."""

    def __init__(
        self,
        retriever_func: Callable[..., Coroutine[Any, Any, Any]] | None = None,
    ):
        self._retriever_func = retriever_func

    @property
    def source_name(self) -> str:
        return "rag"

    async def retrieve(
        self,
        query: str,
        session: AsyncSession | None = None,
        user_id: uuid.UUID | None = None,
        document_ids: list[uuid.UUID] | None = None,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
        **kwargs: Any,
    ) -> list[RAGContext]:
        """Retrieve authoritative RAG contexts using provided retrieval callable."""
        if not self._retriever_func:
            return []

        result = await self._retriever_func(
            session=session,
            processed_query=query,
            user_id=user_id,
            document_ids=document_ids,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )

        # Handle either tuple (chunks, ret_lat, rerank_lat, count) or direct chunks
        if isinstance(result, tuple) and len(result) >= 1:
            chunks = result[0]
        else:
            chunks = result

        return RAGContextAdapter.chunks_to_rag_context(chunks)


class ContextOrchestrator:
    """Intelligent Context Orchestrator deciding what context sources participate in answering a query."""

    def __init__(
        self,
        analyzer: QueryAnalyzer | None = None,
        policy: ContextPolicy | None = None,
        fusion: ContextFusion | None = None,
    ):
        self.analyzer = analyzer or RuleBasedQueryAnalyzer()
        self.policy = policy or RuleBasedContextPolicy()
        self.fusion = fusion or DefaultContextFusion()

    def plan(
        self,
        query: str,
        chat_history: list[tuple[str, str]] | None = None,
        rag_top_k: int = 5,
        memory_top_k: int = 5,
    ) -> ContextPlan:
        """Analyze query and evaluate routing policy to produce a ContextPlan."""
        signals = self.analyzer.analyze(query=query, chat_history=chat_history)
        return self.policy.evaluate(
            query=query,
            signals=signals,
            chat_history=chat_history,
            rag_top_k=rag_top_k,
            memory_top_k=memory_top_k,
        )

    async def execute_plan(
        self,
        plan: ContextPlan,
        query: str,
        user_id: uuid.UUID,
        rag_provider: ContextProvider | None = None,
        cag_provider: ContextProvider | None = None,
        mag_provider: ContextProvider | None = None,
        conversation_history: list[ConversationContext] | None = None,
        session: AsyncSession | None = None,
        **kwargs: Any,
    ) -> tuple[ContextBundle, dict[str, Any]]:
        """Concurrently execute selected context providers with failure isolation."""
        exec_start = time.perf_counter()
        provider_failures: list[str] = []
        provider_latencies: dict[str, float] = {}

        tasks: list[Coroutine[Any, Any, Any]] = []
        active_sources: list[str] = []

        # 1. Dispatch RAG
        if plan.use_rag and rag_provider:
            active_sources.append("rag")
            tasks.append(
                rag_provider.retrieve(
                    query=query,
                    session=session,
                    user_id=user_id,
                    top_k=plan.rag_top_k,
                    **kwargs,
                )
            )

        # 2. Dispatch CAG
        if plan.use_cag and cag_provider:
            active_sources.append("cag")
            tasks.append(
                cag_provider.retrieve(
                    query=query,
                    user_id=user_id,
                    **kwargs,
                )
            )

        # 3. Dispatch MAG
        if plan.use_mag and mag_provider:
            active_sources.append("mag")
            tasks.append(
                mag_provider.retrieve(
                    query=query,
                    session=session,
                    user_id=user_id,
                    top_k=plan.memory_top_k,
                    **kwargs,
                )
            )

        # Run selected providers concurrently
        results: list[Any] = []
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

        rag_contexts: list[RAGContext] = []
        cag_contexts: list[CachedContext] = []
        mag_contexts: list[MemoryContext] = []

        for source_name, res in zip(active_sources, results, strict=False):
            # Strict security enforcement: Authorization/Authentication exceptions are never swallowed
            if isinstance(res, (AuthorizationException, AuthenticationException)):
                raise res

            # Operational failure isolation: Provider failure does not destroy whole request
            if isinstance(res, Exception):
                logger.warning(f"Provider {source_name} failed: {res}")
                provider_failures.append(f"{source_name}: {res}")
                continue

            if source_name == "rag" and isinstance(res, list):
                rag_contexts = res
            elif source_name == "cag" and isinstance(res, list):
                cag_contexts = res
            elif source_name == "mag" and isinstance(res, list):
                mag_contexts = res

        # 4. Context Fusion
        bundle = self.fusion.fuse(
            query=query,
            rag_context=rag_contexts,
            cached_context=cag_contexts,
            memories=mag_contexts,
            conversation_history=conversation_history if plan.use_conversation else [],
        )

        routing_latency_ms = (time.perf_counter() - exec_start) * 1000.0
        bundle.metadata.routing_latency_ms = round(routing_latency_ms, 2)
        bundle.metadata.routing_confidence = plan.confidence
        bundle.metadata.routing_reason = plan.reason
        bundle.metadata.provider_failures = provider_failures

        info = {
            "plan": plan,
            "routing_latency_ms": round(routing_latency_ms, 2),
            "provider_failures": provider_failures,
            "provider_latencies": provider_latencies,
            "selected_sources": plan.selected_sources,
        }

        return bundle, info

    async def orchestrate(
        self,
        query: str,
        user_id: uuid.UUID,
        rag_provider: ContextProvider | None = None,
        cag_provider: ContextProvider | None = None,
        mag_provider: ContextProvider | None = None,
        chat_history: list[tuple[str, str]] | None = None,
        session: AsyncSession | None = None,
        rag_top_k: int = 5,
        memory_top_k: int = 5,
        **kwargs: Any,
    ) -> tuple[ContextBundle, ContextPlan]:
        """Convenience end-to-end pipeline method: analyze -> plan -> execute -> fuse."""
        plan = self.plan(
            query=query,
            chat_history=chat_history,
            rag_top_k=rag_top_k,
            memory_top_k=memory_top_k,
        )
        conv_contexts = RAGContextAdapter.history_to_conversation_context(chat_history)
        bundle, _ = await self.execute_plan(
            plan=plan,
            query=query,
            user_id=user_id,
            rag_provider=rag_provider,
            cag_provider=cag_provider,
            mag_provider=mag_provider,
            conversation_history=conv_contexts,
            session=session,
            **kwargs,
        )
        return bundle, plan
