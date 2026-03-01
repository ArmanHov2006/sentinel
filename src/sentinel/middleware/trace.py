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
from sentinel.core.metrics import sentinel_metrics

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
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)

        sentinel_metrics.increment_active_requests()

        start = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            elapsed = time.perf_counter() - start

            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{elapsed}ms"
            logger.info(
                "%s %s -> %d (%.2fms)", request.method, request.url.path, status_code, elapsed
            )
            sentinel_metrics.record_request("unknown", "unknown", status_code)
            sentinel_metrics.record_latency("unknown", "unknown", elapsed)

            return response
        finally:
            sentinel_metrics.decrement_active_requests()
