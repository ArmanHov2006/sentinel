"""
Health check endpoint.

Returns the overall system health including subsystem checks
for Redis connectivity and circuit breaker states.
"""

import logging
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Request

from sentinel.api.schemas.health import (
    CircuitBreakerCheck,
    HealthChecks,
    HealthResponse,
    RedisHealthCheck,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Operations"])


@router.get("/health", summary="System health check")
async def health_check(request: Request) -> HealthResponse:
    """Return overall system health with subsystem checks.

    Checks Redis connectivity (with latency measurement) and all
    circuit breaker states to determine the aggregate status.

    Status logic:
    - Redis down AND any circuit breaker OPEN -> unhealthy
    - Redis down OR any circuit breaker OPEN  -> degraded
    - Otherwise                               -> healthy
    """
    # --- Redis health check ---
    redis_healthy = False
    redis_latency_ms = 0.0
    redis_client = getattr(request.app.state, "redis", None)

    if redis_client is not None:
        start = time.perf_counter()
        try:
            await redis_client.ping()
            redis_healthy = True
        except Exception:
            redis_healthy = False
        redis_latency_ms = round((time.perf_counter() - start) * 1000, 2)

    # --- Circuit breaker checks ---
    circuit_breakers: dict[str, CircuitBreakerCheck] = {}
    registry = getattr(request.app.state, "registry", None)

    if registry is not None:
        for provider in registry.list_providers():
            if hasattr(provider, "circuit_breaker"):
                cb = provider.circuit_breaker
                last_failure = None
                if cb.last_failure_time > 0:
                    last_failure = datetime.fromtimestamp(cb.last_failure_time, tz=UTC)
                circuit_breakers[provider.name] = CircuitBreakerCheck(
                    state=cb.state.value.upper(),
                    failure_count=cb.failure_count,
                    last_failure=last_failure,
                )

    # --- Determine overall status ---
    redis_down = not redis_healthy
    any_breaker_open = any(cb.state == "OPEN" for cb in circuit_breakers.values())

    if redis_down and any_breaker_open:
        status = "unhealthy"
    elif redis_down or any_breaker_open:
        status = "degraded"
    else:
        status = "healthy"

    # --- Uptime ---
    start_time = getattr(request.app.state, "start_time", time.time())
    uptime_seconds = round(time.time() - start_time, 1)

    return HealthResponse(
        status=status,
        version="0.1.0",
        timestamp=datetime.now(UTC),
        uptime_seconds=uptime_seconds,
        checks=HealthChecks(
            redis=RedisHealthCheck(
                status="healthy" if redis_healthy else "unhealthy",
                latency_ms=redis_latency_ms,
            ),
            circuit_breakers=circuit_breakers,
        ),
    )
