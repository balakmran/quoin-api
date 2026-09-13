import os
from unittest import mock
from unittest.mock import MagicMock, patch

import httpx2
import structlog
from opentelemetry.sdk.resources import SERVICE_NAME
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from structlog.testing import capture_logs

from app.core import metadata, telemetry
from app.core.config import Environment, settings
from app.core.telemetry import (
    SafeConsoleSpanExporter,
    instrument_http_client,
    instrument_sqlalchemy_engine,
    log_formatter_oneline,
    setup_opentelemetry,
)


def test_log_formatter_oneline():
    """Test that the log formatter returns a single-line JSON string."""
    mock_span = MagicMock()
    mock_span.to_json.return_value = '{"foo": "bar"}'

    result = log_formatter_oneline(mock_span)

    assert result == '{"foo": "bar"}' + os.linesep
    mock_span.to_json.assert_called_once_with(indent=None)


class TestSafeConsoleSpanExporter:
    """Tests for SafeConsoleSpanExporter."""

    def test_export_success(self):
        """Test that export calls super().export."""
        exporter = SafeConsoleSpanExporter()
        mock_spans = [MagicMock()]

        with patch.object(ConsoleSpanExporter, "export") as mock_super_export:
            exporter.export(mock_spans)
            mock_super_export.assert_called_once_with(mock_spans)

    def test_export_suppresses_value_error(self):
        """Test export suppresses ValueError (simulating I/O error)."""
        exporter = SafeConsoleSpanExporter()
        mock_spans = [MagicMock()]

        with patch.object(ConsoleSpanExporter, "export") as mock_super_export:
            mock_super_export.side_effect = ValueError(
                "I/O operation on closed file"
            )
            # Should not raise exception
            exporter.export(mock_spans)
            mock_super_export.assert_called_once_with(mock_spans)


class TestSetupOpenTelemetry:
    """Tests for setup_opentelemetry."""

    @mock.patch.object(settings, "OTEL_ENABLED", False)
    def test_setup_disabled(self):
        """Test that setup does nothing when OTEL_ENABLED is False."""
        mock_app = MagicMock()

        with patch(
            "app.core.telemetry.FastAPIInstrumentor"
        ) as mock_instrumentor:
            setup_opentelemetry(mock_app)
            mock_instrumentor.instrument_app.assert_not_called()

    @mock.patch.object(settings, "OTEL_ENABLED", True)
    def test_setup_enabled_local(self):
        """Test setup with local configuration (Console exporter)."""
        mock_app = MagicMock()

        # Ensure OTLP endpoint is treated as unset (empty string is falsy)
        with patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": ""}):
            with (
                patch(
                    "app.core.telemetry.FastAPIInstrumentor"
                ) as mock_instrumentor,
                patch("app.core.telemetry.TracerProvider"),
                patch(
                    "app.core.telemetry.BatchSpanProcessor"
                ) as mock_processor,
                patch(
                    "app.core.telemetry.SafeConsoleSpanExporter"
                ) as mock_exporter,
                patch("app.core.telemetry.trace"),
            ):
                setup_opentelemetry(mock_app)

                # Check that SafeConsoleSpanExporter was used
                mock_exporter.assert_called_once()
                mock_processor.assert_called_once()
                mock_instrumentor.instrument_app.assert_called_once()

    @mock.patch.object(settings, "OTEL_ENABLED", True)
    def test_setup_enabled_otlp(self):
        """Test setup with OTLP configuration."""
        mock_app = MagicMock()

        # Set OTLP endpoint
        with patch.dict(
            os.environ,
            {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317"},
        ):
            with (
                patch(
                    "app.core.telemetry.FastAPIInstrumentor"
                ) as mock_instrumentor,
                patch("app.core.telemetry.TracerProvider"),
                patch(
                    "app.core.telemetry.BatchSpanProcessor"
                ) as mock_processor,
                patch(
                    "app.core.telemetry.OTLPSpanExporter"
                ) as mock_otlp_exporter,
                patch("app.core.telemetry.trace"),
            ):
                setup_opentelemetry(mock_app)

                # Check that OTLPSpanExporter was used
                mock_otlp_exporter.assert_called_once()
                mock_processor.assert_called_once()
                mock_instrumentor.instrument_app.assert_called_once()

    @mock.patch.object(settings, "OTEL_ENABLED", True)
    def test_resource_carries_service_version_and_environment(self):
        """B10 regression: the Resource carries version and environment."""
        mock_app = MagicMock()

        with patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": ""}):
            with (
                patch("app.core.telemetry.FastAPIInstrumentor"),
                patch("app.core.telemetry.TracerProvider") as mock_provider_cls,
                patch("app.core.telemetry.BatchSpanProcessor"),
                patch("app.core.telemetry.SafeConsoleSpanExporter"),
                patch("app.core.telemetry.trace"),
            ):
                setup_opentelemetry(mock_app)

        resource = mock_provider_cls.call_args.kwargs["resource"]
        assert resource.attributes[SERVICE_NAME] == metadata.APP_NAME
        assert resource.attributes["service.version"] == metadata.VERSION
        environment = settings.ENV.value
        assert resource.attributes["deployment.environment.name"] == environment
        # The deprecated key is kept for one release alongside the new one.
        assert resource.attributes["deployment.environment"] == environment

    @mock.patch.object(settings, "OTEL_ENABLED", True)
    @mock.patch.object(settings, "ENV", Environment.production)
    def test_setup_production_without_exporter_warns_and_skips_console(self):
        """B6 regression: production without an OTLP endpoint warns."""
        mock_app = MagicMock()

        with patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": ""}):
            with (
                patch(
                    "app.core.telemetry.FastAPIInstrumentor"
                ) as mock_instrumentor,
                patch("app.core.telemetry.TracerProvider"),
                patch(
                    "app.core.telemetry.BatchSpanProcessor"
                ) as mock_processor,
                patch(
                    "app.core.telemetry.SafeConsoleSpanExporter"
                ) as mock_exporter,
                patch("app.core.telemetry.trace"),
                capture_logs() as cap_logs,
                patch.object(telemetry, "logger", structlog.get_logger()),
            ):
                setup_opentelemetry(mock_app)

        mock_exporter.assert_not_called()
        mock_processor.assert_not_called()
        mock_instrumentor.instrument_app.assert_called_once()
        events = [
            e for e in cap_logs if e["event"] == "otel_enabled_without_exporter"
        ]
        assert len(events) == 1


class TestInstrumentHttpClient:
    """Tests for instrument_http_client."""

    @mock.patch.object(settings, "OTEL_ENABLED", False)
    def test_disabled_does_nothing(self):
        """When OTEL is disabled the client is not instrumented."""
        mock_client = MagicMock()
        with patch(
            "app.core.telemetry.HTTPX2ClientInstrumentor"
        ) as mock_instrumentor:
            instrument_http_client(mock_client)
            mock_instrumentor.instrument_client.assert_not_called()

    @mock.patch.object(settings, "OTEL_ENABLED", True)
    def test_enabled_instruments_client(self):
        """When OTEL is enabled the specific client is instrumented."""
        mock_client = MagicMock()
        with patch(
            "app.core.telemetry.HTTPX2ClientInstrumentor"
        ) as mock_instrumentor:
            instrument_http_client(mock_client)
            mock_instrumentor.instrument_client.assert_called_once_with(
                mock_client
            )

    @mock.patch.object(settings, "OTEL_ENABLED", True)
    async def test_enabled_accepts_real_client(self):
        """A real httpx2.AsyncClient is accepted by the instrumentor."""
        client = httpx2.AsyncClient()
        try:
            # Must not raise against the real instrumentor API.
            instrument_http_client(client)
        finally:
            await client.aclose()

    @mock.patch.object(settings, "OTEL_ENABLED", True)
    def test_instrumentation_failure_is_swallowed(self):
        """Instrumentation errors are logged, not raised (best-effort)."""
        mock_client = MagicMock()
        with patch(
            "app.core.telemetry.HTTPX2ClientInstrumentor"
        ) as mock_instrumentor:
            mock_instrumentor.instrument_client.side_effect = RuntimeError(
                "version skew"
            )
            # Should not propagate — app startup must not abort.
            instrument_http_client(mock_client)


class TestInstrumentSqlalchemyEngine:
    """Tests for instrument_sqlalchemy_engine (Improvement 3)."""

    @mock.patch.object(settings, "OTEL_ENABLED", False)
    def test_disabled_does_nothing(self):
        """When OTEL is disabled the engine is not instrumented."""
        mock_engine = MagicMock()
        with patch(
            "app.core.telemetry.SQLAlchemyInstrumentor"
        ) as mock_instrumentor_cls:
            instrument_sqlalchemy_engine(mock_engine)
            mock_instrumentor_cls.assert_not_called()

    @mock.patch.object(settings, "OTEL_ENABLED", True)
    def test_enabled_instruments_the_sync_engine(self):
        """When OTEL is enabled, the engine's sync_engine is instrumented."""
        mock_engine = MagicMock()
        with patch(
            "app.core.telemetry.SQLAlchemyInstrumentor"
        ) as mock_instrumentor_cls:
            mock_instrumentor = mock_instrumentor_cls.return_value
            instrument_sqlalchemy_engine(mock_engine)
            mock_instrumentor.instrument.assert_called_once_with(
                engine=mock_engine.sync_engine
            )

    @mock.patch.object(settings, "OTEL_ENABLED", True)
    def test_instrumentation_failure_is_swallowed(self):
        """Instrumentation errors are logged, not raised (best-effort)."""
        mock_engine = MagicMock()
        with patch(
            "app.core.telemetry.SQLAlchemyInstrumentor"
        ) as mock_instrumentor_cls:
            mock_instrumentor = mock_instrumentor_cls.return_value
            mock_instrumentor.instrument.side_effect = RuntimeError(
                "version skew"
            )
            # Should not propagate — app startup must not abort.
            instrument_sqlalchemy_engine(mock_engine)
