"""Structured logging, configured once at startup.

``setup_logging`` wires structlog and the standard library into a single
pipeline: context variables (request ID, caller), log level, timestamp,
and trace correlation. It runs first during startup, before anything
else has a chance to log.

``production`` renders JSON in UTC; development and test render
human-readable console lines. ``QUOIN_LOG_LEVEL`` sets the verbosity.
"""

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog
from opentelemetry import trace
from structlog.types import Processor

from app.core.config import Environment, settings


def _add_otel_context(
    logger: Any, method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Inject active OTel trace_id and span_id into every log event."""
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


# Mutated in place (never rebound) so cached loggers and
# structlog.testing.capture_logs() -- both of which key off this list's
# identity -- stay wired to it across repeated setup_logging() calls.
_processors: list[Processor] = []


def setup_logging() -> None:
    """Configure structured logging."""
    # One predicate picks both the renderer and the logger factory: a
    # console renderer routed through stdlib gets its line JSON-wrapped.
    json_logs = settings.ENV == Environment.production

    # Processors compatible with both PrintLogger and stdlib logger
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        _add_otel_context,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        # UTC in production so aggregated JSON logs are timezone-stable
        # across hosts; local time in dev/test keeps console logs
        # readable against the wall clock.
        structlog.processors.TimeStamper(fmt="iso", utc=json_logs),
    ]

    if json_logs:
        processors = [
            # Only for prod (needs stdlib logger)
            structlog.stdlib.add_logger_name,
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # ConsoleRenderer formats exc_info itself (prettier tracebacks).
        # Drop format_exc_info here, or it pre-renders exc_info to a
        # string and ConsoleRenderer emits a UserWarning.
        console_processors = [
            p
            for p in shared_processors
            if p is not structlog.processors.format_exc_info
        ]
        processors = [
            *console_processors,
            structlog.dev.ConsoleRenderer(
                pad_event_to=0
            ),  # No padding for compact logs
        ]

    _processors.clear()
    _processors.extend(processors)

    structlog.configure(
        processors=_processors,
        logger_factory=structlog.stdlib.LoggerFactory()
        if json_logs
        else structlog.PrintLoggerFactory(),
        # The filtering wrapper is what enforces QUOIN_LOG_LEVEL;
        # structlog.stdlib.BoundLogger has no level filter of its own.
        wrapper_class=structlog.make_filtering_bound_logger(settings.LOG_LEVEL),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging for third-party libraries
    if json_logs:
        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)

        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.addHandler(handler)
        root_logger.setLevel(settings.LOG_LEVEL)
