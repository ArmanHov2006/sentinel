"""
Domain-level exceptions.

Hierarchical exceptions allow catching at different granularities.
"""


class SentinelError(Exception):
    """Base exception for all sentinel errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        """Convert exception to dictionary for serialization."""
        return {"message": self.message, "details": self.details, "type": type(self).__name__}


class ProviderError(SentinelError):
    """Error from an LLM provider."""

    def __init__(
        self,
        message: str,
        provider: str,
        status_code: int | None = None,
        details: dict | None = None,
    ):
        super().__init__(message, details)
        self.provider = provider
        self.status_code = status_code


class ProviderUnavailableError(ProviderError):
    """Provider is temporarily unavailable (timeout, 5xx, connection error)."""

    pass


class ProviderRateLimitError(ProviderError):
    """Provider rate limit exceeded (429)."""

    pass


class CircuitOpenError(SentinelError):
    """Circuit breaker is open."""

    pass
