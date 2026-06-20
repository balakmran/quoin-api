import os
from unittest import mock
from unittest.mock import MagicMock, patch

from opentelemetry.sdk.trace.export import ConsoleSpanExporter

from app.core.config import settings
from app.core.telemetry import (
    SafeConsoleSpanExporter,
    instrument_http_client,
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


class TestInstrumentHttpClient:
    """Tests for instrument_http_client."""

    @mock.patch.object(settings, "OTEL_ENABLED", False)
    def test_disabled_does_nothing(self):
        """When OTEL is disabled the client is not instrumented."""
        mock_client = MagicMock()
        with patch(
            "app.core.telemetry.HTTPXClientInstrumentor"
        ) as mock_instrumentor:
            instrument_http_client(mock_client)
            mock_instrumentor.instrument_client.assert_not_called()

    @mock.patch.object(settings, "OTEL_ENABLED", True)
    def test_enabled_instruments_client(self):
        """When OTEL is enabled the specific client is instrumented."""
        mock_client = MagicMock()
        with patch(
            "app.core.telemetry.HTTPXClientInstrumentor"
        ) as mock_instrumentor:
            instrument_http_client(mock_client)
            mock_instrumentor.instrument_client.assert_called_once_with(
                mock_client
            )
