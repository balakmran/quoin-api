# Observability

This guide explains the observability stack in the QuoinAPI,
including structured logging with Structlog and distributed tracing
with OpenTelemetry.

---

## Overview

The application provides comprehensive observability through two
complementary systems:

1. **Structured Logging** ([Structlog](https://www.structlog.org/)) —
   Machine-readable logs for debugging and monitoring
2. **Distributed Tracing** ([OpenTelemetry](https://opentelemetry.io/)) —
   Request lifecycle tracking across services

---

## Logging vs Tracing

Quick comparison to understand when to use each tool:

| Feature           | Structured Logging         | Distributed Tracing        |
| ----------------- | -------------------------- | -------------------------- |
| **Purpose**       | Record events and errors   | Track request lifecycle    |
| **When to Use**   | Business events, debugging | Performance analysis, flow |
| **Output Format** | JSON logs (production)     | Spans with attributes      |
| **Overhead**      | JSON serialisation         | Span creation and export   |
| **Control**       | `QUOIN_LOG_LEVEL` setting  | `QUOIN_OTEL_ENABLED` flag  |
| **Best For**      | "What happened?"           | "How long did it take?"    |

---

## Structured Logging

### Configuration

Logging is configured in [`app/core/logging.py`](https://github.com/balakmran/quoin-api/blob/main/app/core/logging.py)
and automatically set up when the application starts.

```python
from app.core.logging import setup_logging

setup_logging()
```

### Log Output Formats

> **TIP**: `QUOIN_ENV` controls log **format** (human vs JSON).
> `QUOIN_LOG_LEVEL` controls **verbosity**. They are independent knobs.

#### Development and test (`QUOIN_ENV=development` / `test`)

Human-readable console output, one line per event:

```
2026-02-15T15:30:00.123456 [info     ] user_created email=test@example.com user_id=abc123
2026-02-15T15:30:05.789012 [info     ] app_error message=User not found status_code=404 path=/api/v1/users/xyz
```

#### Production (`QUOIN_ENV=production`)

Machine-readable JSON:

```json
{
  "event": "user_created",
  "email": "test@example.com",
  "user_id": "abc123def456",
  "timestamp": "2026-02-15T15:30:00.123456+00:00",
  "level": "info"
}
```

In `production` the `timestamp` is emitted in **UTC** so logs
aggregated from many hosts share one timezone. Development and test
logs use host-local time to stay readable against the wall clock.

### Usage in Code

Get a structured logger and use it with **keyword arguments**:

```python
import structlog

logger = structlog.get_logger()


class UserService:
    async def create_user(self, user_create: UserCreate) -> User:
        user = await self.repository.create(user_create)

        logger.info(
            "user_created",
            user_id=str(user.id),
            email=user.email,
        )

        return user
```

!!! warning
    Always use keyword arguments for log data. This ensures fields are
    consistent and searchable.

### Log Levels

| Level       | When to Use                  | Example                                      |
| :---------- | :--------------------------- | :------------------------------------------- |
| `debug()`   | Detailed diagnostic info     | `logger.debug("cache_hit", key="user:123")`  |
| `info()`    | General informational events | `logger.info("user_created", user_id=...)`   |
| `warning()` | Unexpected but recoverable   | `logger.warning("rate_limit_approaching")`   |
| `error()`   | Errors that need attention   | `logger.error("payment_failed", reason=...)` |

### Exception Logging

Log exceptions with stack traces:

```python
try:
    result = await external_api_call()
except Exception:
    logger.exception(
        "external_api_error",
        endpoint="/api/v1/resource",
        retry_count=3,
    )
    raise
```

### Contextual Data

Bind context that applies to multiple log statements:

```python
from structlog.contextvars import bind_contextvars, clear_contextvars


async def process_order(order_id: str):
    bind_contextvars(order_id=order_id, user_id=current_user.id)

    logger.info("order_processing_started")
    # ... processing steps
    logger.info("payment_completed", amount=total)
    logger.info("order_processing_finished")

    clear_contextvars()  # Clean up context
```

All three log statements will automatically include `order_id` and
`user_id`.

### Request ID

Every request is assigned a unique ID and bound to the log context
automatically by `RequestIDMiddleware`. No code is required in routes
or services — the field appears in every log event for that request.

```json
{
  "event": "user_created",
  "request_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "level": "info"
}
```

The middleware reads the ID from the incoming request header, or
generates a `uuid4()` if the header is absent. The same header is
echoed back on the response so clients can correlate their own logs.

The header name defaults to `X-Request-ID` and is configurable:

```bash
# .env
QUOIN_REQUEST_ID_HEADER=X-Correlation-ID
```

This affects both the inbound lookup and the outbound response header,
so callers and the application always agree on the name.

### Caller

Once a route authenticates, `get_current_caller` binds the token's
`sub` to the log context as `caller`. Every later log line in that
request then says who made it, including the `http_request` access log
line. `RequestIDMiddleware` unbinds it along
with `request_id` when the request ends. Public routes have no caller
and log none.

### Error Response Levels

The exception handlers log each error response at a level that matches
who has to act on it:

| Status | Level | Traceback |
| :----- | :---- | :-------- |
| 5xx | `error` | yes |
| 401, 403 | `warning` | no |
| Any other 4xx, including 404 and 405 | `info` | no |

A deliberate 503 from `/ready`, or an outbound call that has exhausted
its retries, needs an operator. A scanner probing unknown paths does
not. So `QUOIN_LOG_LEVEL=WARNING` hides routine client errors but
keeps denials and server faults. An unhandled exception always logs at
`error` with its traceback.

### Access Log

`AccessLogMiddleware` emits exactly one structured `http_request` INFO
line as each request completes — so happy-path traffic is visible in
the log stream, not only in traces. The line carries `method`, `path`,
`route`, `status`, and `duration_ms`, plus the `request_id` (and trace
context) bound for that request:

```json
{
  "event": "http_request",
  "method": "GET",
  "path": "/api/v1/users/3f2a1c9e-...",
  "route": "/api/v1/users/{user_id}",
  "status": 200,
  "duration_ms": 12.34,
  "request_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "level": "info"
}
```

`path` is the literal request path — high-cardinality, so it is
useless as a dashboard dimension. `route` is the matched path
*template* (`scope["route"]`, set once FastAPI resolves the endpoint),
so dashboards can aggregate `GET /users/{user_id}` across every user
ID without a cardinality explosion. `route` is `null` when no route
matched (a 404).

The middleware sits inside `RequestIDMiddleware` but outside the
timeout and body-size limits, so 504 and 413 responses are logged with
their real status too. If a handler raises before responding, a line
is still recorded (with `status` 500) before the error propagates.

The `/health` and `/ready` probe paths are excluded to keep
orchestrator polling out of the stream. Disable the access log
entirely with:

```bash
# .env
QUOIN_ACCESS_LOG_ENABLED=False
```

---

## OpenTelemetry Tracing

### Configuration

OTEL is configured in [`app/core/telemetry.py`](https://github.com/balakmran/quoin-api/blob/main/app/core/telemetry.py).
`setup_opentelemetry(app)` runs at app-creation time and instruments
FastAPI; the database engine is instrumented separately, in the
lifespan, once it exists:

```python
from app.core.telemetry import instrument_sqlalchemy_engine, setup_opentelemetry

app = FastAPI(...)
setup_opentelemetry(app)  # FastAPI spans

# Inside the lifespan, once the engine is created:
instrument_sqlalchemy_engine(engine)  # database spans
```

### Resource attributes

Every span carries the identity of the service that produced it:

| Attribute | Value |
| :--- | :--- |
| `service.name` | Application name from `app/core/metadata.py` |
| `service.version` | Application version |
| `deployment.environment.name` | `QUOIN_ENV` |

These are built with `Resource.create`, which also runs the standard
OpenTelemetry detectors — so `OTEL_SERVICE_NAME` and
`OTEL_RESOURCE_ATTRIBUTES` still contribute any attribute not set
above, though the explicit values win over them.

### What Gets Traced

**Automatically instrumented:**

- HTTP requests (FastAPI)
- Database queries (SQLAlchemy, via `instrument_sqlalchemy_engine`)
- Outgoing HTTP calls (the shared `ResilientHTTPClient`, via
  `instrument_http_client`)

**Example trace hierarchy:**

```
POST /api/v1/users/
├── SELECT ... FROM users WHERE email = ?
└── INSERT INTO users ...
```

Service and repository methods get no span of their own; add one where
the time is worth seeing (see [Custom Spans](#custom-spans)).

### Custom Spans

Add custom spans for business logic:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)


class OrderService:
    async def process_order(self, order_id: str):
        with tracer.start_as_current_span("validate_order") as span:
            span.set_attribute("order.id", order_id)
            validation_result = await self._validate(order_id)
            span.set_attribute("validation.success", validation_result)

        with tracer.start_as_current_span("charge_payment"):
            await self.payment_service.charge(amount)
```

### Span Attributes

Add metadata to spans:

```python
from opentelemetry import trace

span = trace.get_current_span()
span.set_attribute("user.id", str(user.id))
span.set_attribute("user.tier", "premium")
span.set_attribute("feature.enabled", True)
```

### Log Correlation

Every log event emitted during a traced request automatically includes
`trace_id` and `span_id` fields, injected by `_add_otel_context` in
[`app/core/logging.py`](https://github.com/balakmran/quoin-api/blob/main/app/core/logging.py).
No extra code is needed in routes or services.

```json
{
  "event": "user_created",
  "request_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "level": "info"
}
```

The `trace_id` matches the span printed by the console exporter (or
the trace visible in your backend), so you can jump from any log line
directly to the full trace.

When `QUOIN_OTEL_ENABLED=False` or no active span exists, the fields
are omitted rather than set to zero values.

### Enabling/Disabling OTEL

Control via environment variable:

```bash
# .env
QUOIN_OTEL_ENABLED=True   # Enable tracing (default in production)
QUOIN_OTEL_ENABLED=False  # Disable tracing (skips all instrumentation)
```

---

## Viewing Traces

QuoinAPI exports via OTLP, the vendor-neutral OpenTelemetry wire
protocol. Any OTLP-compatible backend works without changing
application code — only the `OTEL_EXPORTER_OTLP_ENDPOINT` env var
needs to point at it.

### Console (development and test default)

With no `OTEL_EXPORTER_OTLP_ENDPOINT` set, development and test print
spans to stdout. Each span includes a `trace_id` you can match against
the `trace_id` field in your structlog output:

```
{
    name: POST /api/v1/users/
    context: {"trace_id": "4bf92f3577b34da6a3ce929d0e0e4736", ...}
    start_time: 2026-02-15T15:30:00.000000Z
    end_time: 2026-02-15T15:30:00.123456Z
}
```

### Jaeger (local UI)

[Jaeger](https://www.jaegertracing.io/) is a CNCF open-source tracing
backend. Run it as a single container:

```bash
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4318:4318 \
  jaegertracing/all-in-one:latest
```

Then point the app at it:

```bash
# .env
QUOIN_OTEL_ENABLED=True
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

Open `http://localhost:16686` and search by service name
(`quoin-api`). Each trace shows the full span tree with correlated
log fields attached.

### Production

Any OTLP-compatible backend works — set the endpoint and the app
ships spans without code changes:

| Backend | Type | OTLP endpoint |
| :--- | :--- | :--- |
| Grafana Tempo | Open source | `http://tempo:4318` |
| Jaeger | Open source (CNCF) | `http://jaeger:4318` |
| OpenTelemetry Collector | Open source (CNCF) | `http://otel-col:4318` |

!!! tip
    For production, route through the
    [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/)
    rather than exporting directly to a backend. It gives you batching,
    retry, tail-based sampling, and the ability to fan out to multiple
    backends without changing the app.

!!! warning "Production with no endpoint configured"
    Development and test fall back to printing spans to stdout when
    `OTEL_EXPORTER_OTLP_ENDPOINT` is unset. Production does not — with
    `QUOIN_OTEL_ENABLED=true` and no endpoint, it logs one
    `otel_enabled_without_exporter` warning at startup and exports no
    spans at all, rather than interleaving every span into the JSON log
    stream. Set `OTEL_EXPORTER_OTLP_ENDPOINT` (or a collector's env
    vars) before enabling OTel in production.

---

## Best Practices

### Logging

**Do:**

- Use keyword arguments for structured data
- Log business events (user_created, order_placed)
- Include relevant IDs (user_id, request_id)
- Use appropriate log levels

**Don't:**

- Log sensitive data (passwords, tokens, PII without redaction)
- Use string formatting: `logger.info(f"User {user_id}")`
- Log in tight loops (aggregate instead)
- Log the same event multiple times

### Tracing

**Do:**

- Add spans for expensive operations
- Include relevant attributes (IDs, amounts, flags)
- Use semantic naming: `validate_order` not `step_1`
- Propagate context across async boundaries

**Don't:**

- Create spans for trivial operations (<1ms)
- Add excessive attributes (keep <10 per span)
- Ignore errors (always record exceptions)
- Block on span export

---

## Performance Impact

### Logging

The cost is mostly JSON serialisation in production and scales with log
volume. Raise `QUOIN_LOG_LEVEL` or turn off the access log
(`QUOIN_ACCESS_LOG_ENABLED=False`) if it shows up in a profile.

### Tracing

- **Disabled** (`QUOIN_OTEL_ENABLED=False`): no instrumentation is
  installed, so there is no tracing overhead.
- **Enabled** (`QUOIN_OTEL_ENABLED=True`): every request and database
  query creates and exports spans. Measure it under your own load.

> **TIP**: For high-throughput services, consider sampling (e.g., trace 10% of
> requests) in the OpenTelemetry Collector.

---

## Testing

Assert on the **event dictionary**, not on formatted output. structlog's
`capture_logs()` intercepts entries before rendering, so a test stays
valid whether the environment renders JSON or console lines:

```python
from structlog.testing import capture_logs


def test_log_level_filters_below_threshold() -> None:
    """QUOIN_LOG_LEVEL suppresses logs below itself."""
    try:
        with patch("app.core.logging.settings.LOG_LEVEL", "WARNING"):
            setup_logging()
            logger = structlog.get_logger()
            with capture_logs() as cap_logs:
                logger.info("suppressed")
                logger.warning("emitted")
    finally:
        setup_logging()  # restore for later tests

    events = [entry["event"] for entry in cap_logs]
    assert "emitted" in events
    assert "suppressed" not in events
```

The `finally` is not optional. `setup_logging()` rebinds structlog's
configuration process-wide, so a test that reconfigures it and returns
leaves every later test asserting against the wrong setup. Restore it.

For contextual fields — request ID, caller — assert that the key is
*present* on the entry rather than pinning its value; the value is
generated per request and pinning it makes the test a liability.

Tracing is tested differently. `tests/core/test_telemetry.py` asserts
the **setup** path — that the right exporter is chosen for the
environment, that resource attributes carry service version and
environment, that instrumentation failures are swallowed rather than
crashing startup — and not the spans themselves. Asserting on emitted
spans mostly re-tests the OpenTelemetry SDK; asserting that a
misconfigured exporter can't take the app down tests your code.

## Troubleshooting

### Logs Not Appearing

**Check:**

1. Is the event below `QUOIN_LOG_LEVEL`? (`INFO` by default — `DEBUG`
   lines are dropped.)
2. Is `setup_logging()` called? (Should be in `create_app()`)
3. Is `QUOIN_ENV` set correctly?
4. Are you using positional args instead of keyword args?

### Traces Not Captured

**Check:**

1. Is `QUOIN_OTEL_ENABLED=True`?
2. Is `setup_opentelemetry(app)` called after app creation?
3. In production, is `OTEL_EXPORTER_OTLP_ENDPOINT` set? Without it the
   app logs `otel_enabled_without_exporter` and exports nothing.
4. Missing **database** spans only? `instrument_sqlalchemy_engine(engine)`
   must run in the lifespan, once the engine exists.

### Too Many Logs

**Solution**: raise the log level — no code change needed:

```bash
QUOIN_LOG_LEVEL=WARNING  # Only warnings and errors
```

---

## See Also

- [Structlog Documentation](https://www.structlog.org/)
- [OpenTelemetry Python Docs](https://opentelemetry.io/docs/languages/python/)
- [app/core/logging.py](https://github.com/balakmran/quoin-api/blob/main/app/core/logging.py) — Logging configuration
- [app/core/telemetry.py](https://github.com/balakmran/quoin-api/blob/main/app/core/telemetry.py) — OTEL configuration
