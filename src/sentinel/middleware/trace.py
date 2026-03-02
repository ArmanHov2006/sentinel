"""Request tracing and metrics middleware."""

import time
import uuid

import structlog
from opentelemetry import trace as otel_trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from sentinel.core.context import set_request_id
from sentinel.core.metrics import sentinel_metrics

logger = structlog.get_logger()


class TraceMiddleware(BaseHTTPMiddleware):
    """Assigns a trace ID, measures latency, and records request metrics."""

    async def dispatch(self, request: Request, call_next: ...) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        span = otel_trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.trace_id:
            structlog.contextvars.bind_contextvars(
                trace_id=format(ctx.trace_id, "032x"),
                span_id=format(ctx.span_id, "016x"),
            )

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
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                elapsed_ms=round(elapsed * 1000, 2),
            )
            sentinel_metrics.record_request("unknown", "unknown", status_code)
            sentinel_metrics.record_latency("unknown", "unknown", elapsed)

            return response
        finally:
            sentinel_metrics.decrement_active_requests()
