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
| ✅ | Completed (unreleased) |
| 🚧 | In Progress |
| 📋 | Planned |
| 💡 | Under Consideration |
| ❌ | Deferred / Won't Do |

The path from `v0.6.x` toward `v1.0.0` runs through the releases below. Each
is independently shippable and gated by `just check` plus the existing
pre-push hook. The ordering reflects a deliberate sequence: observability
first (you can't fix what you can't see), then security (procurement-grade),
then API contract (lock the public surface), then release engineering (ship
safely). All monitoring and observability follows OpenTelemetry and CNCF
standards — no vendor-specific tooling.

---

## v0.7.0 — Operability & Observability

The foundation that everything else logs and alerts against. Builds on the
existing OpenTelemetry setup and closes the gap between “the app runs” and
“the app is observable in production”. The migration playbook lands here so
every subsequent migration is written against the safety net from the start.

| Status | Feature |
| :----- | :------ |
| ✅ | **Request ID middleware** — Generate/propagate `X-Request-ID` and bind it to the structlog context per request |
| ✅ | **Trace/log correlation** — Inject `trace_id` and `span_id` from the active OTel span into every structlog event |
| 📋 | **OTel Metrics** — Add `MeterProvider` alongside the existing `TracerProvider`; export via OTLP or Prometheus |
| 📋 | **`/metrics` endpoint** — Expose a Prometheus-compatible scrape endpoint in the `system` module |
| ✅ | **Liveness vs readiness split** — `/health` (process up) and `/ready` (DB reachable via `ServiceUnavailableError`) already separated in the `system` module |
| ✅ | **`application/problem+json` errors** — RFC 9457 envelope wired into the global `QuoinError` handler |
| ✅ | **Request timeouts** — Per-request wall-clock timeout via `anyio.fail_after()`; configurable via `QUOIN_REQUEST_TIMEOUT_SECONDS`; returns 504 RFC 9457 `GatewayTimeoutError` |
| 📋 | **Zero-downtime migration playbook** — Expand/contract patterns documented; `migrate-gen` guard flags destructive operations for review |
| 📋 | **Audit log** — Append-only `audit` table and service for who-did-what-when, distinct from app logs |
| 📋 | **SLOs + alert rules** — SLO doc plus checked-in alert rules YAML for latency, error rate, and saturation |

---

## v0.8.0 — Security & Production Hardening

The procurement gate plus the production-readiness gate. Brings the repo
to a state where a security review won't surface obvious gaps, a
dependency CVE won't ship unnoticed, and the service can handle load and
outbound calls without falling over.

| Status | Feature |
| :----- | :------ |
| 📋 | **Supply chain scanning in CI** — `pip-audit`, Trivy (image), Semgrep (SAST), and gitleaks (secrets) on every PR |
| 📋 | **Security headers middleware** — HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy |
| 📋 | **CORS hardening** — Explicit allowlist, credentials policy, no wildcard in non-dev environments |
| 📋 | **Outbound HTTP client** — Shared `httpx.AsyncClient` lifecycle-managed in lifespan; retries with exponential backoff; circuit breaker; OTel-instrumented |
| 📋 | **Request size caps** — Starlette middleware enforcing a configurable max request body size; returns 413 RFC 9457 |
| 📋 | **Graceful shutdown** — In-flight request drain on SIGTERM; in-app counter middleware + lifespan wait with `QUOIN_SHUTDOWN_DRAIN_TIMEOUT` |
| 📋 | **Rate limiting** — `slowapi` middleware with per-IP and per-token (JWT subject) limits; in-memory backend for dev |
| 📋 | **Audit fields** — Add `last_login_at` to `User`; propagate actor identity into the audit log on every mutation |
| 📋 | **Secrets manager adapter** — Pluggable env loader supporting Vault / AWS Secrets Manager / Doppler |
| 📋 | **PII classification + field-level encryption** — Helper for marking PII columns and encrypting at rest (Fernet or `pgcrypto`) |
| 📋 | **OWASP API Top-10 self-review** — Checklist + findings doc under `docs/security/` |

---

## v0.9.0 — API Contract Maturity

Locks the public surface before scale work. Anything we change after this
risks breaking downstream consumers, so the contract decisions land here.
Versioning policy is set first to frame every other decision in the release.

| Status | Feature |
| :----- | :------ |
| 📋 | **Versioning + deprecation policy** — `Sunset` and `Deprecation` headers; documented policy beyond the `/api/v1` prefix |
| 📋 | **Pagination/filter/sort envelope** — Standard list-response shape and query-parameter conventions across all modules |
| 📋 | **Cursor-based pagination** — Supplement offset pagination with keyset/cursor pagination for large datasets |
| 📋 | **ETag / `If-Match`** — Optimistic concurrency control on update endpoints |
| 📋 | **Idempotency keys** — DB-backed idempotency-key store for non-GET mutations |
| 📋 | **Soft delete** — Wire `User.is_active = False` semantics into `delete_user`; add `deleted_at` timestamp |

---

## v0.10.0 — Release Engineering & DevEx

The “ship safely” release. Tooling for fast iteration, runbooks for the
human side of operating the service, and operational playbooks for day-two
concerns.

| Status | Feature |
| :----- | :------ |
| 📋 | **Test factories** — Integrate `polyfactory` for generating realistic test fixtures |
| 📋 | **Contract testing** — Add a `Schemathesis` smoke test against the live OpenAPI schema in CI |
| 📋 | **`just lint-fix`** — New recipe running `ruff check --fix` for auto-remediation |
| 📋 | **Auto-register routers** — `just new <module>` registers the router in `api.py` automatically |
| 📋 | **`just typecheck-strict`** — Escalate `ty` strictness level for teams that want zero-tolerance type checking |
| 📋 | **Feature flags** — DB-backed feature-flag module with a swappable interface (Unleash/GrowthBook compatible) |
| 📋 | **Blue/green or canary deploy workflow** — Sample workflow + doc for staged rollouts |
| 📋 | **Rollback runbook** — Tied to image tag; tested as part of the release ritual |
| 📋 | **Incident + post-mortem templates** — Markdown templates under `docs/runbooks/` |
| 📋 | **Backup + PITR runbook** — Documented procedure with a quarterly restore drill |

---

## v0.11.0 — Template Completeness

The milestone that makes QuoinAPI a fully self-contained, production-ready
Copier template with opt-in feature flags. Whether this becomes `v1.0.0`
will be decided once the preceding releases are shipped and the scope is
clear.

| Status | Feature |
| :----- | :------ |
| 📋 | **API stability + semver policy** — Public guarantee on what changes are breaking and how deprecations land |
| 📋 | **Published performance benchmarks** — Reproducible benchmark suite + headline numbers in the docs |
| 📋 | **WebSocket support** — Basic WebSocket connection manager example with lifecycle integration |
| 📋 | **Copier feature flags** — `auth`, `rate_limit`, `metrics`, `feature_flags` as opt-in boolean variables in `copier.yml` |
| 📋 | **Launch checklist** — Every preceding phase verified complete |

---

## Backlog (post-0.11)

Documented now so they aren't lost; revisited after `v0.11.0` ships and the
real-world demand for each is clearer.

| Status | Feature |
| :----- | :------ |
| 💡 | **Background task worker** — Persistent async task queue for emails, webhooks, and long-running work; evaluate Arq (asyncio-native) vs Dramatiq (broker-agnostic) |
| 💡 | **Redis cache layer** — Shared Redis client and caching helpers; replaces DB-backed idempotency store at scale |
| 💡 | **Multi-tenancy pattern** — Tenant-scoped query pattern with an example module |
| 💡 | **Organizations + memberships + scopes** — Richer authorization model beyond `require_roles` |
| 💡 | **API keys** — Hashed at rest, scoped, rotatable; for service-to-service callers |
| 💡 | **Connection pool tuning + read-replica routing** — Repository-layer routing of reads to replicas |
| 💡 | **Retention / erasure jobs** — GDPR Article 17 erasure on soft-deleted rows |
| ❌ | **mTLS for internal service-to-service** — Out of scope until QuoinAPI is multi-service |

---

## How to Contribute

1. Check if an issue already exists for the feature you want to work on.
2. Open a **Discussion** to align on approach before writing code.
3. Reference this roadmap item in your PR description.
4. Follow the [Contributing Guide](CONTRIBUTING.md) and ensure
   `just check` passes before requesting review.
