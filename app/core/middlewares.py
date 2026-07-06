import re
import uuid

import anyio
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Environment, settings
from app.core.schemas import ProblemDetail

logger = structlog.get_logger(__name__)

# Accept an inbound request ID only if it is a short, printable token.
# Rejecting everything else stops a client from injecting newlines or
# control characters into logs and the reflected response header.
# Anchor with \Z, not $: $ also matches just before a trailing newline,
# which would let a value ending in "\n" slip past the injection guard.
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}\Z")


def _safe_request_id(raw: str | None) -> str:
    """Return the inbound request ID if safe, else a fresh UUID."""
    if raw is not None and _REQUEST_ID_RE.match(raw):
        return raw
    return str(uuid.uuid4())


class TimeoutMiddleware:
    """Enforce a per-request wall-clock timeout using anyio cancel scopes.

    Pure ASGI so it adds no ``BaseHTTPMiddleware`` task/streaming
    overhead. A 504 is only manufacturable while the response has not
    yet started; once ``http.response.start`` has gone out the headers
    are already on the wire, so a timeout past that point can only abort
    the connection (the clock stops at headers — the same limitation the
    old ``BaseHTTPMiddleware`` had, now explicit rather than silent).
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap the downstream ASGI app."""
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Cancel the request and return 504 if it exceeds the timeout."""
        timeout = settings.REQUEST_TIMEOUT_SECONDS
        if scope["type"] != "http" or timeout <= 0:
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            with anyio.fail_after(timeout):
                await self.app(scope, receive, send_wrapper)
        except TimeoutError:
            logger.warning(
                "request_timeout",
                path=scope.get("path", ""),
                timeout=timeout,
            )
            if response_started:
                # Headers already sent — the fail_after scope has torn
                # down the handler; nothing left to do but let the abort
                # propagate.
                raise
            problem = ProblemDetail(
                type="urn:quoin:error:gateway_timeout_error",
                title="Gateway Timeout",
                status=504,
                detail=f"Request exceeded {timeout}s timeout",
                instance=scope.get("path", ""),
            )
            await _send_problem(send, problem, 504)


class RequestIDMiddleware:
    """Generate or propagate X-Request-ID and bind it to the log context.

    Pure ASGI. The contextvar is unbound only after the downstream app
    has fully completed, so log lines emitted while a response body is
    still streaming keep their ``request_id`` binding.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap the downstream ASGI app."""
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Assign a request ID, bind it to structlog, echo it in response."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        header = settings.REQUEST_ID_HEADER
        inbound = _header_value(scope, header.lower().encode("latin-1"))
        request_id = _safe_request_id(inbound)
        structlog.contextvars.bind_contextvars(request_id=request_id)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(raw=message["headers"])[header] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")


class SecurityHeadersMiddleware:
    """Add baseline security response headers on every response.

    Emits HSTS, CSP, X-Frame-Options, X-Content-Type-Options,
    Referrer-Policy, and Permissions-Policy. All values are configurable
    via ``QUOIN_SECURITY_*`` settings; the middleware itself is gated by
    ``QUOIN_SECURITY_HEADERS_ENABLED``. Pure ASGI.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap the downstream ASGI app."""
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Apply configured security headers to the downstream response."""
        if scope["type"] != "http" or not settings.SECURITY_HEADERS_ENABLED:
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                _apply_security_headers(MutableHeaders(raw=message["headers"]))
            await send(message)

        await self.app(scope, receive, send_with_headers)


def _apply_security_headers(headers: MutableHeaders) -> None:
    """Set the configured security headers, never clobbering existing ones."""
    headers.setdefault("X-Content-Type-Options", "nosniff")
    headers.setdefault("X-Frame-Options", "DENY")
    if settings.SECURITY_REFERRER_POLICY:
        headers.setdefault("Referrer-Policy", settings.SECURITY_REFERRER_POLICY)
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


async def _send_problem(
    send: Send,
    problem: ProblemDetail,
    status: int,
    *,
    close: bool = False,
) -> None:
    """Send an RFC 9457 Problem Details response over raw ASGI.

    Args:
        send: The ASGI send callable.
        problem: The Problem Details body to serialise.
        status: The HTTP status code.
        close: When True, add ``Connection: close`` — used where the
            request stream may still hold an unread body (a rejected
            oversize upload) that we do not want to drain.
    """
    body = problem.model_dump_json(exclude_none=True).encode("utf-8")
    headers = [
        (b"content-type", b"application/problem+json"),
        (b"content-length", str(len(body)).encode("ascii")),
    ]
    if close:
        headers.append((b"connection", b"close"))
    await send(
        {"type": "http.response.start", "status": status, "headers": headers}
    )
    await send({"type": "http.response.body", "body": body})


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
    await _send_problem(send, problem, 413, close=True)


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
    LIFO). SecurityHeaders and RequestID are added last so they become
    the outermost layers: every response — including 504s from
    TimeoutMiddleware, 413s from the size limit, and 400s from
    TrustedHost — bubbles back up through them and gets security
    headers and an X-Request-ID echo before reaching the client.

    TrustedHost sits outside CORS so Host validation applies to every
    request, including a CORS preflight — Starlette's CORSMiddleware
    answers preflight (OPTIONS) requests itself without calling the
    wrapped app, so if CORS were outer, a forged Host header on a
    preflight would never reach TrustedHost at all. CORS in turn wraps
    Timeout and SizeLimit so their 504/413 responses still get CORS
    headers; a bad-Host 400 from TrustedHost does not get CORS headers
    (it isn't part of a legitimate CORS negotiation), but it does get
    the outer SecurityHeaders/RequestID treatment. Within that, Timeout
    wraps SizeLimit so oversize bodies are still rejected before the
    timeout clock ticks into downstream work. The in-flight counter is
    added first of all so it sits innermost — closest to the router —
    and brackets only requests that pass every outer layer and reach a
    handler.
    """
    app.add_middleware(InFlightRequestMiddleware)  # innermost — added first
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(TimeoutMiddleware)
    configure_cors(app)
    configure_trusted_hosts(app)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)  # outermost — added last


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
