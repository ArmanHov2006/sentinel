"""Prometheus metrics and legacy in-memory metrics collector."""

import threading
from collections import deque
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

sentinel_cost_total = Counter(
    "sentinel_cost_total", "Total cost of requests", ["provider", "model"]
)

sentinel_active_requests = Gauge(
    "sentinel_active_requests", "Number of active (in-flight) requests"
)

sentinel_requests_total = Counter(
    "sentinel_requests_total",
    "Total number of completed requests",
    ["provider", "model", "status_code"],
)

sentinel_request_duration_seconds = Histogram(
    "sentinel_request_duration_seconds",
    "Request latency in seconds",
    ["provider", "model"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)

sentinel_tokens_total = Counter(
    "sentinel_tokens_total", "Token usage count", ["provider", "model", "type"]
)

sentinel_cache_hits_total = Counter("sentinel_cache_hits_total", "Total number of cache hits")

sentinel_cache_misses_total = Counter("sentinel_cache_misses_total", "Total number of cache misses")

sentinel_circuit_breaker_state = Gauge(
    "sentinel_circuit_breaker_state", "Circuit breaker state: 0=closed, 1=open", ["provider"]
)

sentinel_pii_detections_total = Counter(
    "sentinel_pii_detections_total",
    "Total number of PII detections (redact/block actions)",
    ["action"],
)


class SentinelMetrics:
    def record_request(self, provider: str, model: str, status_code: int) -> None:
        sentinel_requests_total.labels(
            provider=provider, model=model, status_code=status_code
        ).inc()

    def record_latency(self, provider: str, model: str, duration: float) -> None:
        sentinel_request_duration_seconds.labels(provider=provider, model=model).observe(duration)

    def record_cost(self, cost: Any) -> None:
        sentinel_cost_total.labels(provider=cost.usage.provider, model=cost.usage.model).inc(
            cost.total_cost
        )

    def record_cache_hit(self) -> None:
        sentinel_cache_hits_total.inc()

    def record_cache_miss(self) -> None:
        sentinel_cache_misses_total.inc()

    def record_tokens(self, provider: str, model: str, token_type: str, count: int) -> None:
        sentinel_tokens_total.labels(provider=provider, model=model, token_type=token_type).inc(
            count
        )

    def record_circuit_breaker(self, provider: str, state: int) -> None:
        sentinel_circuit_breaker_state.labels(provider=provider).set(state)

    def record_pii(self, action: str) -> None:
        sentinel_pii_detections_total.labels(action=action).inc()

    def increment_active_requests(self) -> None:
        sentinel_active_requests.inc()

    def decrement_active_requests(self) -> None:
        sentinel_active_requests.dec()


sentinel_metrics = SentinelMetrics()


# Legacy in-memory metrics (for /metrics JSON, reset, dashboard, rate_limiter, cache, circuit_breaker)
class MetricsCollector:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {
            "requests_total": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "pii_detections": 0,
            "pii_blocks": 0,
            "injection_detections": 0,
            "injection_blocks": 0,
            "rate_limit_rejections": 0,
            "circuit_breaker_trips": 0,
        }
        self._gauges: dict[str, int] = {"active_requests": 0}
        self._counter_dicts: dict[str, dict[str, int]] = {
            "requests_by_status": {},
            "requests_by_endpoint": {},
        }
        self._observations: dict[str, deque[float]] = {
            "response_time_seconds": deque(maxlen=1000),
        }

    def increment(self, metric_name: str, amount: int = 1) -> None:
        with self._lock:
            if metric_name in self._counters:
                self._counters[metric_name] += amount
            elif metric_name in self._gauges:
                self._gauges[metric_name] += amount

    def decrement(self, metric_name: str, amount: int = 1) -> None:
        with self._lock:
            if metric_name in self._gauges:
                self._gauges[metric_name] -= amount

    def observe(self, metric_name: str, value: float) -> None:
        with self._lock:
            if metric_name in self._observations:
                self._observations[metric_name].append(value)

    def increment_dict(self, metric_name: str, key: str, amount: int = 1) -> None:
        with self._lock:
            if metric_name in self._counter_dicts:
                current = self._counter_dicts[metric_name].get(key, 0)
                self._counter_dicts[metric_name][key] = current + amount

    def reset(self) -> None:
        with self._lock:
            self._counters = {k: 0 for k in self._counters}
            self._gauges = {k: 0 for k in self._gauges}
            self._counter_dicts = {k: {} for k in self._counter_dicts}
            self._observations = {k: deque(maxlen=1000) for k in self._observations}

    def get_metrics(self) -> dict[str, Any]:
        with self._lock:
            response_times = list(self._observations["response_time_seconds"])
            counters_snapshot = dict(self._counters)
            gauges_snapshot = dict(self._gauges)
            by_status = dict(self._counter_dicts["requests_by_status"])
            by_endpoint = dict(self._counter_dicts["requests_by_endpoint"])
        avg_ms = 0.0
        p50_ms = 0.0
        p95_ms = 0.0
        p99_ms = 0.0
        if response_times:
            sorted_times = sorted(response_times)
            n = len(sorted_times)
            avg_ms = round(sum(sorted_times) / n * 1000, 1)
            p50_ms = round(sorted_times[int(n * 0.5)] * 1000, 1)
            p95_ms = round(sorted_times[min(int(n * 0.95), n - 1)] * 1000, 1)
            p99_ms = round(sorted_times[min(int(n * 0.99), n - 1)] * 1000, 1)
        cache_hits = counters_snapshot["cache_hits"]
        cache_misses = counters_snapshot["cache_misses"]
        total_cache = cache_hits + cache_misses
        hit_rate = round(cache_hits / total_cache, 3) if total_cache > 0 else 0.0
        return {
            "requests": {
                "total": counters_snapshot["requests_total"],
                "by_status": by_status,
                "by_endpoint": by_endpoint,
                "active": gauges_snapshot["active_requests"],
            },
            "performance": {
                "avg_response_time_ms": avg_ms,
                "p50_response_time_ms": p50_ms,
                "p95_response_time_ms": p95_ms,
                "p99_response_time_ms": p99_ms,
            },
            "cache": {"hits": cache_hits, "misses": cache_misses, "hit_rate": hit_rate},
            "security": {
                "pii_detections": counters_snapshot["pii_detections"],
                "pii_blocks": counters_snapshot["pii_blocks"],
                "injection_detections": counters_snapshot["injection_detections"],
                "injection_blocks": counters_snapshot["injection_blocks"],
                "rate_limit_rejections": counters_snapshot["rate_limit_rejections"],
                "circuit_breaker_trips": counters_snapshot["circuit_breaker_trips"],
            },
        }


metrics = MetricsCollector()


def get_metrics() -> dict[str, Any]:
    return metrics.get_metrics()
