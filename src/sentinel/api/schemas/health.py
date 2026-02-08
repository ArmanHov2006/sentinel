"""Health and operational response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class RedisHealthCheck(BaseModel):
    """Redis health check result."""

    status: Literal["healthy", "unhealthy"]
    latency_ms: float


class CircuitBreakerCheck(BaseModel):
    """Circuit breaker state for a single provider."""

    state: Literal["CLOSED", "OPEN", "HALF_OPEN"]
    failure_count: int
    last_failure: datetime | None = None


class HealthChecks(BaseModel):
    """Container for all health checks."""

    redis: RedisHealthCheck
    circuit_breakers: dict[str, CircuitBreakerCheck]


class HealthResponse(BaseModel):
    """Full health check response with subsystem checks."""

    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    timestamp: datetime
    uptime_seconds: float
    checks: HealthChecks
