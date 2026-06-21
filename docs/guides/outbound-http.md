# Outbound HTTP Client

QuoinAPI ships a single, shared, resilient HTTP client for calling
upstream services. It is the sanctioned way to make outbound requests —
prefer it over instantiating ad-hoc `httpx.AsyncClient()` objects, which
leak connection pools and skip the retry, circuit-breaking, and tracing
behaviour described below.

## Why a shared client

- **One connection pool.** The client is created once during application
  startup and lives on `app.state.http_client` for the process lifetime,
  so connections are pooled and reused across requests.
- **Resilience by default.** Every call is wrapped, from the outside in,
  by a per-host circuit breaker and a retry loop with exponential
  backoff.
- **Observability for free.** When `QUOIN_OTEL_ENABLED` is true the
  client is OpenTelemetry-instrumented, so each outbound call produces a
  span correlated with the inbound request.
- **Graceful shutdown.** The client is closed during the lifespan
  shutdown, after in-flight requests have drained.

## Using it in a service

Inject `HTTPClientDep` and call the verb helpers. The dependency reads
the shared client from `app.state`:

```python
from app.http import HTTPClientDep


class WeatherService:
    def __init__(self, http: HTTPClientDep) -> None:
        self._http = http

    async def current(self, city: str) -> dict:
        response = await self._http.get(
            "https://api.example.com/weather",
            params={"city": city},
        )
        # Status codes are yours to interpret — a 404 is a domain
        # outcome, not an infrastructure failure.
        if response.status_code == 404:
            raise NotFoundError(f"No weather for {city}")
        response.raise_for_status()
        return response.json()
```

`request`, `get`, `post`, `put`, `patch`, and `delete` all accept the
same keyword arguments as `httpx.AsyncClient` (`params`, `json`,
`headers`, `timeout`, …) and return the raw `httpx.Response`.

The client is shared across every integration, so pass **absolute URLs**
rather than relying on a single base URL.

## Resilience semantics

### Retries

Transient transport failures (connection errors, timeouts) are retried
up to `QUOIN_HTTP_RETRY_ATTEMPTS` times with exponential backoff plus
jitter, powered by [stamina](https://stamina.hynek.me/). The backoff
shape (initial/max wait, jitter) is tuned via module constants in
`app/http/client.py`.

There is **no aggregate retry deadline** — each attempt is bounded by
`QUOIN_HTTP_TIMEOUT_SECONDS`, so the worst-case wall-clock for one call
is roughly `attempts × timeout` plus backoff (e.g. ~30s at the defaults).
Size the inbound request timeout accordingly, or lower `attempts` for
latency-sensitive paths.

Response **status codes are not retried by default**, so non-idempotent
writes are never silently replayed. Opt in per call when the verb is
safe to repeat:

```python
# Retry 429 / 5xx responses as well as transport errors
response = await http.get(url, retry_on_status=True)
```

!!! warning
    `retry_on_status=True` replays the request verbatim and **does not
    honour `Retry-After`**. Only use it with idempotent operations — do
    not pass it to `post()`/`put()`/`patch()` against an upstream that
    isn't idempotent, or a write may be applied more than once.

### Circuit breaker

A per-host circuit breaker
([purgatory](https://purgatory.readthedocs.io/)) opens after a
configurable number of failures and stays open for a recovery window
(both module constants in `app/http/client.py`), failing fast with a
`503` instead of hammering a struggling upstream. The breaker wraps the
**whole** retry sequence, so an open circuit short-circuits before any
retry is attempted, and each logical call counts as a single success or
failure.

The breaker tracks **transport-level health** — timeouts and connection
failures. An ordinary `4xx`/`5xx` *response* is a success from the
breaker's point of view (the upstream answered), so a host returning
steady `500`s will not trip the circuit on default calls. The exception
is `retry_on_status=True`: an exhausted retryable status then counts as a
breaker failure, since it propagates as an error through the wrapper.

## Error mapping

Only transport-level failures are translated into domain exceptions —
HTTP status codes are left for the caller to interpret.

| Condition                                  | Raised exception          | Status |
| :----------------------------------------- | :------------------------ | :----: |
| Circuit open for the target host           | `ServiceUnavailableError` | 503    |
| Upstream timed out after retries           | `GatewayTimeoutError`     | 504    |
| Connection/transport error after retries   | `BadGatewayError`         | 502    |

These are standard `QuoinError` subclasses, so the global exception
handler renders them as [RFC 9457](error-handling.md) Problem Details
automatically.

## Configuration

Two settings are env-tunable: `QUOIN_HTTP_TIMEOUT_SECONDS` and
`QUOIN_HTTP_RETRY_ATTEMPTS` (see the
[Configuration guide](configuration.md#key-settings)). Finer backoff and
circuit-breaker tuning live as module constants in `app/http/client.py` —
change them there if a deployment genuinely needs to. The connection pool
uses httpx's defaults (100 max connections, 20 keep-alive).

## Testing outbound calls

Inject an `httpx.MockTransport` via `create_http_client(transport=...)`
to exercise client behaviour without real network I/O, and use
`stamina.set_testing(True)` to remove backoff sleeps:

```python
import httpx
import stamina
from app.http.client import create_http_client


async def test_retries_then_succeeds() -> None:
    stamina.set_testing(True, attempts=3)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200)

    client = create_http_client(transport=httpx.MockTransport(handler))
    response = await client.get("http://upstream.test/x")
    assert response.status_code == 200
    await client.aclose()
```

## See Also

- [Configuration](configuration.md) — `QUOIN_HTTP_*` settings
- [Error Handling](error-handling.md) — the Problem Details contract
- [Observability](observability.md) — OpenTelemetry tracing
