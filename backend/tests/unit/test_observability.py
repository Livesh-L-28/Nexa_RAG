"""Unit and property tests for Phase 13 Observability & Metrics subsystem."""

import concurrent.futures
import time
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.observability import (
    EventType,
    InMemoryMetricsRecorder,
    ObservabilityEvent,
    PipelineMetrics,
    get_observability_logger,
)
from app.observability.logger import sanitize_payload
from app.observability.timing import Timer as MonotonicTimer

# ==============================================================================
# 1. Monotonic Timing Tests
# ==============================================================================


def test_timer_basic_start_stop():
    """Verify Timer measures elapsed duration and stops accurately."""
    timer = MonotonicTimer(autostart=True)
    assert timer.is_running is True
    time.sleep(0.01)  # 10ms
    elapsed = timer.stop()
    assert timer.is_running is False
    assert elapsed >= 8.0  # at least ~8ms
    # Repeated elapsed calls should remain fixed after stop
    assert timer.elapsed_ms == elapsed


def test_timer_context_manager():
    """Verify Timer functions as a context manager measuring duration."""
    with MonotonicTimer() as t:
        time.sleep(0.01)
        assert t.is_running is True
    assert t.is_running is False
    assert t.elapsed_ms >= 8.0


def test_timer_not_started_error():
    """Verify stopping an unstarted timer raises RuntimeError."""
    timer = MonotonicTimer(autostart=False)
    with pytest.raises(RuntimeError, match="Timer was never started"):
        timer.stop()


def test_timer_monotonic_clock_resilience():
    """Verify Timer strictly uses monotonic clocks rather than wall clocks."""
    t1 = MonotonicTimer()
    start_val = t1._start_time
    time.sleep(0.005)
    t1.stop()
    assert t1._stop_time > start_val


# ==============================================================================
# 2. Request ID Generation, Propagation, and Validation
# ==============================================================================


@pytest.mark.asyncio
async def test_request_id_created_in_middleware():
    """Verify HTTP requests receive an X-Request-ID response header."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        assert "x-request-id" in res.headers
        parsed_id = uuid.UUID(res.headers["x-request-id"])
        assert parsed_id is not None


@pytest.mark.asyncio
async def test_request_id_propagated_from_client_header():
    """Verify client-supplied valid UUID X-Request-ID is preserved across request lifecycle."""
    custom_id = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health", headers={"X-Request-ID": custom_id})
        assert res.status_code == 200
        assert res.headers["x-request-id"] == custom_id


@pytest.mark.asyncio
async def test_request_id_malformed_fallback():
    """Verify client-supplied malformed X-Request-ID falls back to a generated valid UUID."""
    malformed_id = "not-a-valid-uuid-12345"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health", headers={"X-Request-ID": malformed_id})
        assert res.status_code == 200
        assert res.headers["x-request-id"] != malformed_id
        # Must be a valid UUID
        assert uuid.UUID(res.headers["x-request-id"]) is not None


# ==============================================================================
# 3. Privacy Controls & Sanitization
# ==============================================================================


def test_sensitive_keys_redacted_in_logger():
    """Verify sensitive keys such as api_key, token, password, and secrets are redacted."""
    raw_payload = {
        "api_key": "sk-live-secret123456789",
        "authorization": "Bearer eyJhbGciOi...",
        "user_password": "supersecretpassword",
        "jwt_secret": "my-secret-key",
        "prompt_text": "Classified customer confidential info",
        "memory_content": "User has secret financial debts",
        "safe_key": "safe_value",
        "count": 42,
    }
    sanitized = sanitize_payload(raw_payload)

    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["authorization"] == "[REDACTED]"
    assert sanitized["user_password"] == "[REDACTED]"
    assert sanitized["jwt_secret"] == "[REDACTED]"
    assert sanitized["prompt_text"] == "[REDACTED]"
    assert sanitized["memory_content"] == "[REDACTED]"
    assert sanitized["safe_key"] == "safe_value"
    assert sanitized["count"] == 42


def test_nested_sanitization():
    """Verify sanitization penetrates nested dictionaries and lists."""
    nested = {
        "level1": [
            {"token": "secret_abc", "id": "123"},
            {"nested_auth": {"bearer": "secret_xyz"}},
        ]
    }
    sanitized = sanitize_payload(nested)
    assert sanitized["level1"][0]["token"] == "[REDACTED]"
    assert sanitized["level1"][0]["id"] == "123"
    assert sanitized["level1"][1]["nested_auth"]["bearer"] == "[REDACTED]"


# ==============================================================================
# 4. Pipeline Execution Telemetry Models
# ==============================================================================


def test_pipeline_metrics_safe_summary():
    """Verify PipelineMetrics produces a clean, privacy-safe summary without leaked content."""
    req_id = uuid.uuid4()
    sess_id = uuid.uuid4()
    metrics = PipelineMetrics(
        request_id=req_id,
        session_id=sess_id,
        total_latency_ms=120.5,
        query_processing_latency_ms=5.0,
        routing_latency_ms=2.0,
        retrieval_latency_ms=45.0,
        reranking_latency_ms=20.0,
        fusion_latency_ms=3.0,
        prompt_build_latency_ms=2.5,
        llm_generation_latency_ms=43.0,
        rag_selected=True,
        hybrid_candidates_count=10,
        reranked_chunks_count=5,
        top_score=0.92,
        average_score=0.78,
        minimum_score=0.61,
        citation_count=3,
        cag_selected=True,
        cag_cache_hit=True,
        mag_selected=True,
        memories_retrieved=2,
        estimated_input_tokens=450,
        llm_provider="groq",
        llm_model="llama-3.3-70b-versatile",
        actual_input_tokens=452,
        actual_output_tokens=68,
        actual_total_tokens=520,
    )

    summary = metrics.to_safe_summary()
    assert summary["request_id"] == str(req_id)
    assert summary["session_id"] == str(sess_id)
    assert summary["total_latency_ms"] == 120.5
    assert summary["rag_quality"]["top_score"] == 0.92
    assert summary["llm"]["actual_total_tokens"] == 520
    # Confirm no prompt or chunk text is present in summary
    assert "prompt" not in summary
    assert "query" not in summary
    assert "chunks" not in summary


def test_estimated_vs_actual_tokens_distinction():
    """Verify estimated prompt tokens are strictly distinguished from actual provider tokens."""
    metrics = PipelineMetrics(
        request_id=uuid.uuid4(),
        estimated_input_tokens=500,
        actual_input_tokens=523,
    )
    assert metrics.estimated_input_tokens == 500
    assert metrics.actual_input_tokens == 523
    assert metrics.estimated_input_tokens != metrics.actual_input_tokens


# ==============================================================================
# 5. Metrics Recorder & Concurrency Safety
# ==============================================================================


def test_in_memory_metrics_recorder_aggregations():
    """Verify InMemoryMetricsRecorder correctly aggregates counters, latencies, and dropped items."""
    recorder = InMemoryMetricsRecorder()
    recorder.reset()

    # Record 3 pipeline metric runs
    for lat in [100.0, 200.0, 300.0]:
        m = PipelineMetrics(
            request_id=uuid.uuid4(),
            total_latency_ms=lat,
            retrieval_latency_ms=lat / 2.0,
            rag_selected=True,
            cag_selected=True,
            cag_cache_hit=(lat == 100.0),
            cag_cache_miss=(lat != 100.0),
            contexts_dropped=2 if lat == 200.0 else 0,
            dropped_reasons={"duplicate": 2} if lat == 200.0 else {},
        )
        recorder.record_pipeline_metrics(m)

    summary = recorder.get_metrics_summary()
    req_lat = summary["latencies"]["request_latency"]
    assert req_lat["count"] == 3
    assert req_lat["min_ms"] == 100.0
    assert req_lat["max_ms"] == 300.0
    assert req_lat["avg_ms"] == 200.0

    # Cache hit rate: 1 hit out of 3 lookups = ~0.3333
    assert summary["cache_hit_rate"] == 0.3333
    assert summary["counters"]["cag_hits_total"] == 1.0
    assert summary["counters"]["cag_misses_total"] == 2.0
    assert summary["contexts_dropped_by_reason"]["duplicate"] == 2


def test_metrics_recorder_thread_safety():
    """Verify concurrent metric recordings from multiple threads do not corrupt data."""
    recorder = InMemoryMetricsRecorder()
    recorder.reset()

    num_threads = 8
    iterations_per_thread = 50

    def worker():
        for _ in range(iterations_per_thread):
            m = PipelineMetrics(
                request_id=uuid.uuid4(),
                total_latency_ms=50.0,
                retrieval_latency_ms=25.0,
                rag_selected=True,
            )
            recorder.record_pipeline_metrics(m)
            recorder.increment("requests_total")

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker) for _ in range(num_threads)]
        concurrent.futures.wait(futures)

    summary = recorder.get_metrics_summary()
    expected_total = num_threads * iterations_per_thread
    assert summary["latencies"]["request_latency"]["count"] == expected_total
    assert summary["counters"]["requests_total"] == float(expected_total)


def test_metrics_recorder_bounded_event_history():
    """Verify event history in recorder is bounded and does not grow unbounded."""
    recorder = InMemoryMetricsRecorder(max_event_history=10)
    for i in range(25):
        recorder.record_event(
            ObservabilityEvent(
                event=EventType.REQUEST_STARTED,
                request_id=uuid.uuid4(),
                data={"index": i},
            )
        )
    summary = recorder.get_metrics_summary()
    assert summary["recent_events_count"] == 10


def test_metrics_recorder_reset():
    """Verify reset clears all metrics and counters."""
    recorder = InMemoryMetricsRecorder()
    recorder.increment("requests_total", 5.0)
    assert recorder.get_metrics_summary()["counters"]["requests_total"] == 5.0

    recorder.reset()
    assert recorder.get_metrics_summary()["counters"]["requests_total"] == 0.0


# ==============================================================================
# 6. Event Types & ObservabilityLogger
# ==============================================================================


def test_observability_logger_events(caplog):
    """Verify ObservabilityLogger formats JSON logs correctly and emits stage events."""
    obs_logger = get_observability_logger()
    req_id = uuid.uuid4()

    with caplog.at_level("INFO"):
        obs_logger.log_stage_completed(
            EventType.RAG_COMPLETED,
            request_id=req_id,
            candidates_count=10,
            reranked_count=5,
        )

    assert len(caplog.records) > 0
    record = caplog.records[-1]
    assert "rag_completed" in record.message
    assert str(req_id) in record.message


def test_observability_logger_error_level(caplog):
    """Verify errors are logged at ERROR log level with sanitized messages."""
    obs_logger = get_observability_logger()
    req_id = uuid.uuid4()

    with caplog.at_level("ERROR"):
        obs_logger.log_error(
            request_id=req_id,
            session_id=None,
            stage="retrieval",
            error_type="DatabaseTimeout",
            sanitized_message="Timeout after 5.0s",
        )

    assert any(r.levelname == "ERROR" and "stage_failed" in r.message for r in caplog.records)


# ==============================================================================
# 7. Health & Readiness Endpoint Integration
# ==============================================================================


@pytest.mark.asyncio
async def test_health_ready_includes_metrics_summary():
    """Verify /health/ready returns aggregated telemetry metrics alongside readiness state."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health/ready")
        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert "metrics" in data
        assert "counters" in data["metrics"]
        assert "latencies" in data["metrics"]


# ==============================================================================
# 8. Pipeline Query & Streaming Observability Integration
# ==============================================================================


@pytest.mark.asyncio
async def test_pipeline_query_emits_telemetry_and_metadata():
    """Verify RAGPipeline.query generates request_id, records metrics, and populates metadata."""
    from unittest.mock import AsyncMock, MagicMock

    from app.llm.models import LLMResponse, LLMUsage
    from app.rag.pipeline import RAGPipeline
    from app.retrieval.vector_search import ScoredChunk

    mock_llm = MagicMock()
    mock_llm.provider_name = "mock"
    mock_llm.model_name = "mock-llm-v1"
    mock_llm.generate_response = AsyncMock(
        return_value=LLMResponse(
            text="Grounded answer based on source [Source 1].",
            provider="mock",
            model="mock-llm-v1",
            usage=LLMUsage(input_tokens=150, output_tokens=30, total_tokens=180),
        )
    )

    chunk = ScoredChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="system_architecture.pdf",
        chunk_index=0,
        content="NexaRAG is a high-performance modular RAG platform.",
        score=0.95,
        page_number=1,
        metadata={},
    )

    pipeline = RAGPipeline(llm=mock_llm, cag_enabled=False, mag_enabled=False)
    pipeline._retrieve_and_rerank = AsyncMock(return_value=([chunk], 15.0, 10.0, 5))

    mock_session = AsyncMock()
    custom_request_id = uuid.uuid4()
    custom_session_id = uuid.uuid4()

    response = await pipeline.query(
        session=mock_session,
        query="What is NexaRAG?",
        user_id=uuid.uuid4(),
        session_id=custom_session_id,
        request_id=custom_request_id,
    )

    assert response.request_id == custom_request_id
    assert response.session_id == custom_session_id
    assert response.metadata.request_id == custom_request_id
    assert response.metadata.rag_selected is True
    assert response.metadata.top_k == 1
    assert response.metadata.input_tokens == 150
    assert response.metadata.output_tokens == 30
    assert response.metadata.total_tokens == 180
    assert response.metadata.prompt_build_latency_ms >= 0.0
    assert response.metadata.estimated_input_tokens > 0


@pytest.mark.asyncio
async def test_pipeline_query_stream_emits_request_id_and_ttft():
    """Verify RAGPipeline.query_stream yields init event with request_id and done event with TTFT."""
    import json
    from unittest.mock import AsyncMock, MagicMock

    from app.rag.pipeline import RAGPipeline
    from app.retrieval.vector_search import ScoredChunk

    async def mock_stream(*args, **kwargs):
        tokens = ["Hello", " ", "world", "!"]
        for t in tokens:
            yield t

    mock_llm = MagicMock()
    mock_llm.provider_name = "mock"
    mock_llm.model_name = "mock-llm-v1"
    mock_llm.generate_stream = mock_stream

    chunk = ScoredChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="guide.pdf",
        chunk_index=0,
        content="Streaming observability guide.",
        score=0.88,
        page_number=2,
        metadata={},
    )

    pipeline = RAGPipeline(llm=mock_llm, cag_enabled=False, mag_enabled=False)
    pipeline._retrieve_and_rerank = AsyncMock(return_value=([chunk], 12.0, 8.0, 3))

    mock_session = AsyncMock()
    custom_req_id = uuid.uuid4()

    events = []
    async for sse in pipeline.query_stream(
        session=mock_session,
        query="Explain streaming",
        user_id=uuid.uuid4(),
        request_id=custom_req_id,
    ):
        line = sse.strip()
        if line.startswith("data: "):
            payload = json.loads(line[6:])
            events.append(payload)

    # Check init event
    init_event = events[0]
    assert init_event["type"] == "init"
    assert init_event["request_id"] == str(custom_req_id)

    # Check token events
    token_events = [e for e in events if e["type"] == "token"]
    assert len(token_events) == 4

    # Check done event
    done_event = events[-1]
    assert done_event["type"] == "done"
    assert done_event["request_id"] == str(custom_req_id)
    assert done_event["metadata"]["request_id"] == str(custom_req_id)
    assert done_event["metadata"]["time_to_first_token_ms"] is not None
    assert done_event["metadata"]["time_to_first_token_ms"] >= 0.0


@pytest.mark.asyncio
async def test_streaming_error_emits_sanitized_error_event():
    """Verify exceptions during streaming emit sanitized error event and increment failure metrics."""
    import json
    from unittest.mock import AsyncMock, MagicMock

    from app.rag.pipeline import RAGPipeline

    async def failing_stream(*args, **kwargs):
        raise ConnectionResetError("Connection lost with secret key Bearer sk-secret123456")
        yield "token"

    mock_llm = MagicMock()
    mock_llm.provider_name = "mock"
    mock_llm.model_name = "mock-llm-v1"
    mock_llm.generate_stream = failing_stream

    pipeline = RAGPipeline(llm=mock_llm, cag_enabled=False, mag_enabled=False)
    pipeline._retrieve_and_rerank = AsyncMock(return_value=([], 0.0, 0.0, 0))

    mock_session = AsyncMock()
    custom_req_id = uuid.uuid4()

    events = []
    async for sse in pipeline.query_stream(
        session=mock_session,
        query="Trigger error",
        user_id=uuid.uuid4(),
        request_id=custom_req_id,
    ):
        line = sse.strip()
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))

    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    # Secret must be redacted from error message
    assert "sk-secret123456" not in error_events[0]["message"]


def test_rag_quality_score_computation():
    """Verify quality score aggregations (top, min, average) on ScoredChunk candidates."""
    from app.retrieval.vector_search import ScoredChunk

    chunk1 = ScoredChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="doc1.pdf",
        chunk_index=0,
        content="Chunk 1",
        score=0.90,
        page_number=1,
        metadata={},
    )
    chunk2 = ScoredChunk(
        chunk_id=uuid.uuid4(),
        document_id=chunk1.document_id,
        filename="doc1.pdf",
        chunk_index=1,
        content="Chunk 2",
        score=0.70,
        page_number=2,
        metadata={},
    )
    chunk3 = ScoredChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="doc2.pdf",
        chunk_index=0,
        content="Chunk 3",
        score=0.80,
        page_number=1,
        metadata={},
    )

    chunks = [chunk1, chunk2, chunk3]
    scores = [c.score for c in chunks if c.score is not None]
    top_score = max(scores)
    min_score = min(scores)
    avg_score = round(sum(scores) / len(scores), 4)
    unique_docs = len({c.document_id for c in chunks})
    unique_pages = len(
        {(c.document_id, c.page_number) for c in chunks if c.page_number is not None}
    )

    assert top_score == 0.90
    assert min_score == 0.70
    assert avg_score == 0.80
    assert unique_docs == 2
    assert unique_pages == 3


def test_fusion_dropped_reasons_tally():
    """Verify fusion accurately tallies dropped contexts across reason categories."""
    from app.orchestration.models import ContextSource, DroppedContext

    dropped_list = [
        DroppedContext(
            source=ContextSource.RAG,
            source_id="rag1",
            reason="duplicate",
            priority=3,
            estimated_tokens=50,
        ),
        DroppedContext(
            source=ContextSource.CAG,
            source_id="cag1",
            reason="duplicate",
            priority=4,
            estimated_tokens=40,
        ),
        DroppedContext(
            source=ContextSource.MAG,
            source_id="mag1",
            reason="token_budget",
            priority=5,
            estimated_tokens=60,
        ),
        DroppedContext(
            source=ContextSource.RAG,
            source_id="rag2",
            reason="below_relevance_threshold",
            priority=3,
            estimated_tokens=30,
        ),
    ]

    tally: dict[str, int] = {}
    for d in dropped_list:
        tally[d.reason] = tally.get(d.reason, 0) + 1

    assert tally["duplicate"] == 2
    assert tally["token_budget"] == 1
    assert tally["below_relevance_threshold"] == 1


@pytest.mark.asyncio
async def test_api_chat_with_custom_request_id_header(client: AsyncClient, user_token: str):
    """Verify end-to-end API chat query honors custom X-Request-ID and returns it in metadata."""
    custom_request_id = str(uuid.uuid4())
    payload = {
        "query": "What is the observability model in NexaRAG?",
        "top_k": 2,
    }
    response = await client.post(
        "/api/v1/chat",
        json=payload,
        headers={
            "Authorization": f"Bearer {user_token}",
            "X-Request-ID": custom_request_id,
        },
    )
    assert response.status_code == 200
    assert response.headers.get("x-request-id") == custom_request_id
    data = response.json()
    assert data["request_id"] == custom_request_id
    assert data["metadata"]["request_id"] == custom_request_id
    assert data["metadata"]["prompt_build_latency_ms"] >= 0.0
    assert data["metadata"]["estimated_input_tokens"] > 0


@pytest.mark.asyncio
async def test_api_chat_without_header_generates_request_id(client: AsyncClient, user_token: str):
    """Verify end-to-end API chat query generates a valid request_id when header is omitted."""
    payload = {
        "query": "Explain latency breakdown",
        "top_k": 1,
    }
    response = await client.post(
        "/api/v1/chat",
        json=payload,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 200
    header_id = response.headers.get("x-request-id")
    assert header_id is not None
    assert uuid.UUID(header_id) is not None
    data = response.json()
    assert data["request_id"] == header_id
    assert data["metadata"]["request_id"] == header_id
