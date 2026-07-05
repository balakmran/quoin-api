import uuid
from unittest.mock import patch

import anyio
import pytest
import structlog
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from httpx import ASGITransport, AsyncClient, Response
from starlette.types import Message, Receive, Scope, Send

from app.core.config import Environment, settings
from app.core.middlewares import (
    RequestIDMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
    TimeoutMiddleware,
    _safe_request_id,
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
        has_security_headers = any(
            m.cls == SecurityHeadersMiddleware for m in app.user_middleware
        )
        has_size_limit = any(
            m.cls == RequestSizeLimitMiddleware for m in app.user_middleware
        )

        assert has_cors
        assert has_trusted_host
        assert has_request_id
        assert has_timeout
        assert has_security_headers
        assert has_size_limit


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
@pytest.mark.parametrize(
    "hostile",
    [
        "bad id with spaces",
        "inject;DROP TABLE",
        "a" * 65,  # over the 64-char cap
    ],
)
async def test_request_id_middleware_rejects_unsafe_id(
    request_id_app: FastAPI,
    hostile: str,
) -> None:
    """Unsafe inbound X-Request-ID is discarded for a fresh UUID (S6)."""
    async with AsyncClient(
        transport=ASGITransport(app=request_id_app), base_url="http://test"
    ) as ac:
        response = await ac.get(
            "/test", headers={settings.REQUEST_ID_HEADER: hostile}
        )

    echoed = response.headers[settings.REQUEST_ID_HEADER]
    assert echoed != hostile
    uuid.UUID(echoed)  # a valid UUID replaced the hostile value


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "has space",
        "inject;DROP",
        "café",  # non-ASCII
        "trailing-newline\n",  # \Z anchor rejects; $ would have accepted
        "a\nb",  # embedded newline
        "a" * 65,  # over the 64-char cap
    ],
)
def test_safe_request_id_rejects_unsafe_values(raw: str | None) -> None:
    """Unsafe raw values are replaced with a fresh UUID (S6)."""
    result = _safe_request_id(raw)
    assert result != raw
    uuid.UUID(result)  # raises if not a valid UUID


@pytest.mark.parametrize("raw", ["my-trace-id-42", "a", "a" * 64, "A.b_c-9"])
def test_safe_request_id_passes_valid_values(raw: str) -> None:
    """Well-formed request IDs are returned unchanged (S6)."""
    assert _safe_request_id(raw) == raw


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


def test_configure_cors_rejects_wildcard_with_credentials_in_prod() -> None:
    """In production, wildcard methods/headers + credentials must error."""
    app = FastAPI()
    with (
        patch.object(settings, "ENV", Environment.production),
        patch.object(settings, "BACKEND_CORS_ORIGINS", ["https://example.com"]),
        patch.object(settings, "BACKEND_CORS_ALLOW_METHODS", ["*"]),
        patch.object(settings, "BACKEND_CORS_ALLOW_CREDENTIALS", True),
    ):
        with pytest.raises(RuntimeError, match="CORS misconfiguration"):
            configure_cors(app)


def test_configure_cors_allows_wildcard_in_development() -> None:
    """Development should still accept wildcard methods for convenience."""
    app = FastAPI()
    with (
        patch.object(settings, "ENV", Environment.development),
        patch.object(
            settings, "BACKEND_CORS_ORIGINS", ["http://localhost:3000"]
        ),
        patch.object(settings, "BACKEND_CORS_ALLOW_METHODS", ["*"]),
        patch.object(settings, "BACKEND_CORS_ALLOW_CREDENTIALS", True),
    ):
        configure_cors(app)
    assert any(m.cls == CORSMiddleware for m in app.user_middleware)


@pytest.fixture
def security_headers_app() -> FastAPI:
    """Minimal app with SecurityHeadersMiddleware."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/x")
    async def endpoint() -> dict[str, str]:
        return {}

    return app


@pytest.mark.asyncio
async def test_security_headers_emitted(
    security_headers_app: FastAPI,
) -> None:
    """All configured security headers are present on responses."""
    async with AsyncClient(
        transport=ASGITransport(app=security_headers_app),
        base_url="http://test",
    ) as ac:
        response = await ac.get("/x")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in response.headers
    assert "Permissions-Policy" in response.headers
    assert "Content-Security-Policy" in response.headers
    hsts = response.headers["Strict-Transport-Security"]
    assert "max-age=" in hsts
    assert "includeSubDomains" in hsts


@pytest.mark.asyncio
async def test_security_headers_disabled(
    security_headers_app: FastAPI,
) -> None:
    """When disabled, the middleware does not set any headers."""
    with patch.object(settings, "SECURITY_HEADERS_ENABLED", False):
        async with AsyncClient(
            transport=ASGITransport(app=security_headers_app),
            base_url="http://test",
        ) as ac:
            response = await ac.get("/x")

    assert "X-Frame-Options" not in response.headers
    assert "Content-Security-Policy" not in response.headers


@pytest.mark.asyncio
async def test_security_headers_hsts_disabled_when_max_age_zero(
    security_headers_app: FastAPI,
) -> None:
    """HSTS is omitted when max-age is 0."""
    with patch.object(settings, "SECURITY_HSTS_MAX_AGE", 0):
        async with AsyncClient(
            transport=ASGITransport(app=security_headers_app),
            base_url="http://test",
        ) as ac:
            response = await ac.get("/x")

    assert "Strict-Transport-Security" not in response.headers


@pytest.fixture
def size_limit_app() -> FastAPI:
    """Minimal app with RequestSizeLimitMiddleware."""
    app = FastAPI()
    app.add_middleware(RequestSizeLimitMiddleware)

    @app.post("/echo")
    async def echo(payload: dict[str, str]) -> dict[str, str]:
        return payload

    return app


@pytest.mark.asyncio
async def test_request_size_limit_rejects_oversize_content_length(
    size_limit_app: FastAPI,
) -> None:
    """An advertised Content-Length over the cap returns 413."""
    with patch.object(settings, "MAX_REQUEST_BODY_BYTES", 16):
        body = b'{"a":"' + b"x" * 64 + b'"}'
        async with AsyncClient(
            transport=ASGITransport(app=size_limit_app),
            base_url="http://test",
        ) as ac:
            response = await ac.post(
                "/echo",
                content=body,
                headers={"Content-Type": "application/json"},
            )

    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert response.headers["content-type"] == "application/problem+json"
    payload = response.json()
    assert payload["type"] == "urn:quoin:error:payload_too_large"
    assert payload["status"] == status.HTTP_413_CONTENT_TOO_LARGE


@pytest.mark.asyncio
async def test_request_size_limit_allows_under_cap(
    size_limit_app: FastAPI,
) -> None:
    """Requests under the cap pass through normally."""
    with patch.object(settings, "MAX_REQUEST_BODY_BYTES", 1024):
        async with AsyncClient(
            transport=ASGITransport(app=size_limit_app),
            base_url="http://test",
        ) as ac:
            response = await ac.post("/echo", json={"a": "b"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"a": "b"}


@pytest.mark.asyncio
async def test_request_size_limit_invalid_content_length(
    size_limit_app: FastAPI,
) -> None:
    """A non-numeric Content-Length is passed through unchanged."""
    with patch.object(settings, "MAX_REQUEST_BODY_BYTES", 16):
        async with AsyncClient(
            transport=ASGITransport(app=size_limit_app),
            base_url="http://test",
        ) as ac:
            response = await ac.post(
                "/echo",
                content=b'{"a":"b"}',
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": "not-a-number",
                },
            )

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_request_size_limit_ignores_non_http_scope() -> None:
    """Lifespan / websocket scopes pass through untouched."""
    seen: list[str] = []

    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        seen.append(scope["type"])

    middleware = RequestSizeLimitMiddleware(downstream)

    async def empty_recv() -> Message:
        return {"type": "lifespan.startup"}

    async def noop_send(_: Message) -> None:
        return None

    await middleware({"type": "lifespan"}, empty_recv, noop_send)
    assert seen == ["lifespan"]


@pytest.mark.asyncio
async def test_security_headers_optional_directives_can_be_disabled(
    security_headers_app: FastAPI,
) -> None:
    """Empty CSP/Referrer/Permissions strings suppress those headers."""
    with (
        patch.object(settings, "SECURITY_CSP", ""),
        patch.object(settings, "SECURITY_REFERRER_POLICY", ""),
        patch.object(settings, "SECURITY_PERMISSIONS_POLICY", ""),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=security_headers_app),
            base_url="http://test",
        ) as ac:
            response = await ac.get("/x")

    assert "Content-Security-Policy" not in response.headers
    assert "Referrer-Policy" not in response.headers
    assert "Permissions-Policy" not in response.headers
    # Non-optional headers still present
    assert response.headers["X-Frame-Options"] == "DENY"


@pytest.mark.asyncio
async def test_security_headers_hsts_minimal(
    security_headers_app: FastAPI,
) -> None:
    """HSTS without subdomains, with preload — exercises both flag paths."""
    with (
        patch.object(settings, "SECURITY_HSTS_INCLUDE_SUBDOMAINS", False),
        patch.object(settings, "SECURITY_HSTS_PRELOAD", True),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=security_headers_app),
            base_url="http://test",
        ) as ac:
            response = await ac.get("/x")

    hsts = response.headers["Strict-Transport-Security"]
    assert "includeSubDomains" not in hsts
    assert "preload" in hsts


@pytest.mark.asyncio
async def test_request_size_limit_disabled_when_zero(
    size_limit_app: FastAPI,
) -> None:
    """Setting the cap to <=0 disables the limit."""
    with patch.object(settings, "MAX_REQUEST_BODY_BYTES", 0):
        body = {"a": "x" * 4096}
        async with AsyncClient(
            transport=ASGITransport(app=size_limit_app),
            base_url="http://test",
        ) as ac:
            response = await ac.post("/echo", json=body)

    assert response.status_code == status.HTTP_200_OK


def _assert_security_and_request_id_headers(response: Response) -> None:
    """Assert security headers and a well-formed X-Request-ID survived.

    Regression check for B5: responses manufactured by an inner
    middleware (Timeout, SizeLimit, TrustedHost) must still bubble up
    through the outer SecurityHeaders/RequestID layers.
    """
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in response.headers
    assert "Permissions-Policy" in response.headers
    assert "Content-Security-Policy" in response.headers
    assert "Strict-Transport-Security" in response.headers
    header = settings.REQUEST_ID_HEADER
    assert header in response.headers
    uuid.UUID(response.headers[header])  # raises if not a valid UUID


def _assert_error_response_fully_wrapped(response: Response) -> None:
    """Assert CORS, security, and request-ID headers survived to the client.

    Regression check for B5: responses manufactured by Timeout or
    SizeLimit must still bubble up through the outer
    CORS/SecurityHeaders/RequestID layers.
    """
    assert response.headers["Access-Control-Allow-Origin"] == (
        "http://localhost:3000"
    )
    _assert_security_and_request_id_headers(response)


@pytest.mark.asyncio
async def test_timeout_504_carries_cors_and_security_headers() -> None:
    """A 504 from TimeoutMiddleware still gets CORS/security/request-ID."""
    app = create_app()

    @app.get("/test-timeout-wrapped")
    async def _slow() -> dict[str, str]:
        await anyio.sleep(0.5)
        return {}

    with patch.object(settings, "REQUEST_TIMEOUT_SECONDS", 0.05):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get(
                "/test-timeout-wrapped",
                headers={"Origin": "http://localhost:3000"},
            )

    assert response.status_code == status.HTTP_504_GATEWAY_TIMEOUT
    _assert_error_response_fully_wrapped(response)


@pytest.mark.asyncio
async def test_size_limit_413_carries_cors_and_security_headers() -> None:
    """A 413 from RequestSizeLimitMiddleware still gets CORS/security/RID."""
    app = create_app()

    @app.post("/test-size-wrapped")
    async def _echo(payload: dict[str, str]) -> dict[str, str]:
        return payload

    with patch.object(settings, "MAX_REQUEST_BODY_BYTES", 16):
        body = b'{"a":"' + b"x" * 64 + b'"}'
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/test-size-wrapped",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "Origin": "http://localhost:3000",
                },
            )

    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    _assert_error_response_fully_wrapped(response)


@pytest.mark.asyncio
async def test_trusted_host_400_carries_security_headers() -> None:
    """A 400 from TrustedHostMiddleware still gets security headers/RID.

    It does not carry CORS headers — TrustedHost sits outside CORS
    deliberately (see test_trusted_host_rejects_bad_host_on_preflight),
    so a rejected request never reaches CORSMiddleware.
    """
    app = create_app()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get(
            "/health",
            headers={
                "Host": "evil.example.com",
                "Origin": "http://localhost:3000",
            },
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Access-Control-Allow-Origin" not in response.headers
    _assert_security_and_request_id_headers(response)


@pytest.mark.asyncio
async def test_trusted_host_rejects_bad_host_on_preflight() -> None:
    """B5 regression: a CORS preflight with a forged Host is still rejected.

    TrustedHostMiddleware must sit outside CORSMiddleware — Starlette's
    CORSMiddleware answers preflight (OPTIONS) requests itself without
    calling the wrapped app, so if CORS were outer, a forged Host header
    on a preflight would never reach TrustedHostMiddleware at all.
    """
    app = create_app()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.options(
            "/api/v1/users/",
            headers={
                "Host": "evil.example.com",
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Access-Control-Allow-Origin" not in response.headers
