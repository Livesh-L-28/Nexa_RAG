"""Central RAG Pipeline orchestrator with hybrid retrieval, reranking, and LLM synthesis."""

import json
import time
import uuid
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.cag import CAGContextProvider, get_cag_manager
from app.core.config import get_settings
from app.core.logging import logger
from app.database.repositories.chat_repo import ChatRepository
from app.database.repositories.log_repo import RetrievalLogRepository
from app.embeddings.service import EmbeddingService
from app.guardrails.service import GuardrailService, get_guardrail_service
from app.llm.base import BaseLLM
from app.llm.exceptions import sanitize_error_message
from app.llm.factory import get_llm
from app.memory import MAGContextProvider, MemoryManager
from app.observability import (
    EventType,
    ObservabilityEvent,
    PipelineMetrics,
    Timer,
    get_metrics_recorder,
    get_observability_logger,
)
from app.orchestration import (
    ContextFusion,
    ContextOrchestrator,
    ContextPlan,
    DefaultContextFusion,
    RAGContextAdapter,
)
from app.orchestration.fusion import TokenEstimator
from app.orchestration.models import CachedContext, MemoryContext
from app.rag.context_builder import ContextBuilder
from app.rag.prompt_builder import PromptBuilder
from app.rag.query_processor import QueryProcessor
from app.retrieval.hybrid_search import HybridSearch
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.vector_search import ScoredChunk
from app.schemas.chat import ChatResponse, RetrievalMetadata

settings = get_settings()


class RAGPipeline:
    """Orchestrates end-to-end RAG workflows: ingestion -> retrieval -> rerank -> synthesis."""

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        llm: BaseLLM | None = None,
        reranker: CrossEncoderReranker | None = None,
        context_fusion: ContextFusion | None = None,
        cag_provider: CAGContextProvider | None = None,
        cag_enabled: bool = True,
        mag_provider: MAGContextProvider | None = None,
        mag_enabled: bool = True,
        orchestrator: ContextOrchestrator | None = None,
        routing_enabled: bool = False,
        guardrail_service: GuardrailService | None = None,
    ):
        self.embedding_service = embedding_service or EmbeddingService()
        self.llm = llm or get_llm()
        self.reranker = reranker or CrossEncoderReranker()
        self.context_builder = ContextBuilder()
        self.fusion = context_fusion or DefaultContextFusion()
        self.cag_enabled = cag_enabled
        self.cag_provider = cag_provider or (
            CAGContextProvider(get_cag_manager()) if cag_enabled else None
        )
        self.mag_enabled = mag_enabled
        self.mag_provider = mag_provider or (
            MAGContextProvider(MemoryManager()) if mag_enabled else None
        )
        self.orchestrator = orchestrator or ContextOrchestrator()
        self.routing_enabled = routing_enabled
        self.guardrails = guardrail_service or get_guardrail_service()

    async def _retrieve_and_rerank(
        self,
        session: AsyncSession,
        processed_query: str,
        user_id: uuid.UUID,
        document_ids: list[uuid.UUID] | None = None,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
    ) -> tuple[list[ScoredChunk], float, float, int]:
        """Perform query embedding, hybrid search, and cross-encoder reranking."""
        k = top_k or settings.TOP_K
        threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else settings.SIMILARITY_THRESHOLD
        )
        top_candidates = max(settings.TOP_N_CANDIDATES, k * 2)

        # 1. Embed query
        query_vector = self.embedding_service.embed_query(processed_query)

        # 2. Hybrid search (pgvector cosine + in-memory BM25)
        retrieval_start = time.perf_counter()
        hybrid_search = HybridSearch(session=session)
        candidates = await hybrid_search.search(
            query=processed_query,
            query_vector=query_vector,
            user_id=user_id,
            document_ids=document_ids,
            top_candidates=top_candidates,
            alpha=settings.HYBRID_ALPHA,
            similarity_threshold=threshold,
        )
        retrieval_latency_ms = (time.perf_counter() - retrieval_start) * 1000.0

        candidate_count = len(candidates)

        # 3. Cross-Encoder reranker
        rerank_start = time.perf_counter()
        reranked_chunks = self.reranker.rerank(
            query=processed_query,
            candidates=candidates,
            top_k=k,
        )
        reranking_latency_ms = (time.perf_counter() - rerank_start) * 1000.0

        # Attach authenticated user_id for downstream ContextFusion isolation checks
        for c in reranked_chunks:
            c.metadata["user_id"] = str(user_id)

        return reranked_chunks, retrieval_latency_ms, reranking_latency_ms, candidate_count

    async def query(
        self,
        session: AsyncSession,
        query: str,
        user_id: uuid.UUID,
        session_id: uuid.UUID | None = None,
        document_ids: list[uuid.UUID] | None = None,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
        chat_history: list[tuple[str, str]] | None = None,
        context_plan: ContextPlan | None = None,
        routing_enabled: bool | None = None,
        request_id: uuid.UUID | None = None,
    ) -> ChatResponse:
        """Run complete synchronous RAG pipeline and record observability metrics."""
        total_timer = Timer()
        req_id = request_id or uuid.uuid4()
        obs_logger = get_observability_logger()
        metrics_rec = get_metrics_recorder()

        chat_repo = ChatRepository(session)
        log_repo = RetrievalLogRepository(session)

        # Ensure session exists or create new
        if not session_id:
            first_words = " ".join(query.strip().split()[:5])
            title = f"{first_words}..." if len(query.strip().split()) > 5 else first_words
            chat_session = await chat_repo.create_session(user_id=user_id, title=title)
            session_id = chat_session.id

        # Save user message
        await chat_repo.add_message(
            session_id=session_id,
            role="user",
            content=query,
        )

        obs_logger.log_request_started(request_id=req_id, session_id=session_id, user_id=user_id)
        metrics_rec.record_event(
            ObservabilityEvent(
                event=EventType.REQUEST_STARTED,
                request_id=req_id,
                session_id=session_id,
                data={"user_id": str(user_id)},
            )
        )

        # 1. Input Guardrail Evaluation
        input_guard_timer = Timer()
        input_guard_res = await self.guardrails.input_guard.evaluate(
            query=query,
            user_id=user_id,
            session_id=session_id,
            request_id=req_id,
        )
        input_guard_latency_ms = input_guard_timer.stop()
        metrics_rec.increment("guardrail_checks_total")
        metrics_rec.observe("guardrail_latency", input_guard_latency_ms)

        obs_logger.log_stage_completed(
            EventType.INPUT_GUARDRAIL_COMPLETED,
            request_id=req_id,
            session_id=session_id,
            decision=input_guard_res.decision.value,
            latency_ms=input_guard_latency_ms,
        )

        if input_guard_res.is_blocked:
            metrics_rec.increment("guardrail_blocked_total")
            metrics_rec.increment("guardrail_input_violations_total")
            obs_logger.log_stage_completed(
                EventType.GUARDRAIL_BLOCKED,
                request_id=req_id,
                session_id=session_id,
                stage="INPUT",
                reason=input_guard_res.metadata.reason,
            )
            blocked_msg = (
                "I cannot fulfill this request because it violates application safety guidelines."
            )
            await chat_repo.add_message(
                session_id=session_id,
                role="assistant",
                content=blocked_msg,
                sources=[],
            )
            total_lat = total_timer.stop()
            meta = RetrievalMetadata(
                retrieval_method="none",
                candidates_count=0,
                top_k=0,
                reranking_enabled=False,
                retrieval_latency_ms=0.0,
                reranking_latency_ms=0.0,
                llm_latency_ms=0.0,
                total_latency_ms=round(total_lat, 2),
                guardrails_enabled=True,
                guardrail_input_decision="BLOCK",
                guardrail_latency_ms=round(input_guard_latency_ms, 2),
                guardrail_violations=[v.reason for v in input_guard_res.violations],
                request_id=req_id,
            )
            return ChatResponse(
                session_id=session_id,
                query=query,
                answer=blocked_msg,
                sources=[],
                retrieved_chunks=[],
                metadata=meta,
                request_id=req_id,
            )

        if input_guard_res.is_sanitized:
            metrics_rec.increment("guardrail_sanitized_total")
            query = input_guard_res.safe_text
        else:
            metrics_rec.increment("guardrail_allowed_total")

        # Query preprocessing & conversational expansion
        query_timer = Timer()
        processed_query = QueryProcessor.rewrite_with_history(query, chat_history)
        query_latency_ms = query_timer.stop()
        obs_logger.log_stage_completed(
            EventType.QUERY_PROCESSED,
            request_id=req_id,
            session_id=session_id,
            latency_ms=query_latency_ms,
        )

        # Evaluate ContextPlan if routing is active
        use_routing = routing_enabled if routing_enabled is not None else self.routing_enabled
        plan: ContextPlan | None = None
        routing_timer = Timer(autostart=False)
        if use_routing or context_plan is not None:
            routing_timer.start()
            plan = context_plan or self.orchestrator.plan(
                query=query,
                chat_history=chat_history,
                rag_top_k=top_k or settings.TOP_K,
            )
            routing_latency_ms = routing_timer.stop()
        else:
            routing_latency_ms = 0.0

        selected_sources = plan.selected_sources if plan else ["rag", "cag", "mag", "conversation"]
        obs_logger.log_stage_completed(
            EventType.CONTEXT_SOURCES_SELECTED,
            request_id=req_id,
            session_id=session_id,
            selected_sources=selected_sources,
            routing_latency_ms=routing_latency_ms,
        )

        # Retrieval and reranking (RAG)
        chunks: list[ScoredChunk] = []
        retrieval_latency: float = 0.0
        reranking_latency: float = 0.0
        candidate_count: int = 0

        should_fetch_rag = plan.use_rag if plan is not None else True
        if should_fetch_rag:
            (
                chunks,
                retrieval_latency,
                reranking_latency,
                candidate_count,
            ) = await self._retrieve_and_rerank(
                session=session,
                processed_query=processed_query,
                user_id=user_id,
                document_ids=document_ids,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
            )
            obs_logger.log_stage_completed(
                EventType.RAG_COMPLETED,
                request_id=req_id,
                session_id=session_id,
                candidates_count=candidate_count,
                reranked_count=len(chunks),
                retrieval_latency_ms=retrieval_latency,
                reranking_latency_ms=reranking_latency,
            )

        # CAG context lookup
        cached_contexts: list[CachedContext] = []
        cag_latency_ms: float = 0.0
        should_fetch_cag = plan.use_cag if plan is not None else True
        if self.cag_enabled and self.cag_provider and should_fetch_cag:
            cag_timer = Timer()
            cached_contexts = await self.cag_provider.retrieve(
                query=query,
                user_id=user_id,
            )
            cag_latency_ms = cag_timer.stop()
            obs_logger.log_stage_completed(
                EventType.CAG_COMPLETED,
                request_id=req_id,
                session_id=session_id,
                count=len(cached_contexts),
                latency_ms=cag_latency_ms,
            )

        # MAG context lookup
        memory_contexts: list[MemoryContext] = []
        mag_latency_ms: float = 0.0
        should_fetch_mag = plan.use_mag if plan is not None else True
        if self.mag_enabled and self.mag_provider and should_fetch_mag:
            mag_timer = Timer()
            memory_contexts = await self.mag_provider.retrieve(
                query=query,
                user_id=user_id,
                session=session,
                top_k=plan.memory_top_k if plan else None,
            )
            mag_latency_ms = mag_timer.stop()
            obs_logger.log_stage_completed(
                EventType.MAG_COMPLETED,
                request_id=req_id,
                session_id=session_id,
                count=len(memory_contexts),
                latency_ms=mag_latency_ms,
            )

        # Build grounded context and ContextBundle
        rag_contexts = RAGContextAdapter.chunks_to_rag_context(chunks)
        conv_contexts = (
            RAGContextAdapter.history_to_conversation_context(chat_history)
            if (plan is None or plan.use_conversation)
            else []
        )

        fusion_timer = Timer()
        bundle = self.fusion.fuse(
            query=query,
            rag_context=rag_contexts,
            cached_context=cached_contexts,
            memories=memory_contexts,
            conversation_history=conv_contexts,
            current_user_id=user_id,
        )
        fusion_latency_ms = fusion_timer.stop()
        obs_logger.log_stage_completed(
            EventType.FUSION_COMPLETED,
            request_id=req_id,
            session_id=session_id,
            total_items=bundle.metadata.total_context_items,
            selected_items=bundle.metadata.context_count,
            deduplicated_items=bundle.metadata.deduplicated_items,
            dropped_items=bundle.metadata.dropped_items,
            estimated_tokens=bundle.metadata.estimated_tokens,
            latency_ms=fusion_latency_ms,
        )

        # 2. Retrieval Guardrail Evaluation
        retrieval_guard_timer = Timer()
        contexts_to_check = [
            {
                "content": c.content,
                "user_id": c.metadata.get("user_id"),
                "document_id": str(c.document_id),
            }
            for c in chunks
        ]
        # Include cached and memory contexts in inspection
        for cached in cached_contexts:
            contexts_to_check.append({"content": cached.content, "user_id": str(user_id)})
        for mem in memory_contexts:
            contexts_to_check.append({"content": mem.content, "user_id": str(user_id)})

        retrieval_guard_res = await self.guardrails.retrieval_guard.evaluate(
            query=query,
            contexts=contexts_to_check,
            user_id=user_id,
            request_id=req_id,
        )
        retrieval_guard_latency_ms = retrieval_guard_timer.stop()
        metrics_rec.increment("guardrail_checks_total")
        metrics_rec.observe("guardrail_latency", retrieval_guard_latency_ms)

        obs_logger.log_stage_completed(
            EventType.RETRIEVAL_GUARDRAIL_COMPLETED,
            request_id=req_id,
            session_id=session_id,
            decision=retrieval_guard_res.decision.value,
            latency_ms=retrieval_guard_latency_ms,
        )

        if retrieval_guard_res.is_blocked:
            metrics_rec.increment("guardrail_blocked_total")
            metrics_rec.increment("guardrail_retrieval_violations_total")
            obs_logger.log_stage_completed(
                EventType.GUARDRAIL_BLOCKED,
                request_id=req_id,
                session_id=session_id,
                stage="RETRIEVAL",
                reason=retrieval_guard_res.metadata.reason,
            )
            blocked_msg = "Retrieved content failed security validation policies."
            await chat_repo.add_message(
                session_id=session_id,
                role="assistant",
                content=blocked_msg,
                sources=[],
            )
            total_lat = total_timer.stop()
            meta = RetrievalMetadata(
                retrieval_method="none",
                candidates_count=candidate_count,
                top_k=0,
                reranking_enabled=False,
                retrieval_latency_ms=round(retrieval_latency, 2),
                reranking_latency_ms=round(reranking_latency, 2),
                llm_latency_ms=0.0,
                total_latency_ms=round(total_lat, 2),
                guardrails_enabled=True,
                guardrail_input_decision=input_guard_res.decision.value,
                guardrail_retrieval_decision="BLOCK",
                guardrail_latency_ms=round(input_guard_latency_ms + retrieval_guard_latency_ms, 2),
                guardrail_violations=[v.reason for v in retrieval_guard_res.violations],
                request_id=req_id,
            )
            return ChatResponse(
                session_id=session_id,
                query=query,
                answer=blocked_msg,
                sources=[],
                retrieved_chunks=[],
                metadata=meta,
                request_id=req_id,
            )
        else:
            metrics_rec.increment("guardrail_allowed_total")

        prompt_timer = Timer()
        built_context = self.context_builder.build_context(chunks)
        system_prompt = PromptBuilder.build_system_prompt()
        user_prompt = PromptBuilder.build_user_prompt_from_bundle(
            bundle=bundle,
            formatted_context=built_context.formatted_context,
        )
        prompt_latency_ms = prompt_timer.stop()
        estimated_prompt_tokens = TokenEstimator.estimate(system_prompt + user_prompt)
        obs_logger.log_stage_completed(
            EventType.PROMPT_BUILT,
            request_id=req_id,
            session_id=session_id,
            estimated_tokens=estimated_prompt_tokens,
            latency_ms=prompt_latency_ms,
        )

        # Extract LLM observability fields safely (avoid MagicMock auto-attributes)
        raw_prov = getattr(self.llm, "provider_name", "mock")
        llm_prov_str = raw_prov if isinstance(raw_prov, str) else "mock"

        raw_mod = getattr(self.llm, "model_name", "mock-llm-v1")
        llm_mod_str = raw_mod if isinstance(raw_mod, str) else "mock-llm-v1"

        # LLM generation
        llm_timer = Timer()
        obs_logger.log_stage_completed(
            EventType.LLM_STARTED,
            request_id=req_id,
            session_id=session_id,
            provider=llm_prov_str,
            model=llm_mod_str,
        )

        llm_response = None
        if hasattr(self.llm, "generate_response"):
            try:
                llm_response = await self.llm.generate_response(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                )
                answer = llm_response.text
            except Exception:
                answer = await self.llm.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                )
        else:
            answer = await self.llm.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )
        llm_latency_ms = llm_timer.stop()

        obs_logger.log_stage_completed(
            EventType.LLM_COMPLETED,
            request_id=req_id,
            session_id=session_id,
            provider=llm_prov_str,
            model=llm_mod_str,
            latency_ms=llm_latency_ms,
        )

        # 3. Output Guardrail Evaluation
        output_guard_timer = Timer()
        output_guard_res = await self.guardrails.output_guard.evaluate(
            query=query,
            response_text=answer,
            contexts=contexts_to_check,
            request_id=req_id,
        )
        output_guard_latency_ms = output_guard_timer.stop()
        metrics_rec.increment("guardrail_checks_total")
        metrics_rec.observe("guardrail_latency", output_guard_latency_ms)

        obs_logger.log_stage_completed(
            EventType.OUTPUT_GUARDRAIL_COMPLETED,
            request_id=req_id,
            session_id=session_id,
            decision=output_guard_res.decision.value,
            latency_ms=output_guard_latency_ms,
        )

        total_latency_ms = total_timer.stop()

        output_violations = []
        if output_guard_res.is_blocked:
            metrics_rec.increment("guardrail_blocked_total")
            metrics_rec.increment("guardrail_output_violations_total")
            obs_logger.log_stage_completed(
                EventType.GUARDRAIL_BLOCKED,
                request_id=req_id,
                session_id=session_id,
                stage="OUTPUT",
                reason=output_guard_res.metadata.reason,
            )
            answer = "I cannot provide this response because it violates safety and non-disclosure policies."
            output_violations = [v.reason for v in output_guard_res.violations]
            built_context.citations = []
        elif output_guard_res.is_sanitized:
            metrics_rec.increment("guardrail_sanitized_total")
            answer = output_guard_res.safe_text
        else:
            metrics_rec.increment("guardrail_allowed_total")

        # Save assistant message with citations
        sources_payload = [c.model_dump(mode="json") for c in built_context.citations]
        await chat_repo.add_message(
            session_id=session_id,
            role="assistant",
            content=answer,
            sources=sources_payload,
        )

        # Selectively extract and persist high-value user memories from query
        if self.mag_enabled and self.mag_provider:
            try:
                await self.mag_provider.extract_and_save(
                    session=session,
                    user_id=user_id,
                    text=query,
                )
            except Exception as e:
                logger.warning(f"Error during memory extraction: {e}")

        in_toks = None
        out_toks = None
        tot_toks = None
        finish_reason = None
        if llm_response and getattr(llm_response, "usage", None):
            usage_obj = llm_response.usage
            if isinstance(getattr(usage_obj, "input_tokens", None), int):
                in_toks = usage_obj.input_tokens
            if isinstance(getattr(usage_obj, "output_tokens", None), int):
                out_toks = usage_obj.output_tokens
            if isinstance(getattr(usage_obj, "total_tokens", None), int):
                tot_toks = usage_obj.total_tokens
        if llm_response and getattr(llm_response, "finish_reason", None):
            finish_reason = getattr(llm_response, "finish_reason", None)

        # RAG quality statistics
        scores = [c.score for c in chunks if c.score is not None]
        top_score = max(scores) if scores else None
        min_score = min(scores) if scores else None
        avg_score = round(sum(scores) / len(scores), 4) if scores else None
        unique_docs = len({c.document_id for c in chunks})
        unique_pages = len(
            {(c.document_id, c.page_number) for c in chunks if c.page_number is not None}
        )
        citation_count = len(built_context.citations)

        # Tally dropped context reasons
        dropped_reasons: dict[str, int] = {}
        for dc in bundle.metadata.dropped_contexts:
            dropped_reasons[dc.reason] = dropped_reasons.get(dc.reason, 0) + 1

        # Build telemetry model and record in metrics recorder
        pipeline_metrics = PipelineMetrics(
            request_id=req_id,
            session_id=session_id,
            user_id=user_id,
            query_processing_latency_ms=round(query_latency_ms, 2),
            routing_latency_ms=round(routing_latency_ms, 2),
            retrieval_latency_ms=round(retrieval_latency, 2),
            reranking_latency_ms=round(reranking_latency, 2),
            cag_latency_ms=round(cag_latency_ms, 2),
            mag_latency_ms=round(mag_latency_ms, 2),
            fusion_latency_ms=round(fusion_latency_ms, 2),
            prompt_build_latency_ms=round(prompt_latency_ms, 2),
            llm_generation_latency_ms=round(llm_latency_ms, 2),
            total_latency_ms=round(total_latency_ms, 2),
            rag_selected=bool(chunks),
            hybrid_candidates_count=candidate_count,
            reranked_chunks_count=len(chunks),
            top_score=top_score,
            average_score=avg_score,
            minimum_score=min_score,
            unique_documents_count=unique_docs,
            unique_pages_count=unique_pages,
            citation_count=citation_count,
            cag_selected=bool(cached_contexts),
            cag_cache_hit=bool(cached_contexts),
            cag_cache_miss=self.cag_enabled and should_fetch_cag and not bool(cached_contexts),
            cag_items_used=len(cached_contexts),
            cag_context_tokens=sum(TokenEstimator.estimate(c.content) for c in cached_contexts),
            mag_selected=bool(memory_contexts),
            memories_retrieved=len(memory_contexts),
            memories_used=len(memory_contexts),
            memory_types=[m.memory_type for m in memory_contexts],
            routing_enabled=plan is not None,
            routing_confidence=plan.confidence if plan else 1.0,
            routing_reason=plan.reason if plan else "additive",
            selected_sources=plan.selected_sources if plan else bundle.selected_sources,
            contexts_received=bundle.metadata.total_context_items,
            contexts_selected=bundle.metadata.context_count,
            contexts_deduplicated=bundle.metadata.deduplicated_items,
            contexts_dropped=bundle.metadata.dropped_items,
            estimated_tokens=bundle.metadata.estimated_tokens,
            token_budget=bundle.metadata.token_budget,
            dropped_reasons=dropped_reasons,
            estimated_input_tokens=estimated_prompt_tokens,
            llm_provider=llm_prov_str,
            llm_model=llm_mod_str,
            actual_input_tokens=in_toks,
            actual_output_tokens=out_toks,
            actual_total_tokens=tot_toks,
            finish_reason=finish_reason,
        )
        metrics_rec.record_pipeline_metrics(pipeline_metrics)
        obs_logger.log_stage_completed(
            EventType.REQUEST_COMPLETED,
            request_id=req_id,
            session_id=session_id,
            total_latency_ms=round(total_latency_ms, 2),
        )

        # Persist retrieval observability log
        await log_repo.create_log(
            session_id=session_id,
            user_id=user_id,
            request_id=req_id,
            metadata_=pipeline_metrics.to_safe_summary(),
            query=query,
            retrieved_chunk_ids=[str(cid) for cid in built_context.chunk_ids],
            retrieval_method="hybrid_rerank"
            if (chunks and self.reranker.enabled)
            else ("hybrid" if chunks else "none"),
            candidate_count=candidate_count,
            top_k=len(chunks),
            reranking_enabled=self.reranker.enabled if chunks else False,
            retrieval_latency_ms=round(retrieval_latency, 2),
            reranking_latency_ms=round(reranking_latency, 2),
            llm_latency_ms=round(llm_latency_ms, 2),
            total_latency_ms=round(total_latency_ms, 2),
        )

        metadata = RetrievalMetadata(
            retrieval_method="hybrid_rerank"
            if (chunks and self.reranker.enabled)
            else ("hybrid" if chunks else "none"),
            candidates_count=candidate_count,
            top_k=len(chunks),
            reranking_enabled=self.reranker.enabled if chunks else False,
            retrieval_latency_ms=round(retrieval_latency, 2),
            reranking_latency_ms=round(reranking_latency, 2),
            llm_latency_ms=round(llm_latency_ms, 2),
            total_latency_ms=round(total_latency_ms, 2),
            rag_selected=bool(chunks),
            cag_enabled=self.cag_enabled,
            cag_selected=bool(cached_contexts),
            cache_hit=bool(cached_contexts),
            cache_miss=self.cag_enabled and should_fetch_cag and not bool(cached_contexts),
            cache_context_count=len(cached_contexts),
            cache_context_size=sum(len(c.content) for c in cached_contexts),
            mag_enabled=self.mag_enabled,
            mag_selected=bool(memory_contexts),
            memories_retrieved=len(memory_contexts),
            memories_used=len(memory_contexts),
            memory_retrieval_latency_ms=round(mag_latency_ms, 2),
            memory_types=[m.memory_type for m in memory_contexts],
            routing_enabled=plan is not None,
            routing_latency_ms=round(routing_latency_ms, 2),
            routing_confidence=plan.confidence if plan else 1.0,
            routing_reason=plan.reason if plan else "additive",
            selected_sources=plan.selected_sources if plan else bundle.selected_sources,
            provider_failures=[],
            llm_provider=llm_prov_str,
            llm_model=llm_mod_str,
            input_tokens=in_toks,
            output_tokens=out_toks,
            total_tokens=tot_toks,
            request_id=req_id,
            prompt_build_latency_ms=round(prompt_latency_ms, 2),
            estimated_input_tokens=estimated_prompt_tokens,
            dropped_contexts_count=bundle.metadata.dropped_items,
            dropped_reasons=dropped_reasons,
            guardrails_enabled=True,
            guardrail_input_decision=input_guard_res.decision.value,
            guardrail_retrieval_decision=retrieval_guard_res.decision.value,
            guardrail_output_decision=output_guard_res.decision.value,
            guardrail_latency_ms=round(
                input_guard_latency_ms + retrieval_guard_latency_ms + output_guard_latency_ms, 2
            ),
            guardrail_violations=output_violations,
        )

        retrieved_chunks_payload = [
            {
                "chunk_id": str(c.chunk_id),
                "document_id": str(c.document_id),
                "score": round(c.score, 4),
                "page_number": c.page_number,
                "metadata": c.metadata,
                "content_preview": c.content[:200],
            }
            for c in chunks
        ]

        return ChatResponse(
            session_id=session_id,
            query=query,
            answer=answer,
            sources=built_context.citations,
            retrieved_chunks=retrieved_chunks_payload,
            metadata=metadata,
            request_id=req_id,
        )

    async def query_stream(
        self,
        session: AsyncSession,
        query: str,
        user_id: uuid.UUID,
        session_id: uuid.UUID | None = None,
        document_ids: list[uuid.UUID] | None = None,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
        chat_history: list[tuple[str, str]] | None = None,
        context_plan: ContextPlan | None = None,
        routing_enabled: bool | None = None,
        request_id: uuid.UUID | None = None,
    ) -> AsyncIterator[str]:
        """Stream SSE chunks live to the client, concluding with citation and metric payload."""
        total_timer = Timer()
        req_id = request_id or uuid.uuid4()
        obs_logger = get_observability_logger()
        metrics_rec = get_metrics_recorder()

        chat_repo = ChatRepository(session)
        log_repo = RetrievalLogRepository(session)

        # Ensure session exists or create new
        if not session_id:
            first_words = " ".join(query.strip().split()[:5])
            title = f"{first_words}..." if len(query.strip().split()) > 5 else first_words
            chat_session = await chat_repo.create_session(user_id=user_id, title=title)
            session_id = chat_session.id

        # Save user message
        await chat_repo.add_message(
            session_id=session_id,
            role="user",
            content=query,
        )

        obs_logger.log_request_started(request_id=req_id, session_id=session_id, user_id=user_id)
        metrics_rec.record_event(
            ObservabilityEvent(
                event=EventType.REQUEST_STARTED,
                request_id=req_id,
                session_id=session_id,
                data={"user_id": str(user_id)},
            )
        )

        # 1. Input Guardrail Evaluation
        input_guard_timer = Timer()
        input_guard_res = await self.guardrails.input_guard.evaluate(
            query=query,
            user_id=user_id,
            session_id=session_id,
            request_id=req_id,
        )
        input_guard_latency_ms = input_guard_timer.stop()
        metrics_rec.increment("guardrail_checks_total")
        metrics_rec.observe("guardrail_latency", input_guard_latency_ms)

        obs_logger.log_stage_completed(
            EventType.INPUT_GUARDRAIL_COMPLETED,
            request_id=req_id,
            session_id=session_id,
            decision=input_guard_res.decision.value,
            latency_ms=input_guard_latency_ms,
        )

        if input_guard_res.is_blocked:
            metrics_rec.increment("guardrail_blocked_total")
            metrics_rec.increment("guardrail_input_violations_total")
            obs_logger.log_stage_completed(
                EventType.GUARDRAIL_BLOCKED,
                request_id=req_id,
                session_id=session_id,
                stage="INPUT",
                reason=input_guard_res.metadata.reason,
            )
            blocked_msg = (
                "I cannot fulfill this request because it violates application safety guidelines."
            )
            await chat_repo.add_message(
                session_id=session_id,
                role="assistant",
                content=blocked_msg,
                sources=[],
            )
            yield f"data: {json.dumps({'type': 'error', 'message': blocked_msg, 'code': 'GUARDRAIL_BLOCKED'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': str(session_id), 'request_id': str(req_id), 'sources': [], 'metadata': {'guardrail_input_decision': 'BLOCK', 'guardrails_enabled': True}})}\n\n"
            return

        if input_guard_res.is_sanitized:
            metrics_rec.increment("guardrail_sanitized_total")
            query = input_guard_res.safe_text
        else:
            metrics_rec.increment("guardrail_allowed_total")

        # Yield session_id and request_id initialization event
        yield f"data: {json.dumps({'type': 'init', 'session_id': str(session_id), 'request_id': str(req_id)})}\n\n"

        # Query preprocessing
        query_timer = Timer()
        processed_query = QueryProcessor.rewrite_with_history(query, chat_history)
        query_latency_ms = query_timer.stop()
        obs_logger.log_stage_completed(
            EventType.QUERY_PROCESSED,
            request_id=req_id,
            session_id=session_id,
            latency_ms=query_latency_ms,
        )

        # Evaluate ContextPlan if routing is active
        use_routing = routing_enabled if routing_enabled is not None else self.routing_enabled
        plan: ContextPlan | None = None
        routing_timer = Timer(autostart=False)
        if use_routing or context_plan is not None:
            routing_timer.start()
            plan = context_plan or self.orchestrator.plan(
                query=query,
                chat_history=chat_history,
                rag_top_k=top_k or settings.TOP_K,
            )
            routing_latency_ms = routing_timer.stop()
        else:
            routing_latency_ms = 0.0

        selected_sources = plan.selected_sources if plan else ["rag", "cag", "mag", "conversation"]
        obs_logger.log_stage_completed(
            EventType.CONTEXT_SOURCES_SELECTED,
            request_id=req_id,
            session_id=session_id,
            selected_sources=selected_sources,
            routing_latency_ms=routing_latency_ms,
        )

        # Retrieval and reranking (RAG)
        chunks: list[ScoredChunk] = []
        retrieval_latency: float = 0.0
        reranking_latency: float = 0.0
        candidate_count: int = 0

        should_fetch_rag = plan.use_rag if plan is not None else True
        if should_fetch_rag:
            (
                chunks,
                retrieval_latency,
                reranking_latency,
                candidate_count,
            ) = await self._retrieve_and_rerank(
                session=session,
                processed_query=processed_query,
                user_id=user_id,
                document_ids=document_ids,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
            )
            obs_logger.log_stage_completed(
                EventType.RAG_COMPLETED,
                request_id=req_id,
                session_id=session_id,
                candidates_count=candidate_count,
                reranked_count=len(chunks),
                retrieval_latency_ms=retrieval_latency,
                reranking_latency_ms=reranking_latency,
            )

        # CAG context lookup
        cached_contexts: list[CachedContext] = []
        cag_latency_ms: float = 0.0
        should_fetch_cag = plan.use_cag if plan is not None else True
        if self.cag_enabled and self.cag_provider and should_fetch_cag:
            cag_timer = Timer()
            cached_contexts = await self.cag_provider.retrieve(
                query=query,
                user_id=user_id,
            )
            cag_latency_ms = cag_timer.stop()
            obs_logger.log_stage_completed(
                EventType.CAG_COMPLETED,
                request_id=req_id,
                session_id=session_id,
                count=len(cached_contexts),
                latency_ms=cag_latency_ms,
            )

        # MAG context lookup
        memory_contexts: list[MemoryContext] = []
        mag_latency_ms: float = 0.0
        should_fetch_mag = plan.use_mag if plan is not None else True
        if self.mag_enabled and self.mag_provider and should_fetch_mag:
            mag_timer = Timer()
            memory_contexts = await self.mag_provider.retrieve(
                query=query,
                user_id=user_id,
                session=session,
                top_k=plan.memory_top_k if plan else None,
            )
            mag_latency_ms = mag_timer.stop()
            obs_logger.log_stage_completed(
                EventType.MAG_COMPLETED,
                request_id=req_id,
                session_id=session_id,
                count=len(memory_contexts),
                latency_ms=mag_latency_ms,
            )

        # Context formatting and ContextBundle
        rag_contexts = RAGContextAdapter.chunks_to_rag_context(chunks)
        conv_contexts = (
            RAGContextAdapter.history_to_conversation_context(chat_history)
            if (plan is None or plan.use_conversation)
            else []
        )

        fusion_timer = Timer()
        bundle = self.fusion.fuse(
            query=query,
            rag_context=rag_contexts,
            cached_context=cached_contexts,
            memories=memory_contexts,
            conversation_history=conv_contexts,
            current_user_id=user_id,
        )
        fusion_latency_ms = fusion_timer.stop()
        obs_logger.log_stage_completed(
            EventType.FUSION_COMPLETED,
            request_id=req_id,
            session_id=session_id,
            total_items=bundle.metadata.total_context_items,
            selected_items=bundle.metadata.context_count,
            deduplicated_items=bundle.metadata.deduplicated_items,
            dropped_items=bundle.metadata.dropped_items,
            estimated_tokens=bundle.metadata.estimated_tokens,
            latency_ms=fusion_latency_ms,
        )

        # 2. Retrieval Guardrail Evaluation
        retrieval_guard_timer = Timer()
        contexts_to_check = [
            {
                "content": c.content,
                "user_id": c.metadata.get("user_id"),
                "document_id": str(c.document_id),
            }
            for c in chunks
        ]
        for cached in cached_contexts:
            contexts_to_check.append({"content": cached.content, "user_id": str(user_id)})
        for mem in memory_contexts:
            contexts_to_check.append({"content": mem.content, "user_id": str(user_id)})

        retrieval_guard_res = await self.guardrails.retrieval_guard.evaluate(
            query=query,
            contexts=contexts_to_check,
            user_id=user_id,
            request_id=req_id,
        )
        retrieval_guard_latency_ms = retrieval_guard_timer.stop()
        metrics_rec.increment("guardrail_checks_total")
        metrics_rec.observe("guardrail_latency", retrieval_guard_latency_ms)

        obs_logger.log_stage_completed(
            EventType.RETRIEVAL_GUARDRAIL_COMPLETED,
            request_id=req_id,
            session_id=session_id,
            decision=retrieval_guard_res.decision.value,
            latency_ms=retrieval_guard_latency_ms,
        )

        if retrieval_guard_res.is_blocked:
            metrics_rec.increment("guardrail_blocked_total")
            metrics_rec.increment("guardrail_retrieval_violations_total")
            obs_logger.log_stage_completed(
                EventType.GUARDRAIL_BLOCKED,
                request_id=req_id,
                session_id=session_id,
                stage="RETRIEVAL",
                reason=retrieval_guard_res.metadata.reason,
            )
            blocked_msg = "Retrieved content failed security validation policies."
            await chat_repo.add_message(
                session_id=session_id,
                role="assistant",
                content=blocked_msg,
                sources=[],
            )
            yield f"data: {json.dumps({'type': 'error', 'message': blocked_msg, 'code': 'GUARDRAIL_BLOCKED'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': str(session_id), 'request_id': str(req_id), 'sources': [], 'metadata': {'guardrail_retrieval_decision': 'BLOCK', 'guardrails_enabled': True}})}\n\n"
            return
        else:
            metrics_rec.increment("guardrail_allowed_total")

        prompt_timer = Timer()
        built_context = self.context_builder.build_context(chunks)
        system_prompt = PromptBuilder.build_system_prompt()
        user_prompt = PromptBuilder.build_user_prompt_from_bundle(
            bundle=bundle,
            formatted_context=built_context.formatted_context,
        )
        prompt_latency_ms = prompt_timer.stop()
        estimated_prompt_tokens = TokenEstimator.estimate(system_prompt + user_prompt)
        obs_logger.log_stage_completed(
            EventType.PROMPT_BUILT,
            request_id=req_id,
            session_id=session_id,
            estimated_tokens=estimated_prompt_tokens,
            latency_ms=prompt_latency_ms,
        )

        raw_stream_prov = getattr(self.llm, "provider_name", "mock")
        stream_prov_str = raw_stream_prov if isinstance(raw_stream_prov, str) else "mock"

        raw_stream_mod = getattr(self.llm, "model_name", "mock-llm-v1")
        stream_mod_str = raw_stream_mod if isinstance(raw_stream_mod, str) else "mock-llm-v1"

        # Stream tokens from LLM
        llm_timer = Timer()
        obs_logger.log_stage_completed(
            EventType.LLM_STARTED,
            request_id=req_id,
            session_id=session_id,
            provider=stream_prov_str,
            model=stream_mod_str,
        )

        token_accumulator = []
        first_token_time: float | None = None

        try:
            async for token in self.llm.generate_stream(
                prompt=user_prompt,
                system_prompt=system_prompt,
            ):
                if first_token_time is None:
                    first_token_time = llm_timer.elapsed_ms
                    obs_logger.log_stage_completed(
                        EventType.LLM_FIRST_TOKEN,
                        request_id=req_id,
                        session_id=session_id,
                        ttft_ms=first_token_time,
                    )
                token_accumulator.append(token)
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        except Exception as e:
            clean_err = sanitize_error_message(str(e))
            logger.error(f"Error streaming LLM response: {clean_err}")
            obs_logger.log_error(
                request_id=req_id,
                session_id=session_id,
                stage="llm_streaming",
                error_type=type(e).__name__,
                sanitized_message=clean_err,
            )
            metrics_rec.increment("requests_failed")
            yield f"data: {json.dumps({'type': 'error', 'message': clean_err})}\n\n"
            return

        full_answer = "".join(token_accumulator)
        llm_latency_ms = llm_timer.stop()
        total_latency_ms = total_timer.stop()

        obs_logger.log_stage_completed(
            EventType.LLM_COMPLETED,
            request_id=req_id,
            session_id=session_id,
            provider=stream_prov_str,
            model=stream_mod_str,
            latency_ms=llm_latency_ms,
        )

        # 3. Output Guardrail Evaluation
        output_guard_timer = Timer()
        output_guard_res = await self.guardrails.output_guard.evaluate(
            query=query,
            response_text=full_answer,
            contexts=contexts_to_check,
            request_id=req_id,
        )
        output_guard_latency_ms = output_guard_timer.stop()
        metrics_rec.increment("guardrail_checks_total")
        metrics_rec.observe("guardrail_latency", output_guard_latency_ms)

        obs_logger.log_stage_completed(
            EventType.OUTPUT_GUARDRAIL_COMPLETED,
            request_id=req_id,
            session_id=session_id,
            decision=output_guard_res.decision.value,
            latency_ms=output_guard_latency_ms,
        )

        output_violations = []
        if output_guard_res.is_blocked:
            metrics_rec.increment("guardrail_blocked_total")
            metrics_rec.increment("guardrail_output_violations_total")
            obs_logger.log_stage_completed(
                EventType.GUARDRAIL_BLOCKED,
                request_id=req_id,
                session_id=session_id,
                stage="OUTPUT",
                reason=output_guard_res.metadata.reason,
            )
            full_answer = "I cannot provide this response because it violates safety and non-disclosure policies."
            output_violations = [v.reason for v in output_guard_res.violations]
            built_context.citations = []
            # Notify client to replace unsafe content
            yield f"data: {json.dumps({'type': 'redact', 'message': full_answer})}\n\n"
        elif output_guard_res.is_sanitized:
            metrics_rec.increment("guardrail_sanitized_total")
            full_answer = output_guard_res.safe_text
        else:
            metrics_rec.increment("guardrail_allowed_total")

        # Save assistant message
        sources_payload = [c.model_dump(mode="json") for c in built_context.citations]
        await chat_repo.add_message(
            session_id=session_id,
            role="assistant",
            content=full_answer,
            sources=sources_payload,
        )

        # Selectively extract and persist high-value user memories from query
        if self.mag_enabled and self.mag_provider:
            try:
                await self.mag_provider.extract_and_save(
                    session=session,
                    user_id=user_id,
                    text=query,
                )
            except Exception as e:
                logger.warning(f"Error during memory extraction in stream: {e}")

        # RAG quality statistics
        scores = [c.score for c in chunks if c.score is not None]
        top_score = max(scores) if scores else None
        min_score = min(scores) if scores else None
        avg_score = round(sum(scores) / len(scores), 4) if scores else None
        unique_docs = len({c.document_id for c in chunks})
        unique_pages = len(
            {(c.document_id, c.page_number) for c in chunks if c.page_number is not None}
        )
        citation_count = len(built_context.citations)

        # Tally dropped context reasons
        dropped_reasons: dict[str, int] = {}
        for dc in bundle.metadata.dropped_contexts:
            dropped_reasons[dc.reason] = dropped_reasons.get(dc.reason, 0) + 1

        # Record pipeline metrics
        pipeline_metrics = PipelineMetrics(
            request_id=req_id,
            session_id=session_id,
            user_id=user_id,
            query_processing_latency_ms=round(query_latency_ms, 2),
            routing_latency_ms=round(routing_latency_ms, 2),
            retrieval_latency_ms=round(retrieval_latency, 2),
            reranking_latency_ms=round(reranking_latency, 2),
            cag_latency_ms=round(cag_latency_ms, 2),
            mag_latency_ms=round(mag_latency_ms, 2),
            fusion_latency_ms=round(fusion_latency_ms, 2),
            prompt_build_latency_ms=round(prompt_latency_ms, 2),
            llm_time_to_first_token_ms=round(first_token_time, 2) if first_token_time else None,
            llm_generation_latency_ms=round(llm_latency_ms, 2),
            total_latency_ms=round(total_latency_ms, 2),
            rag_selected=bool(chunks),
            hybrid_candidates_count=candidate_count,
            reranked_chunks_count=len(chunks),
            top_score=top_score,
            average_score=avg_score,
            minimum_score=min_score,
            unique_documents_count=unique_docs,
            unique_pages_count=unique_pages,
            citation_count=citation_count,
            cag_selected=bool(cached_contexts),
            cag_cache_hit=bool(cached_contexts),
            cag_cache_miss=self.cag_enabled and should_fetch_cag and not bool(cached_contexts),
            cag_items_used=len(cached_contexts),
            cag_context_tokens=sum(TokenEstimator.estimate(c.content) for c in cached_contexts),
            mag_selected=bool(memory_contexts),
            memories_retrieved=len(memory_contexts),
            memories_used=len(memory_contexts),
            memory_types=[m.memory_type for m in memory_contexts],
            routing_enabled=plan is not None,
            routing_confidence=plan.confidence if plan else 1.0,
            routing_reason=plan.reason if plan else "additive",
            selected_sources=plan.selected_sources if plan else bundle.selected_sources,
            contexts_received=bundle.metadata.total_context_items,
            contexts_selected=bundle.metadata.context_count,
            contexts_deduplicated=bundle.metadata.deduplicated_items,
            contexts_dropped=bundle.metadata.dropped_items,
            estimated_tokens=bundle.metadata.estimated_tokens,
            token_budget=bundle.metadata.token_budget,
            dropped_reasons=dropped_reasons,
            estimated_input_tokens=estimated_prompt_tokens,
            llm_provider=stream_prov_str,
            llm_model=stream_mod_str,
        )
        metrics_rec.record_pipeline_metrics(pipeline_metrics)
        obs_logger.log_stage_completed(
            EventType.REQUEST_COMPLETED,
            request_id=req_id,
            session_id=session_id,
            total_latency_ms=round(total_latency_ms, 2),
        )

        # Persist retrieval log
        await log_repo.create_log(
            session_id=session_id,
            user_id=user_id,
            request_id=req_id,
            metadata_=pipeline_metrics.to_safe_summary(),
            query=query,
            retrieved_chunk_ids=[str(cid) for cid in built_context.chunk_ids],
            retrieval_method="hybrid_rerank"
            if (chunks and self.reranker.enabled)
            else ("hybrid" if chunks else "none"),
            candidate_count=candidate_count,
            top_k=len(chunks),
            reranking_enabled=self.reranker.enabled if chunks else False,
            retrieval_latency_ms=round(retrieval_latency, 2),
            reranking_latency_ms=round(reranking_latency, 2),
            llm_latency_ms=round(llm_latency_ms, 2),
            total_latency_ms=round(total_latency_ms, 2),
        )

        # Send final completed event
        done_payload = {
            "type": "done",
            "session_id": str(session_id),
            "request_id": str(req_id),
            "sources": sources_payload,
            "metadata": {
                "retrieval_method": "hybrid_rerank"
                if (chunks and self.reranker.enabled)
                else ("hybrid" if chunks else "none"),
                "candidates_count": candidate_count,
                "top_k": len(chunks),
                "reranking_enabled": self.reranker.enabled if chunks else False,
                "retrieval_latency_ms": round(retrieval_latency, 2),
                "reranking_latency_ms": round(reranking_latency, 2),
                "llm_latency_ms": round(llm_latency_ms, 2),
                "total_latency_ms": round(total_latency_ms, 2),
                "rag_selected": bool(chunks),
                "cag_enabled": self.cag_enabled,
                "cag_selected": bool(cached_contexts),
                "cache_hit": bool(cached_contexts),
                "cache_miss": self.cag_enabled and should_fetch_cag and not bool(cached_contexts),
                "cache_context_count": len(cached_contexts),
                "cache_context_size": sum(len(c.content) for c in cached_contexts),
                "mag_enabled": self.mag_enabled,
                "mag_selected": bool(memory_contexts),
                "memories_retrieved": len(memory_contexts),
                "memories_used": len(memory_contexts),
                "memory_retrieval_latency_ms": round(mag_latency_ms, 2),
                "memory_types": [m.memory_type for m in memory_contexts],
                "routing_enabled": plan is not None,
                "routing_latency_ms": round(routing_latency_ms, 2),
                "routing_confidence": plan.confidence if plan else 1.0,
                "routing_reason": plan.reason if plan else "additive",
                "selected_sources": plan.selected_sources if plan else bundle.selected_sources,
                "provider_failures": [],
                "llm_provider": stream_prov_str,
                "llm_model": stream_mod_str,
                "time_to_first_token_ms": round(first_token_time, 2) if first_token_time else None,
                "request_id": str(req_id),
                "prompt_build_latency_ms": round(prompt_latency_ms, 2),
                "estimated_input_tokens": estimated_prompt_tokens,
                "dropped_contexts_count": bundle.metadata.dropped_items,
                "dropped_reasons": dropped_reasons,
                "guardrails_enabled": True,
                "guardrail_input_decision": input_guard_res.decision.value,
                "guardrail_retrieval_decision": retrieval_guard_res.decision.value,
                "guardrail_output_decision": output_guard_res.decision.value,
                "guardrail_latency_ms": round(
                    input_guard_latency_ms + retrieval_guard_latency_ms + output_guard_latency_ms, 2
                ),
                "guardrail_violations": output_violations,
            },
        }
        yield f"data: {json.dumps(done_payload)}\n\n"
