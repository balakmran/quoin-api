import uuid
from collections.abc import Awaitable, Callable

import anyio
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import Environment, settings
from app.core.exception_handlers import _problem_response
from app.core.schemas import ProblemDetail

logger = structlog.get_logger(__name__)


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Enforce a per-request wall-clock timeout using anyio cancel scopes."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Cancel the request and return 504 if it exceeds the timeout.

        Args:
            request: The incoming request.
            call_next: The next middleware or route handler.

        Returns:
            The response from the downstream handler, or a 504 Problem
            Details response if the deadline is exceeded.
        """
        timeout = settings.REQUEST_TIMEOUT_SECONDS
        if timeout <= 0:
            return await call_next(request)
        try:
            with anyio.fail_after(timeout):
                return await call_next(request)
        except TimeoutError:
            logger.warning(
                "request_timeout",
                path=request.url.path,
                timeout=timeout,
            )
            problem = ProblemDetail(
                type="urn:quoin:error:gateway_timeout_error",
                title="Gateway Timeout",
                status=504,
                detail=f"Request exceeded {timeout}s timeout",
                instance=request.url.path,
            )
            return _problem_response(problem, 504)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate or propagate X-Request-ID and bind it to the log context."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Assign a request ID, bind it to structlog, echo it in response."""
        header = settings.REQUEST_ID_HEADER
        request_id = request.headers.get(header, str(uuid.uuid4()))
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
        response.headers[header] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add baseline security response headers on every response.

    Emits HSTS, CSP, X-Frame-Options, X-Content-Type-Options,
    Referrer-Policy, and Permissions-Policy. All values are configurable
    via ``QUOIN_SECURITY_*`` settings; the middleware itself is gated by
    ``QUOIN_SECURITY_HEADERS_ENABLED``.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Apply configured security headers to the downstream response."""
        response = await call_next(request)
        if not settings.SECURITY_HEADERS_ENABLED:
            return response

        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        if settings.SECURITY_REFERRER_POLICY:
            headers.setdefault(
                "Referrer-Policy", settings.SECURITY_REFERRER_POLICY
            )
        if settings.SECURITY_PERMISSIONS_POLICY:
            headers.setdefault(
                "Permissions-Policy", settings.SECURITY_PERMISSIONS_POLICY
            )
        if settings.SECURITY_CSP:
            headers.setdefault("Content-Security-Policy", settings.SECURITY_CSP)
        if settings.SECURITY_HSTS_MAX_AGE > 0:
            value = f"max-age={settings.SECURITY_HSTS_MAX_AGE}"
            if settings.SECURITY_HSTS_INCLUDE_SUBDOMAINS:
                value += "; includeSubDomains"
            if settings.SECURITY_HSTS_PRELOAD:
                value += "; preload"
            headers.setdefault("Strict-Transport-Security", value)
        return response


class RequestSizeLimitMiddleware:
    """Reject request bodies that exceed ``QUOIN_MAX_REQUEST_BODY_BYTES``.

    Pure ASGI middleware that rejects an oversize advertised
    ``Content-Length`` up-front with a 413 RFC 9457 Problem Details
    response. Chunked / non-conforming clients that omit
    ``Content-Length`` are not enforced here — uvicorn/h11 caps raw
    protocol buffers at a lower layer, and adding a streaming counter
    here measurably complicates the request path for a vanishingly
    small attack surface.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap the downstream ASGI app."""
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Enforce the body-size cap for HTTP requests."""
        limit = settings.MAX_REQUEST_BODY_BYTES
        if scope["type"] != "http" or limit <= 0:
            await self.app(scope, receive, send)
            return

        content_length = _header_value(scope, b"content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                declared = -1
            if declared > limit:
                await _send_413(send, scope.get("path", ""), limit)
                return

        await self.app(scope, receive, send)


class InFlightRequestMiddleware:
    """Track in-flight HTTP requests for graceful-shutdown draining.

    Pure ASGI middleware that increments the ``app.state.lifecycle``
    in-flight counter while a request is being processed and decrements
    it once the response is complete. The ``/health`` and ``/ready``
    probe paths are excluded so orchestrator polling does not perturb
    the gauge the shutdown drain waits on.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap the downstream ASGI app."""
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Bracket the request in the in-flight counter, probes aside."""
        if scope["type"] != "http" or scope.get("path", "") in _PROBE_PATHS:
            await self.app(scope, receive, send)
            return

        lifecycle = getattr(scope["app"].state, "lifecycle", None)
        if lifecycle is None:
            raise RuntimeError(
                "InFlightRequestMiddleware requires app.state.lifecycle. "
                "Ensure create_app() sets it before "
                "configure_middlewares()."
            )
        lifecycle.acquire()
        try:
            await self.app(scope, receive, send)
        finally:
            lifecycle.release()


_PROBE_PATHS = frozenset({"/health", "/ready"})


def _header_value(scope: Scope, name: bytes) -> str | None:
    """Return the first matching request header value, or None."""
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return value.decode("latin-1")
    return None


async def _send_413(send: Send, path: str, limit: int) -> None:
    """Send a 413 RFC 9457 Problem Details response and close the stream."""
    logger.warning("request_too_large", path=path, limit=limit)
    problem = ProblemDetail(
        type="urn:quoin:error:payload_too_large",
        title="Content Too Large",
        status=413,
        detail=f"Request body exceeds {limit} bytes",
        instance=path,
    )
    body = problem.model_dump_json(exclude_none=True).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/problem+json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"connection", b"close"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _has_wildcard(values: list[str]) -> bool:
    """Return True if any value in the list is a bare wildcard ``*``."""
    return any(v.strip() == "*" for v in values)


def configure_cors(app: FastAPI) -> None:
    """Configure CORS middleware with an explicit allowlist.

    Rejects wildcard ``allow_methods`` / ``allow_headers`` combined with
    ``allow_credentials=True`` outside development; that combination is
    rejected by browsers and silently disables credentialed CORS.
    """
    if not settings.BACKEND_CORS_ORIGINS:
        return

    methods = settings.BACKEND_CORS_ALLOW_METHODS
    headers = settings.BACKEND_CORS_ALLOW_HEADERS
    allow_credentials = settings.BACKEND_CORS_ALLOW_CREDENTIALS

    if (
        settings.ENV != Environment.development
        and allow_credentials
        and (_has_wildcard(methods) or _has_wildcard(headers))
    ):
        raise RuntimeError(
            "CORS misconfiguration: allow_credentials=True with wildcard "
            "allow_methods/allow_headers is rejected outside development. "
            "Set QUOIN_BACKEND_CORS_ALLOW_METHODS and "
            "QUOIN_BACKEND_CORS_ALLOW_HEADERS to explicit lists."
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=allow_credentials,
        allow_methods=methods,
        allow_headers=headers,
    )


def configure_trusted_hosts(app: FastAPI) -> None:
    """Configure TrustedHost middleware."""
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )


def configure_middlewares(app: FastAPI) -> None:
    """Configure all application middlewares.

    Middleware is registered in innermost-first order (add_middleware is
    LIFO). TimeoutMiddleware is added last so it becomes the outermost
    layer and wraps the entire request lifecycle; the size limit sits
    just inside it so oversize bodies are rejected before any
    downstream work. The in-flight counter is added first of all so it
    sits innermost — closest to the router — and brackets only requests
    that pass the outer layers (CORS, TrustedHost, etc.) and reach a
    handler.
    """
    app.add_middleware(InFlightRequestMiddleware)  # innermost — added first
    configure_cors(app)
    configure_trusted_hosts(app)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(TimeoutMiddleware)  # outermost — added last


__all__ = [
    "InFlightRequestMiddleware",
    "RequestIDMiddleware",
    "RequestSizeLimitMiddleware",
    "SecurityHeadersMiddleware",
    "TimeoutMiddleware",
    "configure_cors",
    "configure_middlewares",
    "configure_trusted_hosts",
]
