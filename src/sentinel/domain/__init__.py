"""Sentinel Domain Layer."""

from sentinel.domain.models import (
    # Existing
    Role,
    FinishReason,
    Message,
    ModelParameters,
    ChatRequest,
    TokenUsage,
    ChatResponse,
    # NEW - Sentinel additions
    GuardrailAction,
    PIIType,
    PIIEntity,
    GuardrailResult,
    JudgeScore,
    StreamChunk,
)

from sentinel.domain.exceptions import (
    # Existing
    SentinelError,
    ProviderError,
    ProviderUnavailableError,
    ProviderRateLimitError,
    InvalidRequestError,
    # NEW - Sentinel additions
    GuardrailError,
    ContentBlockedError,
    PIIDetectedError,
    CacheError,
    CacheConnectionError,
    CacheSerializationError,
)

__all__ = [
    # Models
    "Role",
    "FinishReason",
    "Message",
    "ModelParameters",
    "ChatRequest",
    "TokenUsage",
    "ChatResponse",
    "GuardrailAction",
    "PIIType",
    "PIIEntity",
    "GuardrailResult",
    "JudgeScore",
    "StreamChunk",
    # Exceptions
    "SentinelError",
    "ProviderError",
    "ProviderUnavailableError",
    "ProviderRateLimitError",
    "InvalidRequestError",
    "GuardrailError",
    "ContentBlockedError",
    "PIIDetectedError",
    "CacheError",
    "CacheConnectionError",
    "CacheSerializationError",
]
