"""
Logging configuration for Sentinel.

Configures structured logging with automatic request trace ID injection.
Every log line includes the correlation ID from the request context.
"""

import logging

from sentinel.core.context import get_request_id


class RequestIdFilter(logging.Filter):
    """Logging filter that injects the request trace ID into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add request_id attribute to the log record from context."""
        record.request_id = get_request_id()  # type: ignore[attr-defined]
        return True


def configure_logging() -> None:
    """Configure logging with trace ID injection for all handlers.

    Sets up a console handler with a format that includes the request
    trace ID on every log line. Applies the RequestIdFilter globally
    so all loggers benefit from automatic trace ID injection.
    """
    log_format = "[%(asctime)s] [%(levelname)s] [%(request_id)s] %(name)s: %(message)s"

    request_id_filter = RequestIdFilter()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates on repeated calls
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create and configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format))
    console_handler.addFilter(request_id_filter)

    root_logger.addHandler(console_handler)
