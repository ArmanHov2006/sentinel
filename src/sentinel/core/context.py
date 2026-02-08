"""
Request context variables for cross-cutting concerns.

Uses Python's contextvars to propagate request-scoped values
(like trace IDs) through the async call chain without explicit passing.
"""

from contextvars import ContextVar

# Trace ID for the current request, accessible anywhere in the async call chain.
request_id_var: ContextVar[str] = ContextVar("request_id", default="no-trace")


def get_request_id() -> str:
    """Get the current request's trace ID."""
    return request_id_var.get()


def set_request_id(request_id: str) -> None:
    """Set the trace ID for the current request."""
    request_id_var.set(request_id)
