"""Unit and integration tests for Phase 10: Intelligent Context Orchestrator."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import AuthorizationException
from app.orchestration.analyzer import RuleBasedQueryAnalyzer
from app.orchestration.interfaces import ContextProvider
from app.orchestration.models import (
    CachedContext,
    ContextPlan,
    ContextPriority,
    MemoryContext,
    RAGContext,
)
from app.orchestration.orchestrator import ContextOrchestrator
from app.orchestration.policies import RuleBasedContextPolicy

# ============================================================================
# Query Analyzer Tests
# ============================================================================


def test_memory_reference_detection():
    """Verify analyzer identifies explicit memory references."""
    analyzer = RuleBasedQueryAnalyzer()

    signals1 = analyzer.analyze("What did I tell you about my favorite editor?")
    assert signals1.memory_reference is True
    assert signals1.is_chit_chat is False

    signals2 = analyzer.analyze("Do you remember my previous instructions?")
    assert signals2.memory_reference is True

    signals3 = analyzer.analyze("What do I prefer for code formatting?")
    assert signals3.memory_reference is True


def test_document_reference_detection():
    """Verify analyzer identifies explicit document references."""
    analyzer = RuleBasedQueryAnalyzer()

    signals1 = analyzer.analyze("What does the architecture document say about Redis?")
    assert signals1.document_reference is True

    signals2 = analyzer.analyze("According to the specification, what is the max payload?")
    assert signals2.document_reference is True

    signals3 = analyzer.analyze("In the user guide section 3, how do we configure SSL?")
    assert signals3.document_reference is True


def test_policy_reference_detection():
    """Verify analyzer identifies stable organizational policies and guidelines."""
    analyzer = RuleBasedQueryAnalyzer()

    signals1 = analyzer.analyze("What is our leave policy for annual vacation?")
    assert signals1.policy_reference is True
    assert signals1.stable_knowledge_reference is True

    signals2 = analyzer.analyze("What are the company security standards for TLS?")
    assert signals2.policy_reference is True
    assert signals2.stable_knowledge_reference is True


def test_project_reference_detection():
    """Verify analyzer identifies user project references."""
    analyzer = RuleBasedQueryAnalyzer()

    signals1 = analyzer.analyze("How is our project backend structured?")
    assert signals1.project_reference is True

    signals2 = analyzer.analyze("My codebase uses FastAPI with SQLAlchemy.")
    assert signals2.project_reference is True


def test_conversation_detection():
    """Verify analyzer identifies conversational follow-ups and chit-chat."""
    analyzer = RuleBasedQueryAnalyzer()

    signals_chitchat = analyzer.analyze("Hello there!")
    assert signals_chitchat.is_chit_chat is True

    signals_thanks = analyzer.analyze("Thanks a lot")
    assert signals_thanks.is_chit_chat is True

    signals_conv = analyzer.analyze(
        "As we discussed earlier, what should we do next?",
        chat_history=[("user", "We were discussing deployment")],
    )
    assert signals_conv.conversation_reference is True


# ============================================================================
# Policy Routing Tests
# ============================================================================


def test_memory_query_routes_to_mag():
    """Verify memory queries route to MAG while bypassing RAG and CAG."""
    analyzer = RuleBasedQueryAnalyzer()
    policy = RuleBasedContextPolicy()

    query = "What did I tell you about my project preferences?"
    signals = analyzer.analyze(query)
    plan = policy.evaluate(query, signals)

    assert plan.use_mag is True
    assert plan.use_rag is False
    assert plan.use_cag is False
    assert plan.use_conversation is True
    assert "mag" in plan.selected_sources
    assert plan.confidence >= 0.85


def test_document_query_routes_to_rag():
    """Verify document queries route to RAG while bypassing CAG and MAG."""
    analyzer = RuleBasedQueryAnalyzer()
    policy = RuleBasedContextPolicy()

    query = "What does the architecture document say about authentication?"
    signals = analyzer.analyze(query)
    plan = policy.evaluate(query, signals)

    assert plan.use_rag is True
    assert plan.use_cag is False
    assert plan.use_mag is False
    assert "rag" in plan.selected_sources
    assert plan.confidence >= 0.85


def test_policy_query_routes_to_cag():
    """Verify policy queries route to CAG while bypassing MAG."""
    analyzer = RuleBasedQueryAnalyzer()
    policy = RuleBasedContextPolicy()

    query = "What is our company leave policy?"
    signals = analyzer.analyze(query)
    plan = policy.evaluate(query, signals)

    assert plan.use_cag is True
    assert plan.use_mag is False
    assert "cag" in plan.selected_sources
    assert plan.confidence >= 0.85


def test_combined_query_routes_to_multiple_sources():
    """Verify combined queries route to MAG and RAG concurrently."""
    analyzer = RuleBasedQueryAnalyzer()
    policy = RuleBasedContextPolicy()

    query = "Based on my project and the architecture documentation, how should I implement authentication?"
    signals = analyzer.analyze(query)
    plan = policy.evaluate(query, signals)

    assert plan.use_mag is True
    assert plan.use_rag is True
    assert "mag" in plan.selected_sources
    assert "rag" in plan.selected_sources
    assert plan.confidence >= 0.88


def test_all_context_query_routes_to_all_sources():
    """Verify query referencing project, policy, and docs routes to RAG, CAG, and MAG."""
    analyzer = RuleBasedQueryAnalyzer()
    policy = RuleBasedContextPolicy()

    query = "Given our project tech stack, security policy standards, and architecture doc, how do we deploy?"
    signals = analyzer.analyze(query)
    plan = policy.evaluate(query, signals)

    assert plan.use_rag is True
    assert plan.use_cag is True
    assert plan.use_mag is True
    assert plan.use_conversation is True
    assert set(plan.selected_sources) == {"rag", "cag", "mag", "conversation"}


def test_simple_chat_does_not_trigger_retrieval():
    """Verify simple chit-chat bypasses all external retrieval sources."""
    analyzer = RuleBasedQueryAnalyzer()
    policy = RuleBasedContextPolicy()

    for greeting in ["Hello", "Thanks", "Good morning", "ok", "cool"]:
        signals = analyzer.analyze(greeting)
        plan = policy.evaluate(greeting, signals)

        assert plan.use_rag is False
        assert plan.use_cag is False
        assert plan.use_mag is False
        assert plan.use_conversation is True
        assert plan.selected_sources == ["conversation"]
        assert plan.confidence >= 0.90


# ============================================================================
# Confidence and Fallback Tests
# ============================================================================


def test_confidence_range():
    """Verify all decisions and plans produce confidence bounded in [0.0, 1.0]."""
    orchestrator = ContextOrchestrator()

    queries = [
        "Hello",
        "What did I say?",
        "What is the refund policy?",
        "Explain the microservice architecture documentation.",
        "How do databases store b-trees?",
    ]

    for q in queries:
        plan = orchestrator.plan(q)
        assert 0.0 <= plan.confidence <= 1.0
        for d in plan.decisions:
            assert 0.0 <= d.confidence <= 1.0


def test_low_confidence_fallback():
    """Verify general knowledge query with no explicit signals safely falls back to RAG."""
    orchestrator = ContextOrchestrator()

    # Generic knowledge-seeking query without explicit keywords
    query = "How does vector indexing optimize high-dimensional nearest neighbors?"
    plan = orchestrator.plan(query)

    assert plan.use_rag is True
    assert plan.use_cag is False
    assert plan.use_mag is False
    assert plan.confidence == 0.65
    assert "fallback" in plan.reason.lower()


# ============================================================================
# Orchestrator Execution Tests
# ============================================================================


@pytest.mark.asyncio
async def test_rag_only_execution():
    """Verify orchestrator executes RAG provider when planned."""
    user_id = uuid.uuid4()
    mock_rag = MagicMock(spec=ContextProvider)
    mock_rag.source_name = "rag"
    mock_rag.retrieve = AsyncMock(
        return_value=[
            RAGContext(
                content="Architecture details.",
                document_id=uuid.uuid4(),
                chunk_id=uuid.uuid4(),
                filename="arch.pdf",
            )
        ]
    )

    orchestrator = ContextOrchestrator()
    plan = ContextPlan(use_rag=True, use_cag=False, use_mag=False)

    bundle, info = await orchestrator.execute_plan(
        plan=plan,
        query="What is the architecture?",
        user_id=user_id,
        rag_provider=mock_rag,
    )

    assert len(bundle.rag_context) == 1
    assert bundle.rag_context[0].content == "Architecture details."
    assert len(bundle.cached_context) == 0
    assert len(bundle.memories) == 0
    assert bundle.metadata.rag_selected is True
    mock_rag.retrieve.assert_awaited_once()


@pytest.mark.asyncio
async def test_mag_only_execution():
    """Verify orchestrator executes MAG provider when planned."""
    user_id = uuid.uuid4()
    mock_mag = MagicMock(spec=ContextProvider)
    mock_mag.source_name = "mag"
    mock_mag.retrieve = AsyncMock(
        return_value=[
            MemoryContext(
                content="User prefers Python.",
                memory_id=str(uuid.uuid4()),
                memory_type="preference",
            )
        ]
    )

    orchestrator = ContextOrchestrator()
    plan = ContextPlan(use_rag=False, use_cag=False, use_mag=True)

    bundle, info = await orchestrator.execute_plan(
        plan=plan,
        query="What do I prefer?",
        user_id=user_id,
        mag_provider=mock_mag,
    )

    assert len(bundle.memories) == 1
    assert bundle.memories[0].content == "User prefers Python."
    assert len(bundle.rag_context) == 0
    assert bundle.metadata.mag_selected is True
    mock_mag.retrieve.assert_awaited_once()


@pytest.mark.asyncio
async def test_cag_only_execution():
    """Verify orchestrator executes CAG provider when planned."""
    user_id = uuid.uuid4()
    mock_cag = MagicMock(spec=ContextProvider)
    mock_cag.source_name = "cag"
    mock_cag.retrieve = AsyncMock(
        return_value=[
            CachedContext(
                content="Standard leave is 20 days.",
                cache_id="cag_leave_policy",
            )
        ]
    )

    orchestrator = ContextOrchestrator()
    plan = ContextPlan(use_rag=False, use_cag=True, use_mag=False)

    bundle, info = await orchestrator.execute_plan(
        plan=plan,
        query="What is the leave policy?",
        user_id=user_id,
        cag_provider=mock_cag,
    )

    assert len(bundle.cached_context) == 1
    assert bundle.cached_context[0].content == "Standard leave is 20 days."
    assert bundle.metadata.cag_selected is True
    mock_cag.retrieve.assert_awaited_once()


@pytest.mark.asyncio
async def test_multi_context_execution():
    """Verify orchestrator dispatches RAG, CAG, and MAG concurrently and fuses them by priority."""
    user_id = uuid.uuid4()

    mock_rag = MagicMock(spec=ContextProvider)
    mock_rag.retrieve = AsyncMock(
        return_value=[
            RAGContext(
                content="Doc chunk",
                document_id=uuid.uuid4(),
                chunk_id=uuid.uuid4(),
                filename="f.pdf",
            )
        ]
    )

    mock_cag = MagicMock(spec=ContextProvider)
    mock_cag.retrieve = AsyncMock(
        return_value=[
            CachedContext(
                content="Cached policy",
                cache_id="cag_1",
            )
        ]
    )

    mock_mag = MagicMock(spec=ContextProvider)
    mock_mag.retrieve = AsyncMock(
        return_value=[
            MemoryContext(
                content="User memory",
                memory_id="mem_1",
            )
        ]
    )

    orchestrator = ContextOrchestrator()
    plan = ContextPlan(use_rag=True, use_cag=True, use_mag=True)

    bundle, info = await orchestrator.execute_plan(
        plan=plan,
        query="Comprehensive query",
        user_id=user_id,
        rag_provider=mock_rag,
        cag_provider=mock_cag,
        mag_provider=mock_mag,
    )

    assert bundle.metadata.rag_selected is True
    assert bundle.metadata.cag_selected is True
    assert bundle.metadata.mag_selected is True
    assert len(bundle.rag_context) == 1
    assert len(bundle.cached_context) == 1
    assert len(bundle.memories) == 1

    # Verify priorities are preserved: RAG=3, CAG=4, MAG=5
    assert bundle.rag_context[0].priority == ContextPriority.RAG
    assert bundle.cached_context[0].priority == ContextPriority.CAG
    assert bundle.memories[0].priority == ContextPriority.MAG


@pytest.mark.asyncio
async def test_provider_failure_isolation():
    """Verify failure in one provider (e.g. MAG) does not break RAG + CAG retrieval."""
    user_id = uuid.uuid4()

    mock_rag = MagicMock(spec=ContextProvider)
    mock_rag.retrieve = AsyncMock(
        return_value=[
            RAGContext(
                content="Authoritative doc chunk",
                document_id=uuid.uuid4(),
                chunk_id=uuid.uuid4(),
                filename="doc.pdf",
            )
        ]
    )

    mock_cag = MagicMock(spec=ContextProvider)
    mock_cag.retrieve = AsyncMock(
        return_value=[
            CachedContext(
                content="Cached policy note",
                cache_id="cag_p",
            )
        ]
    )

    # MAG fails with database error
    mock_mag = MagicMock(spec=ContextProvider)
    mock_mag.retrieve = AsyncMock(side_effect=RuntimeError("Database connection lost"))

    orchestrator = ContextOrchestrator()
    plan = ContextPlan(use_rag=True, use_cag=True, use_mag=True)

    bundle, info = await orchestrator.execute_plan(
        plan=plan,
        query="Query with failing memory",
        user_id=user_id,
        rag_provider=mock_rag,
        cag_provider=mock_cag,
        mag_provider=mock_mag,
    )

    # RAG and CAG succeed
    assert len(bundle.rag_context) == 1
    assert len(bundle.cached_context) == 1
    # MAG failed gracefully without throwing
    assert len(bundle.memories) == 0
    assert len(bundle.metadata.provider_failures) == 1
    assert "mag" in bundle.metadata.provider_failures[0]


# ============================================================================
# Security Tests
# ============================================================================


@pytest.mark.asyncio
async def test_user_id_passed_to_memory_provider():
    """Verify user_id is explicitly passed to MAG retrieval ensuring tenant boundary."""
    user_id = uuid.uuid4()
    mock_mag = MagicMock(spec=ContextProvider)
    mock_mag.retrieve = AsyncMock(return_value=[])

    orchestrator = ContextOrchestrator()
    plan = ContextPlan(use_mag=True)

    await orchestrator.execute_plan(
        plan=plan,
        query="What is my project?",
        user_id=user_id,
        mag_provider=mock_mag,
    )

    mock_mag.retrieve.assert_awaited_once()
    assert mock_mag.retrieve.call_args.kwargs["user_id"] == user_id


@pytest.mark.asyncio
async def test_memory_isolation_preserved():
    """Verify User A's context request cannot be routed to User B's identity."""
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    received_user_ids = []

    async def mock_retrieve(query: str, user_id: uuid.UUID | None = None, **kwargs):
        received_user_ids.append(user_id)
        return []

    mock_provider = MagicMock(spec=ContextProvider)
    mock_provider.retrieve = AsyncMock(side_effect=mock_retrieve)

    orchestrator = ContextOrchestrator()
    plan = ContextPlan(use_mag=True)

    await orchestrator.execute_plan(
        plan=plan, query="query a", user_id=user_a, mag_provider=mock_provider
    )
    await orchestrator.execute_plan(
        plan=plan, query="query b", user_id=user_b, mag_provider=mock_provider
    )

    assert received_user_ids == [user_a, user_b]


@pytest.mark.asyncio
async def test_security_exception_not_swallowed():
    """Verify AuthorizationException is re-raised and never swallowed by failure isolation."""
    user_id = uuid.uuid4()

    mock_rag = MagicMock(spec=ContextProvider)
    mock_rag.retrieve = AsyncMock(
        side_effect=AuthorizationException("Unauthorized tenant access attempt")
    )

    orchestrator = ContextOrchestrator()
    plan = ContextPlan(use_rag=True)

    with pytest.raises(AuthorizationException) as exc_info:
        await orchestrator.execute_plan(
            plan=plan,
            query="Unauthorized doc query",
            user_id=user_id,
            rag_provider=mock_rag,
        )

    assert "Unauthorized tenant access attempt" in str(exc_info.value)


# ============================================================================
# Pipeline Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_rag_pipeline_intelligent_routing():
    """Verify RAGPipeline with routing_enabled=True dynamically selects sources based on query intent."""
    from app.cag.cache import LocalCacheStore, build_cache_key
    from app.cag.manager import CAGContextProvider, CAGManager
    from app.rag.pipeline import RAGPipeline
    from app.retrieval.vector_search import ScoredChunk

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value="Intelligently routed answer.")
    mock_embed = MagicMock()
    mock_embed.embed_query.return_value = [0.1] * 384

    cag_manager = CAGManager(store=LocalCacheStore())
    cag_key = build_cache_key("policy", "leave")
    cag_manager.set_context("policy", "leave", "Annual leave is 25 days.")
    cag_manager.policy.register_domain("policy", cag_key)
    cag_provider = CAGContextProvider(manager=cag_manager)

    mock_mag_provider = MagicMock(spec=ContextProvider)
    mock_mag_provider.source_name = "mag"
    mock_mag_provider.retrieve = AsyncMock(
        return_value=[
            MemoryContext(
                content="User project uses FastAPI.",
                memory_id="mem_p",
                memory_type="project_context",
            )
        ]
    )
    mock_mag_provider.extract_and_save = AsyncMock()

    pipeline = RAGPipeline(
        llm=mock_llm,
        embedding_service=mock_embed,
        cag_provider=cag_provider,
        cag_enabled=True,
        mag_provider=mock_mag_provider,
        mag_enabled=True,
        routing_enabled=True,
    )

    # Mock RAG retrieval
    pipeline._retrieve_and_rerank = AsyncMock(
        return_value=(
            [
                ScoredChunk(
                    chunk_id=uuid.uuid4(),
                    document_id=uuid.uuid4(),
                    filename="architecture.pdf",
                    chunk_index=0,
                    content="System documentation on Redis cache.",
                    page_number=1,
                    metadata={},
                    score=0.95,
                )
            ],
            12.0,
            4.0,
            1,
        )
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_chat_repo = MagicMock()
    mock_chat_session = MagicMock()
    mock_chat_session.id = uuid.uuid4()
    mock_chat_repo.create_session = AsyncMock(return_value=mock_chat_session)
    mock_chat_repo.add_message = AsyncMock()

    # 1. Chit-chat: "Hello" -> bypasses RAG, CAG, MAG
    res_chat = await pipeline.query(
        session=mock_session,
        query="Hello there!",
        user_id=uuid.uuid4(),
        session_id=mock_chat_session.id,
    )
    assert res_chat.metadata.routing_enabled is True
    assert res_chat.metadata.rag_selected is False
    assert res_chat.metadata.cag_selected is False
    assert res_chat.metadata.mag_selected is False
    assert res_chat.metadata.selected_sources == ["conversation"]

    # 2. Document query: "What does the architecture document say about Redis?" -> RAG selected
    res_doc = await pipeline.query(
        session=mock_session,
        query="What does the architecture document say about Redis?",
        user_id=uuid.uuid4(),
        session_id=mock_chat_session.id,
    )
    assert res_doc.metadata.rag_selected is True
    assert res_doc.metadata.cag_selected is False
    assert res_doc.metadata.mag_selected is False
    assert "rag" in res_doc.metadata.selected_sources

    # 3. Policy query: "What is our company leave policy?" -> CAG selected
    res_policy = await pipeline.query(
        session=mock_session,
        query="What is our company leave policy?",
        user_id=uuid.uuid4(),
        session_id=mock_chat_session.id,
    )
    assert res_policy.metadata.cag_selected is True
    assert res_policy.metadata.mag_selected is False
    assert "cag" in res_policy.metadata.selected_sources

    # 4. Combined query: "Based on my project and the architecture document..." -> MAG + RAG
    res_combined = await pipeline.query(
        session=mock_session,
        query="Based on my project and the architecture document, how do we deploy?",
        user_id=uuid.uuid4(),
        session_id=mock_chat_session.id,
    )
    assert res_combined.metadata.rag_selected is True
    assert res_combined.metadata.mag_selected is True
    assert "rag" in res_combined.metadata.selected_sources
    assert "mag" in res_combined.metadata.selected_sources
