# Observability

Every request produces structured logs ([Structlog](https://www.structlog.org/))
and OpenTelemetry traces, and the two share a `request_id`, `trace_id`,
and `caller`. Logs answer "what happened?"; traces answer "where did the
time go?". Both work with no code in your routes; this page covers what
you get for free and how to add your own.

## Structured Logging

Logging is configured by `setup_logging()` in
[`app/core/logging.py`](https://github.com/balakmran/quoin-api/blob/main/app/core/logging.py),
called from `create_app()`. Two independent settings control it:
`QUOIN_ENV` picks the **format**, `QUOIN_LOG_LEVEL` the **verbosity**
(`INFO` by default).

- **Development and test** — one human-readable line per event, in local
  time:

  ```
  2026-02-15T15:30:00.123456 [info     ] user_created email=test@example.com user_id=abc123
  ```

- **Production** — one JSON object per event, timestamped in UTC so logs
  from many hosts line up:

  ```json
  {"event": "user_created", "user_id": "abc123", "level": "info",
   "timestamp": "2026-02-15T15:30:00.123456+00:00"}
  ```

### Logging from your code

Name the event in `snake_case` and pass data as **keyword arguments**,
never an f-string, so every field stays searchable. Never log secrets or
tokens.

```python
import structlog

logger = structlog.get_logger()

logger.info("user_created", user_id=str(user.id), email=user.email)

try:
    await external_api_call()
except Exception:
    logger.exception("external_api_error", retry_count=3)  # with traceback
    raise
```

To attach fields to every event for a stretch of work, bind them to the
context:

```python
from structlog.contextvars import bind_contextvars, clear_contextvars

bind_contextvars(order_id=order_id)
logger.info("order_processing_started")  # includes order_id
clear_contextvars()
```

### Fields added for you

- **`request_id`** — `RequestIDMiddleware` reads it from the incoming
  `X-Request-ID` header, or generates a UUID, and echoes it on the
  response. Rename the header with `QUOIN_REQUEST_ID_HEADER`.
- **`caller`** — once a route authenticates, `get_current_caller` binds
  the token's `sub`. Public routes log no caller.
- **`trace_id`, `span_id`** — added during a traced request, so any log
  line leads to its trace. Omitted when tracing is off.

`RequestIDMiddleware` clears the request's fields when it ends.

### Error Response Levels

The exception handlers log each error response at a level that matches
who has to act on it:

| Status | Level | Traceback |
| :----- | :---- | :-------- |
| 5xx | `error` | yes |
| 401, 403 | `warning` | no |
| Any other 4xx, including 404 and 405 | `info` | no |

So `QUOIN_LOG_LEVEL=WARNING` hides routine client errors, such as a
scanner probing unknown paths, but keeps denials and server faults.

### Access Log

`AccessLogMiddleware` writes one `http_request` line per completed
request, with `method`, `path`, `route`, `status`, and `duration_ms`.
Use `route`, the matched template such as `/api/v1/users/{user_id}`,
for dashboards; `path` is too high-cardinality. `route` is `null` on a
404.

The middleware sits outside the timeout and body-size limits, so 504 and
413 responses are logged with their real status. `/health` and `/ready`
are skipped. Turn the access log off with
`QUOIN_ACCESS_LOG_ENABLED=False`.

## OpenTelemetry Tracing

[`app/core/telemetry.py`](https://github.com/balakmran/quoin-api/blob/main/app/core/telemetry.py)
instruments three things when `QUOIN_OTEL_ENABLED=True` (the default):

- **HTTP requests** — `setup_opentelemetry(app)`, at app creation
- **Database queries** — `instrument_sqlalchemy_engine(engine)`, in the
  lifespan once the engine exists
- **Outbound HTTP** — the shared `ResilientHTTPClient`, via
  `instrument_http_client`

Every span carries `service.name`, `service.version`, and
`deployment.environment.name` (from `QUOIN_ENV`). The standard
`OTEL_SERVICE_NAME` and `OTEL_RESOURCE_ATTRIBUTES` variables still add
anything not set there.

With `QUOIN_OTEL_ENABLED=False` nothing is instrumented, so there is no
overhead.

### Custom Spans

Services and repositories get no span of their own. Add one where the
time is worth seeing, with a verb-style name and a few attributes:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("validate_order") as span:
    span.set_attribute("order.id", order_id)
    await self._validate(order_id)
```

## Viewing Traces

Spans export over OTLP, so any compatible backend works. Point
`OTEL_EXPORTER_OTLP_ENDPOINT` at it; no code changes.

- **No endpoint, development or test** — spans print to stdout.
- **Jaeger locally** — run it, then set the endpoint and open
  `http://localhost:16686`:

  ```bash
  docker run -d --name jaeger -p 16686:16686 -p 4318:4318 \
    jaegertracing/all-in-one:latest
  ```

  ```bash
  OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
  ```

- **Production** — send to Grafana Tempo, Jaeger, or, preferably, an
  [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/),
  which adds batching, retries, sampling, and fan-out.

!!! warning "Production with no endpoint configured"
    Production does not fall back to stdout. With tracing on and no
    endpoint, it logs one `otel_enabled_without_exporter` warning at
    startup and exports nothing. Set `OTEL_EXPORTER_OTLP_ENDPOINT`
    before relying on traces.

## Testing

Assert on the **event dictionary**, not formatted output.
`capture_logs()` intercepts entries before rendering, so the test holds
in any environment:

```python
from structlog.testing import capture_logs


def test_log_level_filters_below_threshold() -> None:
    try:
        with patch("app.core.logging.settings.LOG_LEVEL", "WARNING"):
            setup_logging()
            with capture_logs() as cap_logs:
                structlog.get_logger().info("suppressed")
    finally:
        setup_logging()  # restore for later tests

    assert cap_logs == []
```

The `finally` matters: `setup_logging()` reconfigures structlog for the
whole process. For per-request fields such as `request_id`, assert the
key is present rather than pinning its value.

For tracing, test the setup, not the spans. `tests/core/test_telemetry.py`
checks exporter choice, resource attributes, and that an instrumentation
failure can't crash startup.

## Troubleshooting

### Logs Not Appearing

- The event is below `QUOIN_LOG_LEVEL` (`DEBUG` is dropped by default).
- The app wasn't built by `create_app()`, so `setup_logging()` never
  ran.
- Data was passed positionally instead of as keyword arguments.

### Traces Not Captured

- `QUOIN_OTEL_ENABLED` is `False`.
- In production, `OTEL_EXPORTER_OTLP_ENDPOINT` is unset; look for
  `otel_enabled_without_exporter` at startup.
- Only **database** spans missing: `instrument_sqlalchemy_engine` must
  run in the lifespan, after the engine exists.

### Too Many Logs

Raise `QUOIN_LOG_LEVEL` to `WARNING`, or turn off the access log with
`QUOIN_ACCESS_LOG_ENABLED=False`.

### Tracing Slows Requests

A slow or unreachable OTLP collector is the usual cause in production.
Locally, turn tracing off with `QUOIN_OTEL_ENABLED=False`.

## See Also

- [Error Handling](error-handling.md) — the handlers that log error
  responses
- [Structlog Documentation](https://www.structlog.org/)
- [OpenTelemetry Python Docs](https://opentelemetry.io/docs/languages/python/)
