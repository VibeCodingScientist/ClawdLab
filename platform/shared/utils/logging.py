"""Structured logging configuration using structlog."""

import logging
import sys
from typing import Any

import structlog


def configure_logging(
    level: str = "INFO",
    json_format: bool = True,
    service_name: str = "asrp",
) -> None:
    """
    Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: If True, output JSON; if False, output colored console format
        service_name: Name of the service for log context
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    # Shared processors for all log entries
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_format:
        # Production: JSON output
        processors = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Colored console output
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Bind service name to all loggers
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(service=service_name)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Optional logger name (usually __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


def bind_request_context(
    request_id: str,
    agent_id: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Bind request context to all subsequent log entries.

    Call this at the start of request handling to add
    request-specific context to all logs.

    Args:
        request_id: Unique request identifier
        agent_id: Optional authenticated agent ID
        **kwargs: Additional context to bind
    """
    context = {"request_id": request_id}
    if agent_id:
        context["agent_id"] = agent_id
    context.update(kwargs)
    structlog.contextvars.bind_contextvars(**context)


def clear_request_context() -> None:
    """Clear request context (call at end of request)."""
    structlog.contextvars.clear_contextvars()


class LoggerMixin:
    """Mixin class to add logging to any class."""

    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Get a logger bound to this class."""
        return get_logger(self.__class__.__name__)
