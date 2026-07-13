---
name: quoin-observability
description: Use this skill whenever the user wants to add or change logging,
  metrics, or tracing in QuoinAPI — adding a structured log line, binding
  request context, adding a custom OpenTelemetry span, or reasoning about
  what's already auto-instrumented. Triggers include "add a log for this",
  "log this event", "add a span around this", "why isn't this traced", "add
  context to the logs", "how do I correlate logs and traces", or any request
  that touches `structlog`/`opentelemetry` usage in `app/modules/*` or
  `app/core/`. Do NOT use for changing the logging/tracing *configuration*
  itself (`app/core/logging.py`, `app/core/telemetry.py`) — that's a
  core-infra change, not a per-feature one — or for outbound HTTP resilience
  (retries, circuit breaking), which is `docs/guides/outbound-http.md`.
allowed-tools: Read, Edit, Grep, Glob, Bash
---

# Logging and Tracing in QuoinAPI

QuoinAPI's observability stack is **structlog** (structured logging) plus
**OpenTelemetry** (distributed tracing), both already wired up in
`app/core/logging.py` and `app/core/telemetry.py` — you're adding to an
existing stack, not building one. The long-form reference is
[docs/guides/observability.md](../../../docs/guides/observability.md); this
skill is the in-the-moment cheat sheet.

## What's already automatic — don't re-implement it

Before adding anything, check whether it's already covered:

- **Request ID**: every request gets one, bound to the log context by
  `RequestIDMiddleware`. No code needed in routes or services.
- **Access log**: `AccessLogMiddleware` emits one `http_request` line per
  request (method, path, status, duration_ms) automatically.
- **HTTP/DB spans**: FastAPI routes, SQLAlchemy/asyncpg queries, and outbound
  `httpx` calls are auto-instrumented by `setup_opentelemetry()`. You do not
  need to wrap a repository query or an `HTTPClientDep` call in a manual
  span — it already produces one.
- **Log/trace correlation**: every log line emitted during a traced request
  automatically carries `trace_id` and `span_id`. No code needed.

What you add by hand is **business-event logs** and **custom spans around
business logic** — the two things auto-instrumentation can't infer.

## Adding a log line

```python
import structlog

logger = structlog.get_logger()

class UserService:
    async def create_user(self, user_create: UserCreate) -> User:
        user = await self.repository.create(user_create)
        logger.info("user_created", user_id=str(user.id), email=user.email)
        return user
```

- **Always keyword arguments.** `logger.info(f"User {user_id}")` breaks
  structured search — never use string formatting.
- **Event names are `snake_case` verbs in past tense**: `user_created`,
  `payment_failed`, not `UserCreated` or `creating user`.
- **Pick the level deliberately**: `info` for business events worth
  searching later, `warning` for unexpected-but-recoverable, `error`/
  `exception` for failures needing attention, `debug` for diagnostics you'd
  strip in production. See the level table in the full guide.
- **Never log secrets** — passwords, tokens, unredacted PII.

## Binding context across multiple log lines

```python
from structlog.contextvars import bind_contextvars, clear_contextvars

async def process_order(order_id: str) -> None:
    bind_contextvars(order_id=order_id, user_id=current_user.id)
    logger.info("order_processing_started")
    ...
    logger.info("order_processing_finished")
    clear_contextvars()
```

Every log statement between `bind_contextvars` and `clear_contextvars`
picks up the bound fields automatically — don't repeat them on every call.

## Adding a custom span

Only for genuinely expensive or business-significant operations — not
trivial (<1ms) work, and not anything already auto-instrumented (DB
queries, outbound HTTP):

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

class OrderService:
    async def process_order(self, order_id: str) -> None:
        with tracer.start_as_current_span("validate_order") as span:
            span.set_attribute("order.id", order_id)
            result = await self._validate(order_id)
            span.set_attribute("validation.success", result)
```

- **Semantic names**: `validate_order`, not `step_1`.
- **Keep attributes under ~10 per span**; use dotted names (`order.id`,
  `user.tier`).
- Spans are a no-op when `QUOIN_OTEL_ENABLED=False` — don't gate your own
  code on that setting, the SDK already does.

## Things that bite

- **Positional log arguments.** `logger.info("user created: %s", user_id)`
  isn't structured — always pass fields as keyword arguments.
- **Manually wrapping DB or outbound HTTP calls in spans.** They're already
  instrumented; a manual span here just duplicates the trace with a
  confusing extra layer.
- **Forgetting `clear_contextvars()`** after `bind_contextvars()` in a
  long-lived scope (e.g. a background task) — bound fields leak into
  unrelated log lines for the rest of that context.
- **Logging in a tight loop.** Aggregate into one summary log line instead
  of one line per iteration.
- **Changing `app/core/logging.py` or `app/core/telemetry.py` for a
  feature-specific need.** Those are shared configuration; a per-feature
  need almost always belongs in the module's own logger calls or spans, not
  a change to how logging/tracing is set up globally.
