"""Structured logging configuration using structlog."""

import logging

import structlog


def configure_logging(env: str = "development") -> None:
    """Configure structlog with environment-appropriate rendering.

    In development: colored console output via ConsoleRenderer.
    In production/test: JSON lines via orjson for machine parsing.
    """
    if env == "development":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        import orjson

        renderer = structlog.processors.JSONRenderer(serializer=orjson.dumps)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    for noisy in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
