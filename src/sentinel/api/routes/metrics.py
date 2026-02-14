"""
Metrics endpoint.

Returns all collected in-memory metrics as a JSON snapshot
including request counts, performance percentiles, cache stats,
and security event counters.
"""

import contextlib
import logging
import time
from typing import Any

from fastapi import APIRouter, Request

from sentinel.core.metrics import get_metrics, metrics

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Operations"])


@router.post("/metrics/reset", summary="Reset all stats")
async def reset_stats(request: Request) -> dict[str, str]:
    """Reset metrics, circuit breaker, Redis cache, and uptime for a clean test run."""
    metrics.reset()
    registry = getattr(request.app.state, "registry", None)
    if registry is not None:
        for provider in registry.list_providers():
            if hasattr(provider, "circuit_breaker"):
                provider.circuit_breaker.reset()
    # Flush Redis cache so cached responses don't carry over
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client is not None:
        with contextlib.suppress(Exception):
            await redis_client.flushdb()
    request.app.state.start_time = time.time()
    return {"status": "ok", "message": "Stats and cache reset"}


@router.get("/metrics", summary="Operational metrics")
async def metrics_endpoint() -> dict[str, Any]:
    """Return all collected metrics as a JSON snapshot.

    Includes:
    - Request counts (total, by status, by endpoint, active)
    - Performance percentiles (avg, p50, p95, p99)
    - Cache stats (hits, misses, hit rate)
    - Security events (PII detections, blocks, rate limits, circuit breaker trips)
    """
    return get_metrics()
