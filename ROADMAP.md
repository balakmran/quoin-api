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

The path from `v0.7.0` toward template completeness runs through the
releases below. Each is independently shippable and gated by `just
check` plus the existing pre-push hook. The ordering: close the
security quick-wins, lock the public API contract, then ship the
template-completeness milestone (which may become `v1.0.0`).

This roadmap was trimmed in `v0.7.0` to remove features that are either
deployer-specific (alert rules, deploy workflows, backup runbooks),
duplicate existing infrastructure (OTel metrics on top of OTLP traces,
secrets-manager adapters on top of env vars), or too business-specific
to bake into a template (audit log, PII encryption). Those items live in
the [Backlog](#backlog) and will be revisited only if real demand
surfaces. All monitoring follows OpenTelemetry and CNCF standards — no
vendor-specific tooling.

---

## v0.8.0 — Production Hardening

The procurement-and-production-readiness gate. Absorbs the security
quick-wins, the runtime-hardening items that pair with the v0.7
timeouts, and the small DX cleanups that have been sitting unbuilt.
Sequenced by risk-reduction-per-day: the cheapest, highest-impact
security fixes land first.

| Status | Feature |
| :----- | :------ |
| 📋 | **CORS hardening** — Explicit allowlist, credentials policy, no `allow_methods=["*"]` / `allow_headers=["*"]` with credentials in non-dev environments (closes the wildcard footgun currently in `app/core/middlewares.py`) |
| 📋 | **Security headers middleware** — HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy |
| 📋 | **Request size caps** — Starlette middleware enforcing a configurable max request body size; returns 413 RFC 9457 |
| 📋 | **Graceful shutdown** — In-flight request drain on SIGTERM; in-app counter middleware + lifespan wait with `QUOIN_SHUTDOWN_DRAIN_TIMEOUT` |
| 📋 | **Outbound HTTP client** — Shared `httpx.AsyncClient` lifecycle-managed in lifespan; retries with exponential backoff; circuit breaker; OTel-instrumented. Foundational — every later integration sits on this. |
| 📋 | **Zero-downtime migration playbook** — Expand/contract patterns documented; `migrate-gen` guard flags destructive operations for review |
| 📋 | **Auto-register routers** — `just new <module>` registers the router in `api.py` automatically |
| 📋 | **Dependabot + secret scanning enabled** — `.github/dependabot.yml` + GitHub-native secret scanning (free for public OSS). `docs/security/scanning.md` notes how enterprises can layer Snyk/Black Duck/GHAS on top. |

---

## v0.9.0 — API Contract Maturity

Locks the public surface before the template-completeness milestone.
Anything we change after this risks breaking downstream consumers, so
the contract decisions land here. Versioning policy is set first to
frame every other decision in the release.

| Status | Feature |
| :----- | :------ |
| 📋 | **Versioning + deprecation policy** — `Sunset` and `Deprecation` headers; documented policy beyond the `/api/v1` prefix |
| 📋 | **Pagination/filter/sort envelope** — Standard list-response shape and query-parameter conventions across all modules |
| 📋 | **Soft delete** — Wire `User.is_active = False` semantics into `delete_user`; add `deleted_at` timestamp |

---

## v0.10.0 — Template Completeness

The milestone that makes QuoinAPI a self-contained, production-ready
Copier template with opt-in feature flags and a stability guarantee.
Whether this becomes `v1.0.0` will be decided once the preceding
releases are shipped and the scope is clear.

| Status | Feature |
| :----- | :------ |
| 📋 | **API stability + semver policy** — Public guarantee on what changes are breaking and how deprecations land |
| 📋 | **Copier feature flags** — `auth` as an opt-in boolean variable in `copier.yml` |
| 📋 | **Launch checklist** — Every preceding phase verified complete |

---

## Backlog

Documented now so they aren't lost. Promoted into a milestone only when
real demand surfaces — the bar is "a concrete user is blocked on this",
not "it would be nice to have".

| Status | Feature | Why deferred |
| :----- | :------ | :----------- |
| 💡 | **Supply chain scanning stack (pip-audit, Trivy, Semgrep, gitleaks)** | GitHub's free built-ins (Dependabot + secret scanning + optionally CodeQL) cover the same ground with zero CI overhead, and enterprise forks will swap the stack out for Snyk/Black Duck/GHAS anyway. Shipping a 4-tool default is opinion-as-debt. The `v0.8` Dependabot-only item is the floor. |
| 💡 | **Rate limiting (`slowapi`)** | In-memory backend is dev-only and shared-state in prod requires Redis (also backlog). Most production deployers rate-limit at the edge (NGINX, Cloudflare, API gateway, ALB); in-app rate limiting is niche enough to demand-gate. |
| 💡 | **ETag / `If-Match` optimistic concurrency** | Genuinely useful for some apps but most CRUD APIs don't need it. Pattern can be documented in `docs/guides/` without code in the template. |
| 💡 | **Idempotency keys (DB-backed store)** | Significant scope (replay logic, TTL semantics, key collision handling). Retry-safe idempotent verbs (`PUT`, `DELETE`) + client-supplied request IDs cover most cases. Build when actually needed. |
| 💡 | **`just typecheck-strict`** | `ty` already runs at default strictness in the `Stop` hook + `just check`. A second escalated mode adds maintenance without a stated consumer. |
| 💡 | **OWASP API Top-10 self-review doc** | Pure checklist; rots when OWASP publishes a new revision. Users will run their own review against their org's checklist. |
| 💡 | **OTel Metrics + `/metrics` endpoint** | RED metrics can be derived from the existing OTLP trace stream in the OTel Collector. Direct Prometheus scrape is duplicate plumbing unless a deployer specifically needs it. |
| 💡 | **Audit log table + actor propagation** | Structured logs already carry `request_id`, `trace_id`, caller subject, and path. A dedicated `audit` table is a compliance feature whose design depends on retention, immutability, and export needs that are business-specific. |
| 💡 | **SLOs + alert rules YAML** | Alert thresholds are deployer-specific; shipping defaults invites copy-paste of wrong values. |
| 💡 | **Secrets manager adapter** | `pydantic-settings` already reads env vars. Vault/Doppler/ASM have battle-tested sidecars and init-containers that inject env at runtime; an in-app adapter duplicates that and couples the template to one abstraction. |
| 💡 | **PII classification + field-level encryption** | Huge design surface (key rotation, search-on-encrypted, KMS integration) that's deeply business-specific. Build when a real PII column needs it. |
| 💡 | **Test factories (`polyfactory`)** | Current hand-rolled fixtures are explicit and work fine; polyfactory adds magic for marginal LOC savings. |
| 💡 | **Schemathesis contract testing in CI** | Pays off when external consumers lock against the schema. Adds CI minutes and flaky-test risk before that point. |
| 💡 | **Cursor-based pagination** | Premature unless a module hits million-row tables. Offset pagination is sufficient through `1.0`. |
| 💡 | **Published performance benchmarks** | Marketing more than function. |
| 💡 | **Incident + post-mortem templates** | Pure markdown; every org has its own (Notion/Linear/Jira/Docs). Doesn't belong in a backend code repo. |
| 💡 | **Backup + PITR runbook + restore drill** | Always handled by the managed-DB provider (RDS, Cloud SQL, Aurora, Neon, Supabase). Generic-in-repo guidance will be either useless or wrong. |
| 💡 | **Blue/green or canary deploy workflow** | Deployer-specific (k8s? ECS? Fly? Render?). Belongs in the operator's infra repo. |
| 💡 | **Rollback runbook** | Same — tied to the deploy target. |
| 💡 | **Feature flags (Unleash/GrowthBook compatible)** | Large surface (DB-backed module + swappable interface) with no stated demand. |
| 💡 | **WebSocket support** | Off-thesis for a procurement-grade request/response backend template. |
| 💡 | **Background task worker** | Persistent async task queue for emails, webhooks, and long-running work; evaluate Arq (asyncio-native) vs Dramatiq (broker-agnostic). |
| 💡 | **Redis cache layer** | Shared Redis client and caching helpers; replaces DB-backed idempotency store at scale. |
| 💡 | **Multi-tenancy pattern** | Tenant-scoped query pattern with an example module. |
| 💡 | **Organizations + memberships + scopes** | Richer authorization model beyond `require_roles`. |
| 💡 | **API keys** | Hashed at rest, scoped, rotatable; for service-to-service callers. |
| 💡 | **Connection pool tuning + read-replica routing** | Repository-layer routing of reads to replicas. |
| 💡 | **Retention / erasure jobs** | GDPR Article 17 erasure on soft-deleted rows. |
| ❌ | **mTLS for internal service-to-service** | Out of scope until QuoinAPI is multi-service. |

---

## How to Contribute

1. Check if an issue already exists for the feature you want to work on.
2. Open a **Discussion** to align on approach before writing code.
3. Reference this roadmap item in your PR description.
4. Follow the [Contributing Guide](CONTRIBUTING.md) and ensure
   `just check` passes before requesting review.
