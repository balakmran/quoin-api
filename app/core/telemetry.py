import os

import httpx
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExportResult,
)

from app.core import metadata
from app.core.config import settings


class SafeConsoleSpanExporter(ConsoleSpanExporter):
    """ConsoleSpanExporter that suppresses I/O errors on shutdown."""

    def export(self, spans) -> SpanExportResult:
        """Export spans to console, suppressing errors if stream is closed."""
        try:
            return super().export(spans)
        except ValueError:
            # Suppress "I/O operation on closed file" during shutdown
            return SpanExportResult.SUCCESS


def log_formatter_oneline(span) -> str:
    """Format span as a single-line JSON string."""
    return span.to_json(indent=None) + os.linesep


def setup_opentelemetry(app: FastAPI) -> None:
    """Setup OpenTelemetry instrumentation."""
    if not settings.OTEL_ENABLED:
        return

    resource = Resource(attributes={SERVICE_NAME: metadata.APP_NAME})
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        exporter = OTLPSpanExporter()
        processor = BatchSpanProcessor(exporter)
    else:
        # Local development: Print traces to console
        exporter = SafeConsoleSpanExporter(formatter=log_formatter_oneline)
        processor = BatchSpanProcessor(exporter)

    provider.add_span_processor(processor)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)


def instrument_http_client(client: httpx.AsyncClient) -> None:
    """Instrument a single outbound HTTP client for OTel tracing.

    Spans are emitted for each request made through ``client``. The
    specific client instance is instrumented (rather than patching httpx
    globally) so the test client and other ad-hoc clients are unaffected.

    Args:
        client: The shared async HTTP client to instrument.
    """
    if not settings.OTEL_ENABLED:
        return
    HTTPXClientInstrumentor.instrument_client(client)
