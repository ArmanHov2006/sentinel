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
        return {
            "message": self.message,
            "details": self.details,
            "type": type(self).__name__
        }


class ProviderError(SentinelError):
    """Error from an LLM provider."""
    
    def __init__(
        self,
        message: str,
        provider: str,
        status_code: int | None = None,
        details: dict | None = None
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


class InvalidRequestError(SentinelError):
    """Request was invalid (empty messages, missing model, etc)."""
    pass


# =============================================================================
# GUARDRAIL EXCEPTIONS
# =============================================================================

class GuardrailError(SentinelError):
    """Base error for guardrail-related issues."""
    pass


class ContentBlockedError(GuardrailError):
    """
    Content was blocked by guardrails.
    
    Triggers:
    - PII detected with BLOCK action
    - Banned keywords found
    - Content filter triggered
    """
    
    def __init__(
        self,
        message: str,
        reason: str,
        blocked_content: str | None = None,
        details: dict | None = None,
    ):
        super().__init__(message, details)
        self.reason = reason
        self.blocked_content = blocked_content
    
    def to_dict(self) -> dict:
        result = super().to_dict()
        result["reason"] = self.reason
        if self.blocked_content:
            result["blocked_content"] = self.blocked_content
        return result


class PIIDetectedError(ContentBlockedError):
    """
    PII was detected and request was blocked.
    Contains the types of PII found (but not the actual values).
    """
    
    def __init__(
        self,
        message: str,
        pii_types: list[str],
        details: dict | None = None,
    ):
        super().__init__(
            message,
            reason="pii_detected",
            details=details,
        )
        self.pii_types = pii_types
    
    def to_dict(self) -> dict:
        result = super().to_dict()
        result["pii_types"] = self.pii_types
        return result


# =============================================================================
# CACHE EXCEPTIONS
# =============================================================================

class CacheError(SentinelError):
    """Cache operation failed. Should not block requests."""
    pass


class CacheConnectionError(CacheError):
    """Redis connection failed."""
    pass


class CacheSerializationError(CacheError):
    """Failed to serialize/deserialize cache data."""
    pass

class CircuitOpenError(SentinelError):
    """Circuit breaker is open."""
    pass

