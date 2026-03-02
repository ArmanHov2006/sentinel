"""OpenTelemetry tracing configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = structlog.get_logger()


def configure_telemetry(
    app: FastAPI,
    service_name: str = "sentinel",
    env: str = "development",
    otel_endpoint: str = "http://localhost:4317",
    console_export: bool = False,
) -> None:
    """Set up OpenTelemetry tracing with OTLP export and FastAPI instrumentation."""
    try:
        resource = Resource.create({"service.name": service_name, "deployment.environment": env})
        provider = TracerProvider(resource=resource)

        if env != "test":
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )

                otlp_exporter = OTLPSpanExporter(endpoint=otel_endpoint, insecure=True)
                provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            except Exception:
                logger.warning("otlp_exporter_unavailable", action="traces_local_only")

        if console_export:
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        trace.set_tracer_provider(provider)

        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app)
        except Exception:
            logger.warning("fastapi_instrumentation_failed", action="continue")

        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

            HTTPXClientInstrumentor().instrument()
        except Exception:
            logger.warning("httpx_instrumentation_failed", action="continue")

        logger.info("telemetry_configured", service=service_name, env=env)
    except Exception:
        logger.warning("telemetry_init_failed", action="continue_without_tracing", exc_info=True)


def get_tracer(name: str) -> trace.Tracer:
    """Return a named tracer from the global provider."""
    return trace.get_tracer(name)
