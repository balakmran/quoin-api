# Roadmap

This document outlines the planned evolution of QuoinAPI. It reflects the
current thinking of the maintainers and is subject to change based on community
feedback and shifting priorities.

!!! note
    This is a living document. Completed items are moved to
    [CHANGELOG.md](CHANGELOG.md).
## Status Legend

| Symbol | Meaning |
| :----- | :------ |
| 🚧 | In Progress |
| 📋 | Planned |
| 💡 | Under Consideration |
| ❌ | Deferred / Won't Do |

---

## v0.7.0 — Observability Depth

Builds on the existing OpenTelemetry foundation to close gaps in
metrics and log correlation.

| Status | Feature |
| :----- | :------ |
| 📋 | **Request ID middleware** — Generate/propagate `X-Request-ID` header and bind it to the structlog context per request |
| 📋 | **Trace/log correlation** — Inject `trace_id` and `span_id` from the active OTel span into every structlog event |
| 📋 | **OTel Metrics** — Add `MeterProvider` alongside the existing `TracerProvider`; export via OTLP or Prometheus |
| 📋 | **`/metrics` endpoint** — Expose a Prometheus-compatible scrape endpoint in the system module |

---

## v0.8.0 — API Hardening

Quality-of-life improvements that bring the API surface closer to
real-world production patterns.

| Status | Feature |
| :----- | :------ |
| 📋 | **Rate limiting** — Integrate `slowapi` as middleware; configure per-route limits declaratively |
| 📋 | **Soft delete** — Wire `User.is_active = False` semantics into `delete_user`; add `deleted_at` timestamp |
| 📋 | **Cursor-based pagination** — Supplement offset pagination with keyset/cursor pagination for large datasets |
| 📋 | **Audit fields** — Add `last_login_at` to `User`; propagate actor identity into mutation logs |
| 💡 | **Background tasks** — Document `fastapi.BackgroundTasks` pattern; evaluate `ARQ` for persistent queues |

---

## v0.9.0 — Developer Experience

Tooling and scaffolding improvements that raise the floor for anyone
using QuoinAPI as a starting point.

| Status | Feature |
| :----- | :------ |
| 📋 | **Test factories** — Integrate `polyfactory` for generating realistic test fixtures |
| 📋 | **Contract testing** — Add a `Schemathesis` smoke test against the live OpenAPI schema in CI |
| 📋 | **`just lint-fix`** — New recipe running `ruff check --fix` for auto-remediation |
| 📋 | **Auto-register routers** — `just new <module>` registers the router in `api.py` automatically |
| 💡 | **`just typecheck-strict`** — Escalate `ty` strictness level for teams that want zero-tolerance type checking |

---

## v1.0.0 — Template Completeness

The milestone that makes QuoinAPI a fully self-contained, production-ready
Copier template with opt-in feature flags.

| Status | Feature |
| :----- | :------ |
| 📋 | **Copier feature flags** — `auth`, `rate_limit`, `sentry`, `metrics` as opt-in boolean variables in `copier.yml` |
| 💡 | **Sentry integration** — Optional error tracking via `sentry-sdk[fastapi]`; toggled by Copier flag |
| 💡 | **Multi-tenancy pattern** — Document and scaffold a tenant-scoped query pattern as an example module |
| 💡 | **WebSocket support** — Basic WebSocket connection manager example with lifecycle integration |

---

## How to Contribute

1. Check if an issue already exists for the feature you want to work on.
2. Open a **Discussion** to align on approach before writing code.
3. Reference this roadmap item in your PR description.
4. Follow the [Contributing Guide](CONTRIBUTING.md) and ensure
   `just check` passes before requesting review.
