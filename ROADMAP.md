# Roadmap

This document outlines the planned evolution of QuoinAPI. It reflects the
current thinking of the maintainers and is subject to change based on community
feedback and shifting priorities.

!!! note
    This is a living document. Completed items are moved to
    [CHANGELOG.md](changelog.md).

## Where things stand

The template contract is locked. `0.9.0` shipped pagination, soft
delete, and deprecation; `0.10.0` the stability policy; `0.11.0` to
`0.13.0` the correctness fixes and the CI that proves a generated
project builds and updates; `0.14.0` the day-two proof. The 2026-09-13
full audit that followed found no High; `0.15.0` closed its request-path
findings and `0.16.0` its operational ones.

`1.0.0-rc.1` and `rc.2` rehearsed the release: the launch checklist ran
against each candidate, `rc.1` turned up six things, and `rc.2` carries
those six and nothing else. The checklist has served its purpose and is
retired — its per-release half now lives in the `api-release` skill,
which runs it on every tag rather than once. The Known Correctness
Issues table is empty.

**`0.10.0` was the last feature release before `1.0`.** Everything since
has been fixes and proof; from `1.0` a feature is an ordinary minor
release, and a break is a major or does not happen — see the
[API stability policy](docs/guides/api-stability.md).

The backlog lists only demand-gated features. Operational concerns
(alerting, deploy runbooks, backups) belong in your infrastructure repo.
Features better solved elsewhere — rate limiting, secrets managers, PII
encryption, feature flags, audit tables, retention jobs — were dropped;
ETag concurrency became a
[guide](docs/guides/optimistic-concurrency.md). Observability follows
OpenTelemetry, with no vendor-specific tooling.

---

## Known Correctness Issues

A confirmed bug is neither a milestone nor a backlog item (those are
demand-gated features) — without a lane of its own it tends to get
triaged as one or the other and lost. This table is that lane: add a
row when a review or an incident confirms a correctness bug that isn't
fixed in the same change, and remove the row once the fix ships
(credit it in `CHANGELOG.md` instead). Empty is the steady state, not
a gap in review.

| Issue | Found |
| :---- | :---- |

---

## Backlog

Documented now so they aren't lost. Promoted into a milestone only when
real demand surfaces — the bar is "a concrete user is blocked on this",
not "it would be nice to have".

| Feature | Why deferred |
| :------ | :----------- |
| **Idempotency keys (DB-backed store)** | Significant scope (replay logic, TTL semantics, key collision handling). Retry-safe idempotent verbs (`PUT`, `DELETE`) + client-supplied request IDs cover most cases. Build when actually needed. |
| **OTel Metrics + `/metrics` endpoint** | RED metrics can be derived from the existing OTLP trace stream in the OTel Collector. Direct Prometheus scrape is duplicate plumbing unless a deployer specifically needs it. |
| **Schemathesis contract testing in CI** | Pays off when external consumers lock against the schema. Adds CI minutes and flaky-test risk before that point. |
| **Cursor-based pagination** | Premature unless a module hits million-row tables. Offset pagination is sufficient through `1.0`. |
| **Background task worker** | Persistent async task queue for emails, webhooks, and long-running work; evaluate Arq (asyncio-native) vs Dramatiq (broker-agnostic). |
| **Redis cache layer** | Shared Redis client and caching helpers; replaces DB-backed idempotency store at scale. |
| **Multi-tenancy pattern** | Tenant-scoped query pattern with an example module. |
| **Organizations + memberships + scopes** | Richer authorization model beyond `require_roles`. |
| **API keys** | Hashed at rest, scoped, rotatable; for service-to-service callers. |
| **Read-replica routing** | Repository-layer routing of reads to replicas. Pool sizing itself is already tunable via `QUOIN_DB_POOL_*`. |

Of these, the most plausible promotions in rough order of likelihood
are: background worker, API keys, Redis cache, multi-tenancy. Nothing
currently blocks a known user on any of them, and none of the three
2026-09 analyses proposed anything for this table — every finding was
a defect, a hardening gap, or a proof gap, which is what a freeze is
supposed to produce.

---

## Direction

Intent, not commitments — where the template goes now that the surface
is frozen, as distinct from the backlog below, which is gated on
demand rather than on time.

- **Boring is the brand.** Strict semver, quarterly minors, security
  patches immediately. The cadence work is already dated: Python 3.12
  dropped at its end of life (October 2028), Postgres 19 in Compose and CI
  once it is generally available, and OpenTelemetry semantic-convention
  renames followed as they stabilise rather than pinned forever.
- **The update path is the differentiator.** The verify script, the
  two smoke jobs, the two-tag update check, and `staying-current.md`
  are the assets worth investing in; a template nobody can upgrade is
  a snapshot. The next guide worth writing is a worked outbound
  integration on `ResilientHTTPClient`, which today has no in-tree
  consumer other than the JWKS fetch.
- **Hostile-input tests are the next proof.** `0.15` showed that 100%
  branch coverage measured which lines ran, not which input classes
  reached them. A property-based or fault-injection layer over the
  request path (malformed tokens, dropped dependencies, forged
  headers) is the proof most worth adding once the surface is frozen.
- **The agentic workflow is a product feature.** Twelve skills, two
  subagents, and six hooks are more than any comparable template
  ships. Package them as a Claude Code plugin in `1.1`, once the
  template surface is frozen, so they can version independently of
  the code.
- **Backlog promotions stay demand-gated.** Most plausible, in order:
  background worker, API keys, Redis cache, multi-tenancy. Each lands
  as an ordinary minor, behind a flag or as an example module.
- **Never extract a `quoin-core` package.** The
  [API stability guide](docs/guides/api-stability.md) states this as a
  non-goal; a template you can read end to end is the point.

---

## How to Contribute

1. Check if an issue already exists for the feature you want to work on.
2. Open a **Discussion** to align on approach before writing code.
3. Reference this roadmap item in your PR description.
4. Follow the [Contributing Guide](contributing.md) and ensure
   `just check` passes before requesting review.
