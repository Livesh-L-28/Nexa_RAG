"""Deterministic context fusion implementation."""

import logging
import math
import time
import uuid
from typing import Any

from app.orchestration.interfaces import ContextFusion
from app.orchestration.models import (
    CachedContext,
    ContextBudgetConfig,
    ContextBundle,
    ContextMetadata,
    ContextSource,
    ConversationContext,
    DroppedContext,
    MemoryContext,
    NormalizedContext,
    RAGContext,
)

logger = logging.getLogger(__name__)


class TokenEstimator:
    """Deterministic token estimator approximation (chars / 4)."""

    @staticmethod
    def estimate(text: str) -> int:
        """Estimate token count from string length."""
        if not text:
            return 0
        return max(1, math.ceil(len(text) / 4.0))


class DefaultContextFusion(ContextFusion):
    """Hardened deterministic context fusion engine.

    Enforces:
    1. Normalization into canonical internal representation (NormalizedContext).
    2. Content deduplication (intra-source and cross-source, higher priority wins).
    3. Relevance threshold filtering (scored contexts below min_score excluded).
    4. Deterministic priority ordering (priority asc, score desc, source_id asc).
    5. Priority-aware token budgeting (global and source-specific budgets, complete items).
    6. Tenant / user isolation validation on user-specific context.
    7. Full source attribution and diagnostic dropped context tracking.
    """

    def __init__(self, budget_config: ContextBudgetConfig | None = None):
        self.default_budget_config = budget_config or ContextBudgetConfig()
        self.token_estimator = TokenEstimator()

    @staticmethod
    def _normalize_content_for_dedup(text: str) -> str:
        """Normalize whitespace and case for deduplication comparison without mutating original text."""
        return " ".join(text.lower().split())

    def _normalize_inputs(
        self,
        rag_context: list[RAGContext] | None,
        cached_context: list[CachedContext] | None,
        memories: list[MemoryContext] | None,
        conversation_history: list[ConversationContext] | None,
    ) -> list[NormalizedContext]:
        """Normalize all incoming context items into canonical internal representation."""
        normalized: list[NormalizedContext] = []

        # 1. RAG
        for rc in rag_context or []:
            if not rc.content or not rc.content.strip():
                continue
            normalized.append(
                NormalizedContext(
                    source=ContextSource.RAG,
                    content=rc.content,
                    priority=rc.priority,
                    score=rc.score,
                    source_id=str(rc.chunk_id),
                    metadata=dict(rc.metadata),
                    estimated_tokens=self.token_estimator.estimate(rc.content),
                    original_item=rc,
                )
            )

        # 2. CAG
        for cc in cached_context or []:
            if not cc.content or not cc.content.strip():
                continue
            normalized.append(
                NormalizedContext(
                    source=ContextSource.CAG,
                    content=cc.content,
                    priority=cc.priority,
                    score=None,
                    source_id=cc.cache_id,
                    metadata=dict(cc.metadata),
                    estimated_tokens=self.token_estimator.estimate(cc.content),
                    original_item=cc,
                )
            )

        # 3. MAG
        for mc in memories or []:
            if not mc.content or not mc.content.strip():
                continue
            normalized.append(
                NormalizedContext(
                    source=ContextSource.MAG,
                    content=mc.content,
                    priority=mc.priority,
                    score=mc.relevance_score,
                    source_id=mc.memory_id,
                    metadata=dict(mc.metadata),
                    estimated_tokens=self.token_estimator.estimate(mc.content),
                    original_item=mc,
                )
            )

        # 4. Conversation
        for idx, ch in enumerate(conversation_history or []):
            if not ch.content or not ch.content.strip():
                continue
            meta = {
                "role": ch.role,
                "session_id": str(ch.session_id) if ch.session_id else None,
                "turn_index": idx,
            }
            if ch.created_at:
                meta["created_at"] = ch.created_at.isoformat()
            normalized.append(
                NormalizedContext(
                    source=ContextSource.CONVERSATION,
                    content=ch.content,
                    priority=ch.priority,
                    # Assign a pseudo-score based on turn index so recent turns rank higher than older turns
                    score=float(idx),
                    source_id=f"conv_{idx}_{ch.role}",
                    metadata=meta,
                    estimated_tokens=self.token_estimator.estimate(ch.content),
                    original_item=ch,
                )
            )

        return normalized

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
        """Deterministically assemble, deduplicate, filter, and budget context items."""
        start_time = time.perf_counter()
        config = budget_config or self.default_budget_config

        # 1. Normalize
        candidates = self._normalize_inputs(
            rag_context=rag_context,
            cached_context=cached_context,
            memories=memories,
            conversation_history=conversation_history,
        )
        total_items = len(candidates)
        dropped_contexts: list[DroppedContext] = []

        # 2. Security validation (Tenant / user isolation)
        if current_user_id is not None:
            str_user_id = str(current_user_id)
            valid_candidates = []
            for item in candidates:
                item_owner = item.metadata.get("user_id") or item.metadata.get("owner_id")
                if item_owner is not None and str(item_owner) != str_user_id:
                    dropped_contexts.append(
                        DroppedContext(
                            source=item.source,
                            source_id=item.source_id,
                            reason="security_user_mismatch",
                            priority=item.priority,
                            score=item.score,
                            estimated_tokens=item.estimated_tokens,
                        )
                    )
                else:
                    valid_candidates.append(item)
            candidates = valid_candidates

        # 3. Content Deduplication (Intra-source and Cross-source)
        dedup_map: dict[str, NormalizedContext] = {}
        duplicates_dropped = 0

        for item in candidates:
            norm_key = self._normalize_content_for_dedup(item.content)
            if norm_key in dedup_map:
                existing = dedup_map[norm_key]
                # Compare: does new item beat existing?
                # Lower priority number wins (RAG 3 beats CAG 4 beats MAG 5 beats Conv 6)
                item_wins = False
                if item.priority < existing.priority:
                    item_wins = True
                elif item.priority == existing.priority:
                    item_score = item.score if item.score is not None else -1.0
                    exist_score = existing.score if existing.score is not None else -1.0
                    if item_score > exist_score:
                        item_wins = True
                    elif item_score == exist_score and item.source_id < existing.source_id:
                        item_wins = True

                if item_wins:
                    dropped_contexts.append(
                        DroppedContext(
                            source=existing.source,
                            source_id=existing.source_id,
                            reason="duplicate",
                            priority=existing.priority,
                            score=existing.score,
                            estimated_tokens=existing.estimated_tokens,
                        )
                    )
                    dedup_map[norm_key] = item
                else:
                    dropped_contexts.append(
                        DroppedContext(
                            source=item.source,
                            source_id=item.source_id,
                            reason="duplicate",
                            priority=item.priority,
                            score=item.score,
                            estimated_tokens=item.estimated_tokens,
                        )
                    )
                duplicates_dropped += 1
            else:
                dedup_map[norm_key] = item

        deduped_candidates = list(dedup_map.values())

        # 4. Relevance filtering
        min_score = (
            config.min_context_score
            if config.min_context_score is not None
            else kwargs.get("min_score")
        )
        filtered_candidates = []
        for item in deduped_candidates:
            if min_score is not None and min_score > 0.0:
                if (
                    item.source != ContextSource.CONVERSATION
                    and item.score is not None
                    and item.score < min_score
                ):
                    dropped_contexts.append(
                        DroppedContext(
                            source=item.source,
                            source_id=item.source_id,
                            reason="below_relevance_threshold",
                            priority=item.priority,
                            score=item.score,
                            estimated_tokens=item.estimated_tokens,
                        )
                    )
                    continue
            filtered_candidates.append(item)

        # 5. Deterministic Priority Ordering
        # Order by:
        # - priority asc (1: System, 2: Security, 3: RAG, 4: CAG, 5: MAG, 6: Conv)
        # - score desc (for RAG/MAG relevance; for Conv, higher turn_index = more recent turn)
        # - source_id asc
        def sort_key(nc: NormalizedContext):
            sc = nc.score if nc.score is not None else -1.0
            return (nc.priority, -sc, nc.source_id)

        sorted_candidates = sorted(filtered_candidates, key=sort_key)

        # 6. Priority-Aware Token Budgeting
        source_budgets: dict[ContextSource, int | None] = {
            ContextSource.RAG: config.max_rag_tokens,
            ContextSource.CAG: config.max_cag_tokens,
            ContextSource.MAG: config.max_mag_tokens,
            ContextSource.CONVERSATION: config.max_conversation_tokens,
        }

        global_budget = config.max_context_tokens
        global_tokens_used = 0
        source_tokens_used: dict[ContextSource, int] = {s: 0 for s in ContextSource}

        accepted_items: list[NormalizedContext] = []

        for item in sorted_candidates:
            # Check source-specific budget
            src_limit = source_budgets.get(item.source)
            if src_limit is not None and (
                source_tokens_used[item.source] + item.estimated_tokens > src_limit
            ):
                dropped_contexts.append(
                    DroppedContext(
                        source=item.source,
                        source_id=item.source_id,
                        reason="source_token_budget",
                        priority=item.priority,
                        score=item.score,
                        estimated_tokens=item.estimated_tokens,
                    )
                )
                continue

            # Check global budget
            if global_tokens_used + item.estimated_tokens > global_budget:
                dropped_contexts.append(
                    DroppedContext(
                        source=item.source,
                        source_id=item.source_id,
                        reason="token_budget",
                        priority=item.priority,
                        score=item.score,
                        estimated_tokens=item.estimated_tokens,
                    )
                )
                continue

            # Accept item
            accepted_items.append(item)
            global_tokens_used += item.estimated_tokens
            source_tokens_used[item.source] += item.estimated_tokens

        # 7. Reassemble into typed lists for ContextBundle
        fused_rag: list[RAGContext] = [
            item.original_item for item in accepted_items if item.source == ContextSource.RAG
        ]
        fused_cag: list[CachedContext] = [
            item.original_item for item in accepted_items if item.source == ContextSource.CAG
        ]
        fused_mag: list[MemoryContext] = [
            item.original_item for item in accepted_items if item.source == ContextSource.MAG
        ]
        # Re-sort conversation history into chronological order based on turn_index
        conv_items = [item for item in accepted_items if item.source == ContextSource.CONVERSATION]
        conv_items.sort(key=lambda it: it.metadata.get("turn_index", 0))
        fused_conv: list[ConversationContext] = [item.original_item for item in conv_items]

        # Determine active sources
        sources: list[ContextSource] = []
        if fused_rag:
            sources.append(ContextSource.RAG)
        if fused_cag:
            sources.append(ContextSource.CAG)
        if fused_mag:
            sources.append(ContextSource.MAG)
        if fused_conv:
            sources.append(ContextSource.CONVERSATION)

        selected_sources = [s.value for s in sources]

        # Calculate context size metrics (non-conversation count & chars)
        total_count = len(fused_rag) + len(fused_cag) + len(fused_mag)
        total_chars = (
            sum(len(item.content) for item in fused_rag)
            + sum(len(item.content) for item in fused_cag)
            + sum(len(item.content) for item in fused_mag)
        )

        fusion_latency_ms = (time.perf_counter() - start_time) * 1000.0

        # Construct or merge metadata
        meta = metadata or ContextMetadata()
        meta.rag_selected = bool(fused_rag)
        meta.cag_selected = bool(fused_cag)
        meta.mag_selected = bool(fused_mag)
        meta.context_sources = selected_sources
        meta.context_count = total_count
        meta.context_size_chars = total_chars

        # Phase 11 observability
        meta.total_context_items = total_items
        meta.deduplicated_items = duplicates_dropped
        meta.dropped_items = len(dropped_contexts)
        meta.estimated_tokens = global_tokens_used
        meta.token_budget = global_budget
        meta.dropped_contexts = dropped_contexts
        meta.fusion_latency_ms = round(fusion_latency_ms, 2)

        return ContextBundle(
            query=query,
            rag_context=fused_rag,
            cached_context=fused_cag,
            memories=fused_mag,
            conversation_history=fused_conv,
            sources=sources,
            selected_sources=selected_sources,
            metadata=meta,
        )
