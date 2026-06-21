import asyncio
from collections.abc import Callable, Generator
from types import SimpleNamespace

import httpx
import pytest
import stamina
from fastapi import status

from app.core.config import settings
from app.core.exceptions import (
    BadGatewayError,
    GatewayTimeoutError,
    InternalServerError,
    ServiceUnavailableError,
)
from app.http.client import (
    ResilientHTTPClient,
    create_http_client,
    get_http_client,
)


@pytest.fixture(autouse=True)
def _fast_retries() -> Generator[None]:
    """Disable stamina backoff so retry tests run instantly.

    Keeps the configured number of attempts (``HTTP_RETRY_ATTEMPTS``)
    but removes the exponential-backoff sleeps between them.
    """
    stamina.set_testing(True, attempts=settings.HTTP_RETRY_ATTEMPTS)
    yield
    stamina.set_testing(False)


def _client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> ResilientHTTPClient:
    """Build a resilient client whose transport runs ``handler``."""
    return create_http_client(transport=httpx.MockTransport(handler))


async def test_request_returns_response() -> None:
    """A successful call returns the upstream response unchanged."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    client = _client(handler)
    response = await client.get("http://upstream.test/widgets")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"ok": True}
    await client.aclose()


async def test_non_2xx_status_returned_not_raised() -> None:
    """A 404 is a valid domain outcome and must not raise."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = _client(handler)
    response = await client.get("http://upstream.test/missing")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    await client.aclose()


async def test_retry_then_success() -> None:
    """Transient transport failures are retried until one succeeds."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < settings.HTTP_RETRY_ATTEMPTS:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200)

    client = _client(handler)
    response = await client.get("http://upstream.test/flaky")

    assert response.status_code == status.HTTP_200_OK
    assert calls == settings.HTTP_RETRY_ATTEMPTS
    await client.aclose()


async def test_transport_error_exhausted_raises_bad_gateway() -> None:
    """Persistent transport errors surface as 502 after retries."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("down", request=request)

    client = _client(handler)
    with pytest.raises(BadGatewayError):
        await client.get("http://upstream.test/down")

    assert calls == settings.HTTP_RETRY_ATTEMPTS
    await client.aclose()


async def test_timeout_exhausted_raises_gateway_timeout() -> None:
    """Persistent timeouts surface as 504 after retries."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    client = _client(handler)
    with pytest.raises(GatewayTimeoutError):
        await client.get("http://upstream.test/slow")

    await client.aclose()


async def test_retry_on_status_returns_last_response() -> None:
    """With retry_on_status, an exhausted 503 returns the last response."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    client = _client(handler)
    response = await client.get(
        "http://upstream.test/unstable", retry_on_status=True
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert calls == settings.HTTP_RETRY_ATTEMPTS
    await client.aclose()


async def test_status_not_retried_by_default() -> None:
    """Without retry_on_status, a 503 is returned after a single call."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    client = _client(handler)
    response = await client.get("http://upstream.test/unstable")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert calls == 1
    await client.aclose()


async def test_circuit_opens_and_fails_fast() -> None:
    """After repeated failures the breaker opens and short-circuits."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("down", request=request)

    client = _client(handler)

    # Hammer the host until the breaker opens (ServiceUnavailableError).
    for _ in range(20):
        try:
            await client.get("http://upstream.test/down")
        except BadGatewayError:
            continue
        except ServiceUnavailableError:
            break
    else:  # pragma: no cover - breaker must open within the budget
        pytest.fail("circuit breaker never opened")

    # Once open, a further call must not touch the transport at all.
    calls_when_open = calls
    with pytest.raises(ServiceUnavailableError):
        await client.get("http://upstream.test/down")
    assert calls == calls_when_open
    await client.aclose()


async def test_breaker_is_per_host() -> None:
    """An open circuit for one host does not affect another host."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "bad.test":
            raise httpx.ConnectError("down", request=request)
        return httpx.Response(200)

    client = _client(handler)

    for _ in range(20):
        try:
            await client.get("http://bad.test/x")
        except BadGatewayError:
            continue
        except ServiceUnavailableError:
            break

    # The healthy host is unaffected by the open circuit on bad.test.
    response = await client.get("http://good.test/x")
    assert response.status_code == status.HTTP_200_OK
    await client.aclose()


async def test_retry_on_status_recovers_within_budget() -> None:
    """A retryable status that recovers mid-budget returns the success."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < settings.HTTP_RETRY_ATTEMPTS:
            return httpx.Response(503)
        return httpx.Response(200)

    client = _client(handler)
    response = await client.get("http://upstream.test/x", retry_on_status=True)

    assert response.status_code == status.HTTP_200_OK
    assert calls == settings.HTTP_RETRY_ATTEMPTS
    await client.aclose()


async def test_retry_on_status_failures_open_circuit() -> None:
    """Exhausted retryable statuses count toward the breaker and open it."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    client = _client(handler)

    opened = False
    for _ in range(20):
        try:
            await client.get("http://upstream.test/x", retry_on_status=True)
        except ServiceUnavailableError:
            opened = True
            break
    assert opened, "retryable-status failures should trip the breaker"
    await client.aclose()


async def test_circuit_recovers_after_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A half-open trial closes the circuit once the upstream recovers."""
    monkeypatch.setattr("app.http.client._BREAKER_TTL", 0.1)
    failing = True

    def handler(request: httpx.Request) -> httpx.Response:
        if failing:
            raise httpx.ConnectError("down", request=request)
        return httpx.Response(200)

    client = _client(handler)

    for _ in range(20):
        try:
            await client.get("http://flap.test/x")
        except BadGatewayError:
            continue
        except ServiceUnavailableError:
            break

    # Upstream recovers; wait out the open window, then the next call
    # should be allowed through (half-open) and close the circuit.
    failing = False
    await asyncio.sleep(0.15)
    response = await client.get("http://flap.test/x")

    assert response.status_code == status.HTTP_200_OK
    await client.aclose()


async def test_hostless_url_raises() -> None:
    """A relative/host-less URL is rejected instead of sharing a breaker."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    client = _client(handler)
    with pytest.raises(InternalServerError):
        await client.get("/relative/path")
    await client.aclose()


def test_get_http_client_missing_state_raises() -> None:
    """The dependency raises when the client is not initialised."""
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    with pytest.raises(InternalServerError):
        get_http_client(request)  # type: ignore


def test_get_http_client_returns_state_client() -> None:
    """The dependency returns the client stored on app.state."""
    sentinel = object()
    state = SimpleNamespace(http_client=sentinel)
    request = SimpleNamespace(app=SimpleNamespace(state=state))
    assert get_http_client(request) is sentinel  # type: ignore


@pytest.mark.parametrize("verb", ["get", "post", "put", "patch", "delete"])
async def test_verb_helpers_dispatch(verb: str) -> None:
    """Each verb helper sends its corresponding HTTP method."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.method)
        return httpx.Response(200)

    client = _client(handler)
    response = await getattr(client, verb)("http://upstream.test/x")

    assert response.status_code == status.HTTP_200_OK
    assert seen == [verb.upper()]
    await client.aclose()


async def test_aclose_closes_underlying_client() -> None:
    """Aclose releases the underlying httpx client."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    client = _client(handler)
    await client.aclose()
    assert client.is_closed
