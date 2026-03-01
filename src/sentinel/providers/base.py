"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from sentinel.core.circuit_breaker import CircuitBreaker
from sentinel.core.retry import RetryPolicy
from sentinel.domain.models import ChatRequest, ChatResponse


class LLMProvider(ABC):
    """Base class for all LLM providers."""

    def __init__(self, circuit_breaker: CircuitBreaker, retry_policy: RetryPolicy):
        self._circuit_breaker = circuit_breaker
        self._retry_policy = retry_policy

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the provider."""
        ...

    @property
    @abstractmethod
    def models(self) -> list[str]:
        """Return the list of models supported by the provider."""
        ...

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    async def complete(self, request: ChatRequest) -> ChatResponse: ...

    @abstractmethod
    async def stream(self, request: ChatRequest) -> AsyncIterator[str]: ...

    def is_available(self) -> bool:
        """Check if provider is available (circuit breaker allows execution)."""
        return self._circuit_breaker.can_execute()

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Expose circuit breaker for health/metrics (read-only)."""
        return self._circuit_breaker
