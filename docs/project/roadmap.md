# Roadmap

This document outlines the planned evolution of QuoinAPI. It reflects the
current thinking of the maintainers and is subject to change based on community
feedback and shifting priorities.

!!! note
    This is a living document. Completed items are moved to
    [CHANGELOG.md](changelog.md).

## Status Legend

| Symbol | Meaning |
| :----- | :------ |
| ✅ | Completed (unreleased) |
| 🚧 | In Progress |
| 📋 | Planned |
| 💡 | Under Consideration |
| ❌ | Deferred / Won't Do |

The public API contract is locked — the pagination envelope, soft
delete, and deprecation mechanism shipped in `0.9.0`, and the API
stability and semver policy is now published (see the
[CHANGELOG](changelog.md)). The one remaining milestone below carries
QuoinAPI to template completeness; it is independently shippable, gated
by `just check` plus the existing pre-push hook, and may become
`v1.0.0`.

The backlog below is deliberately narrow: it lists only demand-gated
*features* — application code we would ship behind a feature flag or as
an example module when a concrete user is blocked. Operational and
deployer-specific concerns (alert thresholds, deploy/rollback workflows,
backup runbooks) and rot-prone checklists were dropped outright rather
than parked — they belong in your infrastructure repo, not a backend
code template. All observability follows OpenTelemetry and CNCF
standards — no vendor-specific tooling.

---

## v0.10.0 — Template Completeness

The milestone that makes QuoinAPI a self-contained, production-ready
Copier template with opt-in feature flags and a stability guarantee.
Whether this becomes `v1.0.0` will be decided once the preceding
releases are shipped and the scope is clear.

| Status | Feature |
| :----- | :------ |
| ✅ | **API stability + semver policy** — Public guarantee on what changes are breaking and how deprecations land |
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
| 💡 | **OTel Metrics + `/metrics` endpoint** | RED metrics can be derived from the existing OTLP trace stream in the OTel Collector. Direct Prometheus scrape is duplicate plumbing unless a deployer specifically needs it. |
| 💡 | **Audit log table + actor propagation** | Structured logs already carry `request_id`, `trace_id`, caller subject, and path. A dedicated `audit` table is a compliance feature whose design depends on retention, immutability, and export needs that are business-specific. |
| 💡 | **Secrets manager adapter** | `pydantic-settings` already reads env vars. Vault/Doppler/ASM have battle-tested sidecars and init-containers that inject env at runtime; an in-app adapter duplicates that and couples the template to one abstraction. |
| 💡 | **PII classification + field-level encryption** | Huge design surface (key rotation, search-on-encrypted, KMS integration) that's deeply business-specific. Build when a real PII column needs it. |
| 💡 | **Schemathesis contract testing in CI** | Pays off when external consumers lock against the schema. Adds CI minutes and flaky-test risk before that point. |
| 💡 | **Cursor-based pagination** | Premature unless a module hits million-row tables. Offset pagination is sufficient through `1.0`. |
| 💡 | **Feature flags (Unleash/GrowthBook compatible)** | Large surface (DB-backed module + swappable interface) with no stated demand. |
| 💡 | **Background task worker** | Persistent async task queue for emails, webhooks, and long-running work; evaluate Arq (asyncio-native) vs Dramatiq (broker-agnostic). |
| 💡 | **Redis cache layer** | Shared Redis client and caching helpers; replaces DB-backed idempotency store at scale. |
| 💡 | **Multi-tenancy pattern** | Tenant-scoped query pattern with an example module. |
| 💡 | **Organizations + memberships + scopes** | Richer authorization model beyond `require_roles`. |
| 💡 | **API keys** | Hashed at rest, scoped, rotatable; for service-to-service callers. |
| 💡 | **Read-replica routing** | Repository-layer routing of reads to replicas. Pool sizing itself is already tunable via `QUOIN_DB_POOL_*`. |
| 💡 | **Retention / erasure jobs** | GDPR Article 17 erasure on soft-deleted rows. |

---

## How to Contribute

1. Check if an issue already exists for the feature you want to work on.
2. Open a **Discussion** to align on approach before writing code.
3. Reference this roadmap item in your PR description.
4. Follow the [Contributing Guide](contributing.md) and ensure
   `just check` passes before requesting review.
