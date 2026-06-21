from typing import Annotated, Any

import httpx
import stamina
import structlog
from fastapi import Depends, Request
from purgatory import AsyncCircuitBreakerFactory
from purgatory.domain.model import OpenedState

from app.core import metadata
from app.core.config import settings
from app.core.exceptions import (
    BadGatewayError,
    GatewayTimeoutError,
    InternalServerError,
    ServiceUnavailableError,
)
from app.core.telemetry import instrument_http_client

logger = structlog.get_logger(__name__)

# Upstream status codes worth retrying when ``retry_on_status`` is set:
# 429 (Too Many Requests) plus the transient 5xx (500/502/503/504). Other
# 4xx are caller errors and 501 is not transient, so none are retried.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# Backoff and circuit-breaker tuning. These are module constants rather
# than settings because they are rarely worth changing per deployment;
# the two knobs that are — request timeout and retry attempts — live in
# ``QUOIN_HTTP_*`` settings.
_RETRY_WAIT_INITIAL = 0.1
_RETRY_WAIT_MAX = 2.0
_RETRY_WAIT_JITTER = 1.0
_BREAKER_THRESHOLD = 5
_BREAKER_TTL = 30.0


class _TransientStatusError(Exception):
    """Internal signal that a response status warrants a retry.

    Carries the offending response so the final (post-exhaustion) value
    can still be returned to the caller instead of being swallowed.
    """

    def __init__(self, response: httpx.Response) -> None:
        """Store the response that triggered the retry."""
        super().__init__(f"retryable status {response.status_code}")
        self.response = response


class ResilientHTTPClient:
    """A resilient wrapper around a shared ``httpx.AsyncClient``.

    Every call is guarded, from the outside in, by a per-host circuit
    breaker and then a retry loop with exponential backoff:

    - The **circuit breaker** (purgatory) fails fast with
      :class:`ServiceUnavailableError` once a host has accumulated
      ``_BREAKER_THRESHOLD`` failures, sparing the upstream (and the
      caller) from doomed retries until ``_BREAKER_TTL`` elapses.
    - The **retry loop** (stamina) replays transient transport failures
      and, when ``retry_on_status`` is set, retryable status codes.

    Transport-level failures are translated into domain exceptions
    (502/503/504); response *status codes* are deliberately left for the
    caller to interpret, since a 404 or 409 is often a valid domain
    outcome rather than an infrastructure error.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        breakers: AsyncCircuitBreakerFactory,
    ) -> None:
        """Initialize the wrapper.

        Args:
            client: The underlying shared async HTTP client.
            breakers: Factory producing per-host circuit breakers.
        """
        self._client = client
        self._breakers = breakers

    @property
    def is_closed(self) -> bool:
        """Whether the underlying client has been closed."""
        return self._client.is_closed

    def instrument(self) -> None:
        """Enable OpenTelemetry tracing on the underlying client.

        Keeps the raw client private — callers cannot reach it to bypass
        the resilience wrapper. No-op when ``QUOIN_OTEL_ENABLED`` is false.
        """
        instrument_http_client(self._client)

    def _breaker_key(self, url: httpx.URL | str) -> str:
        """Derive the circuit-breaker key (the target host) for a URL.

        Args:
            url: The request URL; must be absolute (the shared client has
                no base URL).

        Returns:
            The target host, used as the per-host breaker key.

        Raises:
            InternalServerError: If the URL has no host. Falling back to a
                shared key would collapse unrelated upstreams onto one
                circuit breaker, so a host-less URL is rejected instead.
        """
        host = httpx.URL(url).host
        if not host:
            raise InternalServerError(
                f"Outbound HTTP requires an absolute URL with a host: {url!r}"
            )
        return host

    async def request(
        self,
        method: str,
        url: httpx.URL | str,
        *,
        retry_on_status: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        """Send a request with retries and circuit breaking.

        Args:
            method: HTTP method (e.g. ``"GET"``).
            url: Absolute URL of the upstream endpoint.
            retry_on_status: When True, also retry responses whose status
                is transient (429/5xx). Off by default so non-idempotent
                writes are never silently replayed.
            **kwargs: Forwarded to ``httpx.AsyncClient.request`` (e.g.
                ``params``, ``json``, ``headers``, ``timeout``).

        Returns:
            The ``httpx.Response`` (any status code) when the call
            completes within the retry budget.

        Raises:
            ServiceUnavailableError: The circuit for this host is open.
            GatewayTimeoutError: The upstream timed out after retries.
            BadGatewayError: A transport/connection error after retries.
            InternalServerError: The URL has no host (see ``_breaker_key``).

        Note:
            Non-transport httpx errors (e.g. ``InvalidURL``,
            ``TooManyRedirects``) are not translated here and propagate to
            the caller / global handler.
        """
        retry_on: tuple[type[Exception], ...] = (httpx.TransportError,)
        if retry_on_status:
            retry_on += (_TransientStatusError,)

        host = self._breaker_key(url)
        try:
            breaker = await self._breakers.get_breaker(host)
            async with breaker:
                async for attempt in stamina.retry_context(
                    on=retry_on,
                    attempts=settings.HTTP_RETRY_ATTEMPTS,
                    wait_initial=_RETRY_WAIT_INITIAL,
                    wait_max=_RETRY_WAIT_MAX,
                    wait_jitter=_RETRY_WAIT_JITTER,
                    timeout=None,
                ):
                    with attempt:
                        response = await self._client.request(
                            method, url, **kwargs
                        )
                        if (
                            retry_on_status
                            and response.status_code in _RETRYABLE_STATUS
                        ):
                            raise _TransientStatusError(response)
                        return response
        except _TransientStatusError as exc:
            # Retries exhausted on a transient status — hand the last
            # response back rather than raising; the breaker has already
            # recorded the failure on the way out. Log it so a hard-down
            # upstream is visible, mirroring the transport-error paths.
            logger.warning(
                "http_status_retries_exhausted",
                host=host,
                method=method,
                status_code=exc.response.status_code,
                attempts=settings.HTTP_RETRY_ATTEMPTS,
            )
            return exc.response
        except OpenedState as exc:
            logger.warning("http_circuit_open", host=host)
            raise ServiceUnavailableError(
                "Upstream service is unavailable"
            ) from exc
        except httpx.TimeoutException as exc:
            logger.warning(
                "http_upstream_timeout", method=method, error=repr(exc)
            )
            raise GatewayTimeoutError("Upstream request timed out") from exc
        except httpx.TransportError as exc:
            logger.warning(
                "http_upstream_error", method=method, error=repr(exc)
            )
            raise BadGatewayError("Upstream request failed") from exc
        # Unreachable: the loop either returns or raises.
        raise InternalServerError(  # pragma: no cover
            "HTTP request did not complete"
        )

    async def get(self, url: httpx.URL | str, **kwargs: Any) -> httpx.Response:
        """Send a GET request. See :meth:`request`."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: httpx.URL | str, **kwargs: Any) -> httpx.Response:
        """Send a POST request. See :meth:`request`."""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: httpx.URL | str, **kwargs: Any) -> httpx.Response:
        """Send a PUT request. See :meth:`request`."""
        return await self.request("PUT", url, **kwargs)

    async def patch(
        self, url: httpx.URL | str, **kwargs: Any
    ) -> httpx.Response:
        """Send a PATCH request. See :meth:`request`."""
        return await self.request("PATCH", url, **kwargs)

    async def delete(
        self, url: httpx.URL | str, **kwargs: Any
    ) -> httpx.Response:
        """Send a DELETE request. See :meth:`request`."""
        return await self.request("DELETE", url, **kwargs)

    async def aclose(self) -> None:
        """Close the underlying client and release pooled connections."""
        await self._client.aclose()


def create_http_client(
    transport: httpx.AsyncBaseTransport | None = None,
) -> ResilientHTTPClient:
    """Create a configured resilient HTTP client from settings.

    Args:
        transport: Optional transport override. Tests inject an
            ``httpx.MockTransport`` here to avoid real network I/O.

    Returns:
        A ready-to-use :class:`ResilientHTTPClient`.
    """
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.HTTP_TIMEOUT_SECONDS),
        headers={"User-Agent": f"{metadata.APP_NAME}/{metadata.VERSION}"},
        transport=transport,
    )
    breakers = AsyncCircuitBreakerFactory(
        default_threshold=_BREAKER_THRESHOLD,
        default_ttl=_BREAKER_TTL,
    )
    return ResilientHTTPClient(client, breakers)


def get_http_client(request: Request) -> ResilientHTTPClient:
    """Return the shared HTTP client from application state.

    The client is created once during application startup (see
    :mod:`app.main`) and reused across requests.

    Args:
        request: The current FastAPI request (used to access app.state).

    Returns:
        The shared :class:`ResilientHTTPClient`.

    Raises:
        InternalServerError: If the client is not initialised.
    """
    client = getattr(request.app.state, "http_client", None)
    if client is None:
        raise InternalServerError("HTTP client is not initialized")
    return client


HTTPClientDep = Annotated[ResilientHTTPClient, Depends(get_http_client)]
