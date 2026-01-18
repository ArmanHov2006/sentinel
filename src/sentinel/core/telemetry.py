"""
Structured logging for request telemetry.

Logs METADATA only - never log prompt/completion content.
"""

import structlog

from src.sentinel.domain.models import ChatRequest, ChatResponse
from src.sentinel.domain.exceptions import SentinelError


# Configure structlog for JSON output
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger("sentinel.telemetry")


def log_request_started(request: ChatRequest) -> None:
    """Log when request processing begins. No content logged."""
    logger.info(
        "request_started",
        request_id=request.id,
        model=request.model,
        message_count=len(request.messages),
    )


def log_request_completed(request: ChatRequest, response: ChatResponse) -> None:
    """Log successful completion. No content logged."""
    logger.info(
        "request_completed",
        request_id=request.id,
        provider=response.provider,
        model=response.model,
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
        total_tokens=response.usage.total_tokens,
        latency_ms=round(response.latency_ms, 2),
        finish_reason=response.finish_reason.value,
    )


def log_request_failed(request: ChatRequest, error: Exception) -> None:
    """Log request failure with error details."""
    log_data = {
        "request_id": request.id,
        "model": request.model,
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    
    if isinstance(error, SentinelError):
        log_data["error_details"] = error.details
    
    logger.error("request_failed", **log_data)