"""
In-memory metrics collector for Sentinel.

Provides counters, gauges, and observation-based metrics.
Thread-safe singleton accessible from anywhere in the application.
"""

import threading
from collections import deque
from typing import Any


class MetricsCollector:
    """In-memory metrics collector with counters, gauges, and observations.

    All operations are thread-safe via a shared lock. The collector is
    designed to be used as a module-level singleton.
    """

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
        self._gauges: dict[str, int] = {
            "active_requests": 0,
        }
        self._counter_dicts: dict[str, dict[str, int]] = {
            "requests_by_status": {},
            "requests_by_endpoint": {},
        }
        self._observations: dict[str, deque[float]] = {
            "response_time_seconds": deque(maxlen=1000),
        }

    def increment(self, metric_name: str, amount: int = 1) -> None:
        """Increment a counter or gauge metric."""
        with self._lock:
            if metric_name in self._counters:
                self._counters[metric_name] += amount
            elif metric_name in self._gauges:
                self._gauges[metric_name] += amount

    def decrement(self, metric_name: str, amount: int = 1) -> None:
        """Decrement a gauge metric."""
        with self._lock:
            if metric_name in self._gauges:
                self._gauges[metric_name] -= amount

    def observe(self, metric_name: str, value: float) -> None:
        """Record an observation for a metric (e.g., response time)."""
        with self._lock:
            if metric_name in self._observations:
                self._observations[metric_name].append(value)

    def increment_dict(self, metric_name: str, key: str, amount: int = 1) -> None:
        """Increment a value in a counter dict (e.g., requests_by_status)."""
        with self._lock:
            if metric_name in self._counter_dicts:
                current = self._counter_dicts[metric_name].get(key, 0)
                self._counter_dicts[metric_name][key] = current + amount

    def reset(self) -> None:
        """Reset all metrics to initial state."""
        with self._lock:
            self._counters = {k: 0 for k in self._counters}
            self._gauges = {k: 0 for k in self._gauges}
            self._counter_dicts = {k: {} for k in self._counter_dicts}
            self._observations = {k: deque(maxlen=1000) for k in self._observations}

    def get_metrics(self) -> dict[str, Any]:
        """Return a snapshot of all metrics as a structured dict.

        Calculates percentiles from observed response times and
        computes derived metrics like cache hit rate.
        """
        with self._lock:
            response_times = list(self._observations["response_time_seconds"])
            counters_snapshot = dict(self._counters)
            gauges_snapshot = dict(self._gauges)
            by_status = dict(self._counter_dicts["requests_by_status"])
            by_endpoint = dict(self._counter_dicts["requests_by_endpoint"])

        # Calculate percentiles (outside lock — operates on copied data)
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
            "cache": {
                "hits": cache_hits,
                "misses": cache_misses,
                "hit_rate": hit_rate,
            },
            "security": {
                "pii_detections": counters_snapshot["pii_detections"],
                "pii_blocks": counters_snapshot["pii_blocks"],
                "injection_detections": counters_snapshot["injection_detections"],
                "injection_blocks": counters_snapshot["injection_blocks"],
                "rate_limit_rejections": counters_snapshot["rate_limit_rejections"],
                "circuit_breaker_trips": counters_snapshot["circuit_breaker_trips"],
            },
        }


# Module-level singleton
metrics = MetricsCollector()


def get_metrics() -> dict[str, Any]:
    """Get a snapshot of all metrics from the global collector."""
    return metrics.get_metrics()
