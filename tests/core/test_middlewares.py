import uuid
from unittest.mock import patch

import anyio
import pytest
import structlog
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.middlewares import (
    RequestIDMiddleware,
    TimeoutMiddleware,
    configure_cors,
    configure_middlewares,
    configure_trusted_hosts,
)
from app.main import create_app


@pytest.fixture
def timeout_app() -> FastAPI:
    """Minimal app with TimeoutMiddleware for timeout testing."""
    app = FastAPI()
    app.add_middleware(TimeoutMiddleware)

    @app.get("/fast")
    async def fast_endpoint() -> dict[str, str]:
        return {"ok": "true"}

    @app.get("/slow")
    async def slow_endpoint() -> dict[str, str]:
        await anyio.sleep(0.5)
        return {"ok": "true"}

    return app


@pytest.mark.asyncio
async def test_timeout_middleware_fast_request_passes(
    timeout_app: FastAPI,
) -> None:
    """Fast requests complete normally under the configured timeout."""
    async with AsyncClient(
        transport=ASGITransport(app=timeout_app), base_url="http://test"
    ) as ac:
        response = await ac.get("/fast")

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_timeout_middleware_disabled_when_zero(
    timeout_app: FastAPI,
) -> None:
    """Setting timeout to 0 disables the middleware (slow request passes)."""
    with patch.object(settings, "REQUEST_TIMEOUT_SECONDS", 0):
        async with AsyncClient(
            transport=ASGITransport(app=timeout_app), base_url="http://test"
        ) as ac:
            response = await ac.get("/fast")

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_timeout_middleware_slow_request_returns_504(
    timeout_app: FastAPI,
) -> None:
    """Requests that exceed the timeout return 504 RFC 9457."""
    with patch.object(settings, "REQUEST_TIMEOUT_SECONDS", 0.05):
        async with AsyncClient(
            transport=ASGITransport(app=timeout_app), base_url="http://test"
        ) as ac:
            response = await ac.get("/slow")

    assert response.status_code == status.HTTP_504_GATEWAY_TIMEOUT
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "urn:quoin:error:gateway_timeout_error"
    assert body["status"] == status.HTTP_504_GATEWAY_TIMEOUT
    assert body["instance"] == "/slow"


@pytest.mark.asyncio
async def test_timeout_middleware_integration_real_app() -> None:
    """Timeout fires through the full create_app() middleware stack."""
    app = create_app()

    @app.get("/test-timeout-slow")
    async def _slow() -> dict[str, str]:
        await anyio.sleep(0.5)
        return {}

    with patch.object(settings, "REQUEST_TIMEOUT_SECONDS", 0.05):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/test-timeout-slow")

    assert response.status_code == status.HTTP_504_GATEWAY_TIMEOUT
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "urn:quoin:error:gateway_timeout_error"
    assert body["status"] == status.HTTP_504_GATEWAY_TIMEOUT
    assert body["instance"] == "/test-timeout-slow"


def test_configure_cors_enabled() -> None:
    """Test CORS middleware configuration when origins are enabled."""
    app = FastAPI()

    # Patch settings to enable CORS
    with patch.object(
        settings, "BACKEND_CORS_ORIGINS", ["http://localhost:3000"]
    ):
        configure_cors(app)

        # Verify CORSMiddleware is added
        has_cors = any(m.cls == CORSMiddleware for m in app.user_middleware)
        assert has_cors


def test_configure_cors_disabled() -> None:
    """Test CORS middleware when origins are disabled."""
    app = FastAPI()

    # Patch settings to disable CORS
    with patch.object(settings, "BACKEND_CORS_ORIGINS", []):
        configure_cors(app)

        # Verify CORSMiddleware is NOT added
        has_cors = any(m.cls == CORSMiddleware for m in app.user_middleware)
        assert not has_cors


def test_configure_trusted_hosts() -> None:
    """Test TrustedHost middleware configuration."""
    app = FastAPI()
    configure_trusted_hosts(app)

    # Verify TrustedHostMiddleware is added
    has_trusted_host = any(
        m.cls == TrustedHostMiddleware for m in app.user_middleware
    )
    assert has_trusted_host


def test_configure_middlewares() -> None:
    """Test that configure_middlewares configures all middlewares."""
    app = FastAPI()

    with patch.object(
        settings, "BACKEND_CORS_ORIGINS", ["http://localhost:3000"]
    ):
        configure_middlewares(app)

        has_cors = any(m.cls == CORSMiddleware for m in app.user_middleware)
        has_trusted_host = any(
            m.cls == TrustedHostMiddleware for m in app.user_middleware
        )
        has_request_id = any(
            m.cls == RequestIDMiddleware for m in app.user_middleware
        )
        has_timeout = any(
            m.cls == TimeoutMiddleware for m in app.user_middleware
        )

        assert has_cors
        assert has_trusted_host
        assert has_request_id
        assert has_timeout


@pytest.fixture
def request_id_app() -> FastAPI:
    """Minimal app with only RequestIDMiddleware registered."""
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/test")
    async def endpoint() -> dict[str, str]:
        return {}

    return app


@pytest.mark.asyncio
async def test_request_id_middleware_generates_id(
    request_id_app: FastAPI,
) -> None:
    """Test that a UUID is generated when no request ID header is present."""
    async with AsyncClient(
        transport=ASGITransport(app=request_id_app), base_url="http://test"
    ) as ac:
        response = await ac.get("/test")

    header = settings.REQUEST_ID_HEADER
    assert header in response.headers
    uuid.UUID(response.headers[header])  # raises if not a valid UUID


@pytest.mark.asyncio
async def test_request_id_middleware_propagates_existing_id(
    request_id_app: FastAPI,
) -> None:
    """Test that a provided request ID is echoed back unchanged."""
    incoming = "my-trace-id-42"
    async with AsyncClient(
        transport=ASGITransport(app=request_id_app), base_url="http://test"
    ) as ac:
        response = await ac.get(
            "/test", headers={settings.REQUEST_ID_HEADER: incoming}
        )

    assert response.headers[settings.REQUEST_ID_HEADER] == incoming


@pytest.mark.asyncio
async def test_request_id_middleware_custom_header_name() -> None:
    """Test that a custom QUOIN_REQUEST_ID_HEADER is honoured."""
    with patch.object(settings, "REQUEST_ID_HEADER", "X-Correlation-ID"):
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.get("/test")
        async def endpoint() -> dict[str, str]:
            return {}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get(
                "/test", headers={"X-Correlation-ID": "corr-99"}
            )

    assert response.headers["X-Correlation-ID"] == "corr-99"
    assert "X-Request-ID" not in response.headers


@pytest.mark.asyncio
async def test_request_id_middleware_binds_and_clears_structlog(
    request_id_app: FastAPI,
) -> None:
    """Test request_id is bound during the request and cleared after."""
    captured: dict[str, object] = {}

    @request_id_app.get("/capture")
    async def capture_ctx() -> dict[str, str]:
        captured.update(structlog.contextvars.get_contextvars())
        return {}

    async with AsyncClient(
        transport=ASGITransport(app=request_id_app), base_url="http://test"
    ) as ac:
        await ac.get(
            "/capture", headers={settings.REQUEST_ID_HEADER: "ctx-test-id"}
        )

    assert captured["request_id"] == "ctx-test-id"
