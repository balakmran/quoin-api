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

The path from `v0.6.x` to `v1.0.0` runs through five releases. Each is
independently shippable and gated by `just check` plus the existing pre-push
hook. The ordering reflects a deliberate sequence: observability first (you
can't fix what you can't see), then security (procurement-grade), then API
contract (lock the public surface), then release engineering (ship safely),
then GA.

---

## v0.7.0 — Operability & Observability

The foundation that everything else logs and alerts against. Builds on the
existing OpenTelemetry setup and closes the gap between "the app runs" and
"the app is observable in production".

| Status | Feature |
| :----- | :------ |
| 📋 | **OTel Metrics** — Add `MeterProvider` alongside the existing `TracerProvider`; export via OTLP or Prometheus |
| 📋 | **`/metrics` endpoint** — Expose a Prometheus-compatible scrape endpoint in the `system` module |
| 📋 | **Request timeouts** — Per-request wall-clock timeout middleware using `anyio.fail_after()`; configurable via `QUOIN_REQUEST_TIMEOUT_SECONDS`; returns 504 RFC 9457 |
| 📋 | **Audit log** — Append-only `audit` table and service for who-did-what-when, distinct from app logs |
| 📋 | **SLOs + alert rules** — SLO doc plus checked-in alert rules YAML for latency, error rate, and saturation |

---

## v0.8.0 — Security & Production Hardening

The procurement gate plus the production-readiness gate. Brings the repo
to a state where a security review won't surface obvious gaps, a
dependency CVE won't ship unnoticed, and the service can talk to outside
systems and survive load without falling over.

| Status | Feature |
| :----- | :------ |
| 📋 | **Outbound HTTP client** — Shared `httpx.AsyncClient` lifecycle-managed in lifespan; retries with exponential backoff (`tenacity`); circuit breaker (`pybreaker`); OTel-instrumented |
| 📋 | **Request size caps** — Starlette middleware enforcing a configurable max request body size; returns 413 RFC 9457 |
| 📋 | **Rate limiting** — `slowapi` middleware with per-IP and per-token (JWT subject) limits; in-memory backend for dev, Redis for production |
| 📋 | **Idempotency keys** — `Idempotency-Key` header support for non-GET mutations; Redis-backed response cache with TTL; dedupes retries on POST/PUT/PATCH/DELETE |
| 📋 | **Graceful shutdown** — In-flight request drain on SIGTERM; in-app counter middleware + lifespan wait with `QUOIN_SHUTDOWN_DRAIN_TIMEOUT`; switch dev/prod runner from `fastapi` CLI to `uvicorn` for graceful shutdown control |
| 📋 | **Audit fields** — Add `last_login_at` to `User`; propagate actor identity into the audit log on every mutation |
| 📋 | **Supply chain scanning in CI** — `pip-audit`, Trivy (image), Semgrep (SAST), and gitleaks (secrets) on every PR |
| 📋 | **Security headers middleware** — HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy |
| 📋 | **CORS hardening** — Explicit allowlist, credentials policy, no wildcard in non-dev environments |
| 📋 | **Secrets manager adapter** — Pluggable env loader supporting Vault / AWS Secrets Manager / Doppler |
| 📋 | **PII classification + field-level encryption** — Helper for marking PII columns and encrypting at rest (Fernet or `pgcrypto`) |
| 📋 | **OWASP API Top-10 self-review** — Checklist + findings doc under `docs/security/` |

---

## v0.9.0 — API Contract Maturity

Locks the public surface before scale work. Anything we change after this
risks breaking downstream consumers, so the contract decisions land here.

| Status | Feature |
| :----- | :------ |
| 📋 | **Cursor-based pagination** — Supplement offset pagination with keyset/cursor pagination for large datasets |
| 📋 | **Soft delete** — Wire `User.is_active = False` semantics into `delete_user`; add `deleted_at` timestamp |
| 📋 | **Pagination/filter/sort envelope** — Standard list-response shape and query-parameter conventions across all modules |
| 📋 | **ETag / `If-Match`** — Optimistic concurrency control on update endpoints |
| 📋 | **Versioning + deprecation policy** — `Sunset` and `Deprecation` headers; documented policy beyond the `/api/v1` prefix |

---

## v0.10.0 — Release Engineering & DevEx

The "ship safely" release. Tooling for fast iteration, runbooks for the
human side of operating the service, and the migration playbook that keeps
schema changes from causing downtime.

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
| 📋 | **Zero-downtime migration playbook** — Expand/contract patterns documented; `migrate-gen` guard flags destructive operations for review |
| 📋 | **Backup + PITR runbook** — Documented procedure with a quarterly restore drill |

---

## v1.0.0 — Template Completeness & GA

The milestone that makes QuoinAPI a fully self-contained, production-ready
Copier template with opt-in feature flags and a stable public contract.

| Status | Feature |
| :----- | :------ |
| 📋 | **Copier feature flags** — `auth`, `rate_limit`, `sentry`, `metrics`, `feature_flags` as opt-in boolean variables in `copier.yml` |
| 📋 | **Sentry integration** — Optional error tracking via `sentry-sdk[fastapi]`; toggled by Copier flag |
| 📋 | **WebSocket support** — Basic WebSocket connection manager example with lifecycle integration |
| 📋 | **API stability + semver policy** — Public guarantee on what changes are breaking and how deprecations land |
| 📋 | **Published performance benchmarks** — Reproducible benchmark suite + headline numbers in the docs |
| 📋 | **Launch checklist** — Every preceding phase verified complete |

---

## Backlog (post-1.0)

Documented now so they aren't lost; revisited after `v1.0.0` ships and the
real-world demand for each is clearer.

| Status | Feature |
| :----- | :------ |
| 💡 | **ARQ background jobs** — Persistent async task queue for emails, webhooks, long-running work |
| 💡 | **Redis cache layer** — General-purpose response/data caching helpers on top of the existing Redis client used for rate limiting and idempotency |
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
