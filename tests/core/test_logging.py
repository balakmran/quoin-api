import logging
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import structlog
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from app.core.config import Environment
from app.core.exception_handlers import validation_exception_handler
from app.core.logging import _add_otel_context, setup_logging


def test_setup_logging() -> None:
    """Test setup_logging configuration."""
    with patch("structlog.configure") as mock_configure:
        setup_logging()

        # Verify structlog.configure was called
        mock_configure.assert_called_once()

        # Verify basic logging config
        # We can check if basicConfig was called or if the handler is set
        # But since setup_logging modifies global state, we should be careful.
        # The function sets logging.basicConfig.

        # Let's verify that we can get a logger and it works
        logger = structlog.get_logger()
        assert logger is not None


def test_setup_logging_prod() -> None:
    """Test setup_logging configuration in production."""
    with (
        patch("app.core.logging.settings.ENV", Environment.production),
        patch("structlog.configure") as mock_configure,
    ):
        setup_logging()

        mock_configure.assert_called_once()
        # Verify JSONRenderer is in processors
        call_args = mock_configure.call_args
        processors = call_args.kwargs["processors"]
        assert any(
            isinstance(p, structlog.processors.JSONRenderer) for p in processors
        )


def test_setup_logging_not_dev() -> None:
    """Test setup_logging stdlib configuration in non-dev environment."""
    with (
        patch("app.core.logging.settings.ENV", Environment.production),
        patch("logging.getLogger") as mock_get_logger,
        patch("logging.StreamHandler"),
    ):
        mock_root_logger = MagicMock()
        mock_get_logger.return_value = mock_root_logger

        setup_logging()

        # Verify root logger handlers were cleared and new handler added
        mock_root_logger.handlers.clear.assert_called_once()
        mock_root_logger.addHandler.assert_called_once()
        mock_root_logger.setLevel.assert_called_with(logging.INFO)


def test_add_otel_context_injects_fields_when_span_valid() -> None:
    """Test trace_id and span_id are added when an active span exists."""
    mock_ctx = MagicMock()
    mock_ctx.is_valid = True
    mock_ctx.trace_id = 0x4BF92F3577B34DA6A3CE929D0E0E4736
    mock_ctx.span_id = 0x00F067AA0BA902B7

    mock_span = MagicMock()
    mock_span.get_span_context.return_value = mock_ctx

    with patch(
        "app.core.logging.trace.get_current_span", return_value=mock_span
    ):
        result: dict[str, Any] = {}
        _add_otel_context(None, "info", result)

    assert result["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert result["span_id"] == "00f067aa0ba902b7"


def test_add_otel_context_omits_fields_when_span_invalid() -> None:
    """Test no fields are added when there is no active span."""
    mock_ctx = MagicMock()
    mock_ctx.is_valid = False

    mock_span = MagicMock()
    mock_span.get_span_context.return_value = mock_ctx

    with patch(
        "app.core.logging.trace.get_current_span", return_value=mock_span
    ):
        result: dict[str, Any] = {}
        _add_otel_context(None, "info", result)

    assert "trace_id" not in result
    assert "span_id" not in result


@pytest.mark.asyncio
async def test_validation_exception_handler() -> None:
    """Test validation_exception_handler handles Pydantic errors."""
    # Create a mock request
    request = MagicMock()
    request.url.path = "/test"

    # Create a ValidationError
    try:

        class TestModel(BaseModel):
            value: int

        TestModel(value="not_an_int")  # type: ignore
    except PydanticValidationError as exc:
        response = await validation_exception_handler(request, exc)
        assert response.status_code == 422  # noqa: PLR2004
        body = response.body.decode()  # type: ignore
        assert "detail" in body
