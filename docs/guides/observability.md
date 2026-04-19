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
| **Overhead**      | 2-5% CPU                   | 5-10% (when enabled)       |
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

> **TIP**: `QUOIN_ENV` controls log **format** (human vs JSON). `QUOIN_LOG_LEVEL`
> controls **verbosity**. They are independent knobs.

#### Development (`QUOIN_ENV=development`)

Human-readable console output:

```
2026-02-15T15:30:00.123456 [info     ] user_created email=test@example.com user_id=abc123
2026-02-15T15:30:05.789012 [warning  ] app_error message=User not found status_code=404 path=/api/v1/users/xyz
```

#### Production (`QUOIN_ENV=production`)

Machine-readable JSON:

```json
{
  "event": "user_created",
  "email": "test@example.com",
  "user_id": "abc123def456",
  "timestamp": "2026-02-15T15:30:00.123456",
  "level": "info"
}
```

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

---

## OpenTelemetry Tracing

### Configuration

OTEL is configured in [`app/core/telemetry.py`](https://github.com/balakmran/quoin-api/blob/main/app/core/telemetry.py)
and automatically instruments FastAPI.

```python
from app.core.telemetry import setup_opentelemetry

app = FastAPI(...)
setup_opentelemetry(app)
```

### What Gets Traced

**Automatically instrumented:**

- HTTP requests (FastAPI)
- Database queries (SQLAlchemy/asyncpg)
- Outgoing HTTP calls (httpx, if used)

**Example trace hierarchy:**

```
POST /api/v1/users/
├── UserService.create_user
│   ├── UserRepository.get_by_email
│   │   └── SELECT * FROM users WHERE email = ?
│   └── UserRepository.create
│       └── INSERT INTO users VALUES (...)
```

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

### Enabling/Disabling OTEL

Control via environment variable:

```bash
# .env
QUOIN_OTEL_ENABLED=True   # Enable tracing (production)
QUOIN_OTEL_ENABLED=False  # Disable tracing (development)
```

---

## Viewing Traces

### Console Exporter (Development)

By default, traces are printed to the console:

```
{
    name: POST /api/v1/users/
    context: SpanContext(...)
    kind: SpanKind.SERVER
    parent_id: None
    start_time: 2026-02-15T15:30:00.000000Z
    end_time: 2026-02-15T15:30:00.123456Z
    attributes: {
        'http.method': 'POST',
        'http.url': '/api/v1/users/',
        'http.status_code': 201,
    }
}
```

### Production Integration (Future)

For production, export to a tracing backend:

```python
# app/core/telemetry.py
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Export to Jaeger/Tempo/Datadog
otlp_exporter = OTLPSpanExporter(
    endpoint="https://otel-collector.example.com:4317"
)
span_processor = BatchSpanProcessor(otlp_exporter)
```

Popular backends:

- **Jaeger** (open-source)
- **Grafana Tempo** (open-source)
- **Datadog APM** (commercial)
- **New Relic** (commercial)

---

## Best Practices

### Logging

✅ **Do:**

- Use keyword arguments for structured data
- Log business events (user_created, order_placed)
- Include relevant IDs (user_id, request_id)
- Use appropriate log levels

❌ **Don't:**

- Log sensitive data (passwords, tokens, PII without redaction)
- Use string formatting: `logger.info(f"User {user_id}")`
- Log in tight loops (aggregate instead)
- Log the same event multiple times

### Tracing

✅ **Do:**

- Add spans for expensive operations
- Include relevant attributes (IDs, amounts, flags)
- Use semantic naming: `validate_order` not `step_1`
- Propagate context across async boundaries

❌ **Don't:**

- Create spans for trivial operations (<1ms)
- Add excessive attributes (keep <10 per span)
- Ignore errors (always record exceptions)
- Block on span export

---

## Performance Impact

### Logging

- **Development**: Minimal (<1% overhead)
- **Production**: ~2-5% CPU overhead for JSON serialization

### Tracing

- **Disabled** (`QUOIN_OTEL_ENABLED=False`): Zero overhead
- **Enabled** (`QUOIN_OTEL_ENABLED=True`): ~5-10% overhead

> **TIP**: For high-throughput services, consider sampling (e.g., trace 10% of
> requests).

---

## Troubleshooting

### Logs Not Appearing

**Check:**

1. Is `setup_logging()` called? (Should be in `create_app()`)
2. Is `QUOIN_ENV` set correctly?
3. Are you using positional args instead of keyword args?

### Traces Not Captured

**Check:**

1. Is `QUOIN_OTEL_ENABLED=True`?
2. Is `setup_opentelemetry(app)` called after app creation?
3. Are SQLAlchemy/httpx installed? (Required for auto-instrumentation)

### Too Many Logs

**Solution**: Increase log level in production:

```python
# app/core/logging.py
root_logger.setLevel(logging.WARNING)  # Only warnings and errors
```

---

## See Also

- [Structlog Documentation](https://www.structlog.org/)
- [OpenTelemetry Python Docs](https://opentelemetry.io/docs/languages/python/)
- [app/core/logging.py](https://github.com/balakmran/quoin-api/blob/main/app/core/logging.py) — Logging configuration
- [app/core/telemetry.py](https://github.com/balakmran/quoin-api/blob/main/app/core/telemetry.py) — OTEL configuration
