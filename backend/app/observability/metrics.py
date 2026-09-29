"""Provider-independent metrics abstraction and in-memory thread-safe implementation."""

import threading
from abc import ABC, abstractmethod
from collections import deque
from typing import Any

from app.observability.events import EventType, ObservabilityEvent
from app.observability.models import PipelineMetrics


class LatencyStat:
    """Thread-safe running latency summary tracker (count, sum, min, max, avg)."""

    def __init__(self) -> None:
        self.count: int = 0
        self.total_sum: float = 0.0
        self.min_val: float | None = None
        self.max_val: float | None = None

    def add(self, value: float) -> None:
        self.count += 1
        self.total_sum += value
        if self.min_val is None or value < self.min_val:
            self.min_val = value
        if self.max_val is None or value > self.max_val:
            self.max_val = value

    @property
    def avg(self) -> float:
        return round(self.total_sum / self.count, 2) if self.count > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "min_ms": round(self.min_val, 2) if self.min_val is not None else None,
            "max_ms": round(self.max_val, 2) if self.max_val is not None else None,
            "avg_ms": self.avg,
        }


class MetricsRecorder(ABC):
    """Abstract interface for recording telemetry metrics and lifecycle events."""

    @abstractmethod
    def increment(
        self, metric_name: str, value: float = 1.0, tags: dict[str, str] | None = None
    ) -> None:
        """Increment a counter metric."""
        pass

    @abstractmethod
    def observe(self, metric_name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Record a histogram / gauge / duration observation."""
        pass

    @abstractmethod
    def record_event(self, event: ObservabilityEvent) -> None:
        """Record a discrete lifecycle event."""
        pass

    @abstractmethod
    def record_pipeline_metrics(self, metrics: PipelineMetrics) -> None:
        """Record all metrics from a completed or failed pipeline execution."""
        pass

    @abstractmethod
    def get_metrics_summary(self) -> dict[str, Any]:
        """Return an aggregated metrics summary dictionary."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset all in-memory metric state (useful for tests)."""
        pass


class InMemoryMetricsRecorder(MetricsRecorder):
    """Thread-safe, low-overhead in-memory metrics recorder without external dependencies.

    Keeps bounded historical samples to ensure zero memory leaks during prolonged operation.
    """

    def __init__(self, max_event_history: int = 100):
        self._lock = threading.Lock()
        self._max_event_history = max_event_history

        # Counters
        self._counters: dict[str, float] = {
            "requests_total": 0.0,
            "requests_failed": 0.0,
            "cag_hits_total": 0.0,
            "cag_misses_total": 0.0,
            "memories_retrieved_total": 0.0,
            "contexts_dropped_total": 0.0,
            "guardrail_checks_total": 0.0,
            "guardrail_allowed_total": 0.0,
            "guardrail_blocked_total": 0.0,
            "guardrail_sanitized_total": 0.0,
            "guardrail_input_violations_total": 0.0,
            "guardrail_retrieval_violations_total": 0.0,
            "guardrail_output_violations_total": 0.0,
            "guardrail_provider_failures_total": 0.0,
        }

        # Stage latency distributions
        self._latencies: dict[str, LatencyStat] = {
            "request_latency": LatencyStat(),
            "query_latency": LatencyStat(),
            "routing_latency": LatencyStat(),
            "rag_latency": LatencyStat(),
            "rerank_latency": LatencyStat(),
            "cag_latency": LatencyStat(),
            "mag_latency": LatencyStat(),
            "fusion_latency": LatencyStat(),
            "prompt_latency": LatencyStat(),
            "llm_latency": LatencyStat(),
            "llm_ttft": LatencyStat(),
            "guardrail_latency": LatencyStat(),
        }

        # Categories / breakdowns
        self._errors_by_type: dict[str, int] = {}
        self._dropped_by_reason: dict[str, int] = {}
        self._recent_events: deque[dict[str, Any]] = deque(maxlen=self._max_event_history)

    def increment(
        self, metric_name: str, value: float = 1.0, tags: dict[str, str] | None = None
    ) -> None:
        with self._lock:
            self._counters[metric_name] = self._counters.get(metric_name, 0.0) + value

    def observe(self, metric_name: str, value: float, tags: dict[str, str] | None = None) -> None:
        with self._lock:
            if metric_name not in self._latencies:
                self._latencies[metric_name] = LatencyStat()
            self._latencies[metric_name].add(value)

    def record_event(self, event: ObservabilityEvent) -> None:
        with self._lock:
            event_name = (
                event.event.value if isinstance(event.event, EventType) else str(event.event)
            )
            if event_name == EventType.REQUEST_STARTED.value:
                self._counters["requests_total"] += 1.0
            elif event_name in (EventType.REQUEST_FAILED.value, EventType.STAGE_FAILED.value):
                self._counters["requests_failed"] += 1.0
                err_type = str(event.data.get("error_type", "UnknownError"))
                self._errors_by_type[err_type] = self._errors_by_type.get(err_type, 0) + 1

            self._recent_events.append(event.to_dict())

    def record_pipeline_metrics(self, metrics: PipelineMetrics) -> None:
        with self._lock:
            # Latencies
            self._latencies["request_latency"].add(metrics.total_latency_ms)
            self._latencies["query_latency"].add(metrics.query_processing_latency_ms)
            if metrics.routing_enabled:
                self._latencies["routing_latency"].add(metrics.routing_latency_ms)
            if metrics.rag_selected:
                self._latencies["rag_latency"].add(metrics.retrieval_latency_ms)
                self._latencies["rerank_latency"].add(metrics.reranking_latency_ms)
            if metrics.cag_selected:
                self._latencies["cag_latency"].add(metrics.cag_latency_ms)
            if metrics.mag_selected:
                self._latencies["mag_latency"].add(metrics.mag_latency_ms)
            self._latencies["fusion_latency"].add(metrics.fusion_latency_ms)
            self._latencies["prompt_latency"].add(metrics.prompt_build_latency_ms)

            if metrics.llm_generation_latency_ms is not None:
                self._latencies["llm_latency"].add(metrics.llm_generation_latency_ms)
            if metrics.llm_time_to_first_token_ms is not None:
                self._latencies["llm_ttft"].add(metrics.llm_time_to_first_token_ms)

            # CAG counters
            if metrics.cag_cache_hit:
                self._counters["cag_hits_total"] += 1.0
            elif metrics.cag_cache_miss:
                self._counters["cag_misses_total"] += 1.0

            # MAG counters
            if metrics.memories_retrieved > 0:
                self._counters["memories_retrieved_total"] += float(metrics.memories_retrieved)

            # Fusion dropped contexts
            if metrics.contexts_dropped > 0:
                self._counters["contexts_dropped_total"] += float(metrics.contexts_dropped)
                for reason, count in metrics.dropped_reasons.items():
                    self._dropped_by_reason[reason] = self._dropped_by_reason.get(reason, 0) + count

            # Errors
            if metrics.has_error:
                self._counters["requests_failed"] += 1.0
                err_type = metrics.error_type or "UnknownError"
                self._errors_by_type[err_type] = self._errors_by_type.get(err_type, 0) + 1

    def get_metrics_summary(self) -> dict[str, Any]:
        with self._lock:
            cag_hits = self._counters.get("cag_hits_total", 0.0)
            cag_misses = self._counters.get("cag_misses_total", 0.0)
            total_cag_lookups = cag_hits + cag_misses
            cache_hit_rate = (
                round(cag_hits / total_cag_lookups, 4) if total_cag_lookups > 0 else 0.0
            )

            return {
                "counters": dict(self._counters),
                "cache_hit_rate": cache_hit_rate,
                "latencies": {name: stat.to_dict() for name, stat in self._latencies.items()},
                "errors_by_type": dict(self._errors_by_type),
                "contexts_dropped_by_reason": dict(self._dropped_by_reason),
                "recent_events_count": len(self._recent_events),
            }

    def reset(self) -> None:
        with self._lock:
            for k in self._counters:
                self._counters[k] = 0.0
            for k in self._latencies:
                self._latencies[k] = LatencyStat()
            self._errors_by_type.clear()
            self._dropped_by_reason.clear()
            self._recent_events.clear()


_global_recorder = InMemoryMetricsRecorder()


def get_metrics_recorder() -> MetricsRecorder:
    """Return the global MetricsRecorder singleton."""
    return _global_recorder
