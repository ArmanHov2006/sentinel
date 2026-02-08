import logging
import time
from enum import Enum

from sentinel.core.metrics import metrics

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    Closed = "closed"
    Open = "open"
    HalfOpen = "half_open"


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = CircuitBreakerState.Closed

    def can_execute(self) -> bool:
        if self.state == CircuitBreakerState.Open:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitBreakerState.HalfOpen
                return True
            else:
                return False
        else:
            return True

    def record_success(self):
        self.failure_count = 0
        self.state = CircuitBreakerState.Closed

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = CircuitBreakerState.Closed

    def record_failure(self) -> None:
        """Record a failed execution attempt."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.Open
            metrics.increment("circuit_breaker_trips")
            logger.warning(
                "Circuit breaker tripped to OPEN after %d failures",
                self.failure_count,
            )
