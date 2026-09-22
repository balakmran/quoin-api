"""OpenTelemetry instrumentation for distributed tracing.

``setup_opentelemetry`` runs last during startup and chooses an
exporter by environment: OTLP when an endpoint is configured, console
in development and test, none in production. The database engine and
the shared outbound HTTP client are instrumented separately in the
lifespan, once they exist.

Instrumentation failures are swallowed rather than allowed to abort
startup — a misconfigured collector should cost traces, not the
service. Set ``QUOIN_OTEL_ENABLED=False`` to disable it entirely.
"""

import os
from collections.abc import Sequence

import httpx2
import structlog
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPX2ClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExportResult,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core import metadata
from app.core.config import Environment, settings

logger = structlog.get_logger(__name__)


class SafeConsoleSpanExporter(ConsoleSpanExporter):
    """ConsoleSpanExporter that suppresses I/O errors on shutdown."""

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Export spans to console, suppressing errors if stream is closed."""
        try:
            return super().export(spans)
        except ValueError:
            # Suppress "I/O operation on closed file" during shutdown
            return SpanExportResult.SUCCESS


def log_formatter_oneline(span: ReadableSpan) -> str:
    """Format span as a single-line JSON string."""
    return span.to_json(indent=None) + os.linesep


def setup_opentelemetry(app: FastAPI) -> None:
    """Setup OpenTelemetry instrumentation."""
    if not settings.OTEL_ENABLED:
        return

    # Resource.create, unlike a bare Resource(...), also runs the standard
    # detectors, so OTEL_RESOURCE_ATTRIBUTES and OTEL_SERVICE_NAME still
    # contribute — though the explicit values below win over them.
    resource = Resource.create(
        {
            SERVICE_NAME: metadata.APP_NAME,
            "service.version": metadata.VERSION,
            "deployment.environment.name": settings.ENV.value,
        }
    )
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        exporter = OTLPSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(exporter))
    elif settings.ENV == Environment.production:
        # Falling back to the console here would interleave every span
        # with the JSON log stream, for spans nobody collects.
        logger.warning(
            "otel_enabled_without_exporter",
            detail=(
                "QUOIN_OTEL_ENABLED is true but "
                "OTEL_EXPORTER_OTLP_ENDPOINT is unset; no spans will be "
                "exported."
            ),
        )
    else:
        # Local development / test: print traces to console.
        exporter = SafeConsoleSpanExporter(formatter=log_formatter_oneline)
        provider.add_span_processor(BatchSpanProcessor(exporter))

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)


def instrument_http_client(client: httpx2.AsyncClient) -> None:
    """Instrument a single outbound HTTP client for OTel tracing.

    Spans are emitted for each request made through ``client``. The
    specific client instance is instrumented (rather than patching httpx2
    globally) so the test client and other ad-hoc clients are unaffected.
    No-op when ``QUOIN_OTEL_ENABLED`` is false.

    Tracing is best-effort: if instrumentation fails (e.g. an
    instrumentor/httpx2 version skew) the error is logged and swallowed so
    a purely observational concern never aborts application startup.

    Args:
        client: The shared async HTTP client to instrument.
    """
    if not settings.OTEL_ENABLED:
        return
    try:
        HTTPX2ClientInstrumentor.instrument_client(client)
    except Exception as exc:
        logger.warning("http_client_instrumentation_failed", error=repr(exc))


def instrument_sqlalchemy_engine(engine: AsyncEngine) -> None:
    """Instrument a single async engine for OTel database tracing.

    Emits a span per SQL statement executed through ``engine`` — or any
    session bound to it — completing the trace hierarchy the FastAPI and
    outbound-HTTP instrumentors already provide (the observability guide
    promises database spans; without this, that hierarchy did not
    exist). No-op when ``QUOIN_OTEL_ENABLED`` is false.

    Call this **once per process**, on the engine the application
    serves requests from. ``SQLAlchemyInstrumentor`` is a singleton that
    both attaches to the engine passed here *and* patches SQLAlchemy's
    ``create_engine``/``create_async_engine`` module-wide, so every
    engine built afterwards is instrumented too; a second call is
    refused ("Attempting to instrument while already instrumented") and
    leaves its argument untouched.

    Tracing is best-effort: if instrumentation fails (e.g. an
    instrumentor/SQLAlchemy version skew) the error is logged and
    swallowed so a purely observational concern never aborts application
    startup.

    Args:
        engine: The async engine backing every request's session. The
            instrumentor attaches to its underlying sync engine, which is
            where SQLAlchemy's cursor-execute events actually fire.
    """
    if not settings.OTEL_ENABLED:
        return
    try:
        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    except Exception as exc:
        logger.warning("db_instrumentation_failed", error=repr(exc))
