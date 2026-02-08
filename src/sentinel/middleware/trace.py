"""
Request tracing and metrics middleware.

Assigns a unique trace ID to every request, measures response time,
and tracks request metrics. The trace ID flows through the entire
async call chain via contextvars.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from sentinel.core.context import set_request_id
from sentinel.core.metrics import metrics

logger = logging.getLogger(__name__)


class TraceMiddleware(BaseHTTPMiddleware):
    """Middleware that handles request tracing and metrics collection.

    On every incoming request:
    - Extracts or generates a trace ID (X-Request-ID header).
    - Stores the trace ID in the ContextVar for the async call chain.
    - Increments request counters and tracks active requests.
    - Measures response time and records it as an observation.
    - Adds X-Request-ID and X-Response-Time to response headers.
    """

    async def dispatch(self, request: Request, call_next: ...) -> Response:
        """Process each request with tracing and metrics."""
        # Extract existing trace ID or generate a new one
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)

        # Track active requests and total count
        metrics.increment("active_requests")
        metrics.increment("requests_total")
        metrics.increment_dict("requests_by_endpoint", request.url.path)

        # Measure response time
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            metrics.decrement("active_requests")
            raise

        elapsed = time.perf_counter() - start
        elapsed_ms = round(elapsed * 1000, 2)

        # Record metrics
        metrics.decrement("active_requests")
        metrics.observe("response_time_seconds", elapsed)
        metrics.increment_dict("requests_by_status", str(response.status_code))

        # Add trace headers to response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{elapsed_ms}ms"

        logger.info(
            "%s %s -> %d (%.2fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )

        return response
