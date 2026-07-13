# AI-Assisted Development

QuoinAPI ships with a first-class Claude Code setup. This guide covers
everything that was configured — skills, hooks, plugins, and MCP servers —
so you can take full advantage of it and extend it as the project evolves.

---

## Overview

The setup is layered: Claude Code reads conventions from `CLAUDE.md` on every
turn, loads on-demand workflow skills when they match your request, fires
hooks automatically to enforce quality and safety, and connects to live
documentation via an MCP server.

```
CLAUDE.md              ← always-on conventions (60 lines)
.claude/skills/        ← workflow skills, loaded when triggered
.claude/hooks/         ← enforcement scripts
.claude/settings.json  ← hook wiring + enabled plugins
.mcp.json              ← MCP server config (committed, team-wide)
prek.toml              ← git-level quality gates
```

---

## First-time setup

`just setup` handles everything:

```bash
just setup   # installs deps + prek commit hooks + prek pre-push hook
```

The pre-push hook runs the full pytest suite. **PostgreSQL must be running**
when you push (`just db`). Use `git push --no-verify` in emergencies only.

The Claude Code plugins, skills, and MCP server activate automatically the
first time you open the project in a Claude Code session. You will be prompted
to approve the `context7` MCP server on first use.

---

## Skills

Skills are packaged workflows that Claude invokes automatically when your
request matches, or that you can trigger explicitly with `/skill-name`.

All project skills live in `.claude/skills/`.

### `quoin-new-module`

**Triggers on:** "add a product module", "scaffold an orders feature",
"create a new resource for X"

Walks through the full DDD module scaffold: `just new <module>` →
models → schemas → repository → service → routes → exceptions → review
auto-registered router → generate and review migration → write tests →
`just check`.

### `quoin-add-endpoint`

**Triggers on:** "add an endpoint to the user module", "add a GET
/users/by-email route", "expose a search endpoint on products", "add a
deactivate action to users"

The single-endpoint counterpart to `quoin-new-module`: adds one route plus
its plumbing to a module that already exists, working up the layers
schema → repository → service → route against the `app/modules/user/`
reference. Covers the route-ordering gotcha (declare `/count` before
`/{user_id}`), the `response_model` vs return-type convention, reusing the
module's `get_<module>_service` dependency, and the required auth/domain-error
test cases. For a brand-new module use `quoin-new-module`; for a schema change
behind the endpoint use `quoin-db-migration` first.

### `quoin-db-migration`

**Triggers on:** "add a column", "add a field to", "make X nullable",
"change the type of", "add an index on"

Covers the schema-change loop with a built-in migration review checklist:
NOT NULL backfills, type narrowing risk, enum change gaps, downgrade
reversibility, and common autogenerate blind spots.

### `quoin-auth-route`

**Triggers on:** "protect this endpoint", "add RBAC", "require the X role",
"make this admin-only", "who is the caller"

DDD scope syntax (`domain.action`), `require_roles()` wiring, the auth
test triple (happy path / 403 / 401), and `api.superuser` bypass rules.

### `quoin-observability`

**Triggers on:** "add a log for this", "log this event", "add a span
around this", "why isn't this traced", "add context to the logs"

Structured logging (Structlog) and tracing (OpenTelemetry) conventions:
keyword-argument log fields, event-name style, `bind_contextvars` for
multi-line context, and when to add a custom span versus relying on
what's already auto-instrumented (request ID, access log, HTTP/DB spans,
log/trace correlation — none of which need code in a route or service).

### `quoin-write-tests`

**Triggers on:** "write tests for", "add a test", "test this endpoint",
"I need coverage for"

Project fixture map (`client`, `read_client`, `admin_client`, `db_session`,
`caller_read`, `caller_admin`), SAVEPOINT isolation behaviour, adding
domain-specific callers for new modules, and common test anti-patterns to
avoid.

### `quoin-coverage`

**Triggers on:** "make coverage 100%", "fill the coverage gaps", "cover the
missing lines", "get this to 100%", or pasting a `pytest --cov` report

The gap-closing counterpart to `quoin-write-tests`: read the `Missing` column,
classify each gap (error path / partial branch / dead code / defensive guard),
write targeted tests with the existing fixtures, and loop on `just test` until
the target is met. Prefers real tests over `# pragma: no cover`.

### `quoin-pre-pr`

**Triggers on:** "create a PR", "open a pull request", "I'm done with this
feature", "ready to merge", "ship this"

Three-step pre-PR checklist: run `just check` (format, lint, typecheck, tests
at 100% coverage) → update `CHANGELOG.md [Unreleased]` with a concise entry →
run `just docb` to verify the docs build and commit the synced files → create
the PR.

### `quoin-deps-upgrade`

**Triggers on:** "upgrade the dependencies", "update deps", "bump the GitHub
Actions", "upgrade to Python 3.x", "is there a newer version of X"

The version-upgrade ritual for both Python deps and GitHub Actions:
`uv lock --upgrade` respecting `exclude-newer`, checking upstream release notes
for pinning changes, sweeping docs/`.env`/Dockerfile/`copier.yml` for stale
version strings, and verifying with `just check`.

### `quoin-docs-audit`

**Triggers on:** "review the docs for accuracy", "check docs against the
code", "audit docs/ for stale info", "do the guides match the implementation"

A periodic docs↔code drift sweep over `docs/guides/` and `README.md`: settings
table vs `config.py`, endpoint lists vs routers, `just` recipes vs `justfile`,
stale version strings, and broken file references — finishing with `just docb`.
Reports findings before fixing, since a mismatch sometimes means the code
regressed, not the doc.

### `quoin-release`

**Triggers on:** "cut a release", "bump the version", "tag the release",
"prepare the changelog"

Five-step release ritual: curate `[Unreleased]` → `just bump part="..."` →
promote changelog heading → commit and merge to `main` → `just tag`. Covers
changelog section ordering, tag-from-main-only rule, and what to do if the
GitHub Actions release workflow fails.

### `quoin-hotfix`

**Triggers on:** "hotfix this", "emergency patch", "ship just this fix now",
"cut a hotfix release", "critical bug needs to go out now"

The `quoin-release` ritual cut down to one urgent fix: branch from `main`
(never from in-flight feature work), fix, `just check`, patch-bump only, and
a changelog entry that carries *only* the hotfixed change — unrelated
`[Unreleased]` entries wait for the next normal release. Runs on the
`haiku` model since it's a deterministic checklist, not a judgment call.

---

## Hooks

### Stop hook — quality gate (automatic)

Configured in `.claude/settings.json`. Fires at the end of every Claude turn
where the working tree is dirty.

Runs `just format && just lint && just typecheck`. If any step fails, the
turn is blocked and Claude sees the output — it must fix the issue before
responding. Turns with no code changes (Q&A, doc reads) are skipped.

Tests are deliberately excluded here — too slow per turn. Tests are gated
at push time instead (see below).

### Stop hook — config-drift warning (automatic)

Script at `.claude/hooks/config-drift.sh`. Also fires at the end of a dirty
turn. If `app/core/config.py` changed but neither `.env.example` nor
`docs/guides/configuration.md` did, it emits a **non-blocking** reminder to
keep the settings surface and its docs in sync. It never blocks the turn —
not every config edit adds or renames a setting — so treat it as advisory.

### Stop hook — migration reminder (automatic)

Script at `.claude/hooks/migration-reminder.sh`. Also fires at the end of a
dirty turn. If a `app/modules/*/models.py` changed but no new script was added
under `alembic/versions/`, it emits a **non-blocking** reminder to run
`just migrate-gen`. Like the config-drift hook it is advisory — some
`models.py` edits (a docstring, a non-mapped attribute) need no migration.

### Stop hook — `HTTPException` check (automatic)

Script at `.claude/hooks/http-exception-check.sh`. Also fires at the end of a
dirty turn. If a changed `app/modules/*/service.py` or `repository.py`
references `HTTPException`, it emits a **non-blocking** reminder that service
and repository code must raise a domain exception instead (the global
handler only translates domain exceptions). Advisory, not blocking — a hit
can be a false positive, e.g. a comment.

### PostToolUse hook — auto-format Python (automatic)

Configured in `.claude/settings.json`. Fires after any
`Edit` / `Write` / `MultiEdit` tool call.

When the edited file is a `.py` file, it runs `ruff format` on just that
file, so formatting stays clean mid-turn instead of accumulating drift until
the Stop hook runs at the end. It never blocks — it only reformats — and is a
no-op for non-Python files.

### PreToolUse hook — block sensitive files (automatic)

Script at `.claude/hooks/block-sensitive.sh`. Fires before any
`Edit` / `Write` / `MultiEdit` tool call.

Refuses edits to:

| File pattern | Reason |
|---|---|
| `.env`, `.env.*` (except `.env.example`) | Credential leak risk |
| `uv.lock` | Must change via `uv add` / `uv remove` / `uv sync` |
| `alembic/versions/*.py` | Applied migrations must not be rewritten |
| `copier.yml`, `copier.yaml` | Copier template config — edit deliberately |
| `*.jinja` | Copier template files — break consumers if changed |
| `docs/project/*.md` | Generated by `just docb` from a root file — edit the root, not the synced copy |

### prek git hooks (automatic on commit / push)

Configured in `prek.toml`, installed by `just setup`.

| Event | What runs |
|---|---|
| `git commit` | ruff format, ruff check --fix, ty check |
| `git push` | full pytest suite (requires Postgres running) |

---

## Plugins

Enabled in `.claude/settings.json`. Activate on session start.

### `commit-commands`

Provides a `commit` skill that structures git commits following the
project's Conventional Commits convention. Claude uses it automatically
when asked to commit.

### `pr-review-toolkit`

**Invoke:** `/review-pr` (or `/review-pr <aspect>` to target one lens)

Six specialized agents run in parallel against the current branch diff:

| Agent | Focuses on |
|---|---|
| `code-reviewer` | Project guidelines, CLAUDE.md conventions |
| `comment-analyzer` | Code comment quality |
| `pr-test-analyzer` | Test coverage gaps |
| `silent-failure-hunter` | Swallowed exceptions, bare `except`, missing error propagation |
| `type-design-analyzer` | Type correctness and design |
| `code-simplifier` | Clarity and maintainability |

The `silent-failure-hunter` is particularly relevant here: the project's
exception contract (always raise domain exceptions, never swallow errors)
is exactly what it checks.

### `security-guidance`

Automatic — no invocation needed. A `PreToolUse` hook that scans file
edits for security patterns (command injection, XSS, hardcoded secrets,
unsafe deserialization) and injects a contextual warning into Claude's
context when a risk is detected.

### `claude-md-management`

Two tools:

**`/revise-claude-md`** — run at the end of a productive session. Reviews
the conversation, extracts codebase learnings, and proposes targeted
updates to `CLAUDE.md`.

**`claude-md-improver` skill** — triggered by "audit CLAUDE.md",
"check project memory". Scans all `CLAUDE.md` files, scores quality, and
proposes improvements.

### `claude-code-setup`

Provides the `claude-automation-recommender` skill, which analyses the
codebase and suggests new Claude Code automations (hooks, skills, MCP
servers, plugins). Use it periodically or after adding a new major
dependency.

---

## Subagents

Project-local agents live in `.claude/agents/`. They run with their own
context and a restricted toolset, separate from the `pr-review-toolkit`
plugin agents above.

### `migration-reviewer`

**Invoke:** "review this migration", "is this migration safe", or run it after
`just migrate-gen` and before `just migrate-up`.

Audits the newest autogenerated Alembic script against the project's
schema-change checklist — autogen faithfulness, unrelated drift, NOT NULL
backfills, type narrowing, enum ops, `downgrade()` reversibility, and
server-vs-Python defaults — and returns an `APPROVE` / `CHANGES NEEDED` /
`DO NOT APPLY` verdict. It mirrors the `quoin-db-migration` skill's checklist
so the riskiest class of change gets a second pass before it lands.

### `rbac-route-auditor`

**Invoke:** "check auth coverage", "audit routes for missing
require_roles", "is every route protected", or run it right after adding or
editing routes.

Scans `app/modules/*/routes.py` for endpoints that are neither protected by
`require_roles(...)` nor deliberately public (a route in
`app/modules/system/` marked `include_in_schema=False`). This is the
single most-repeated warning across the `quoin-*` skills — a route without
`require_roles()` compiles, runs, and returns 200 to anyone, since auth in
this project is opt-in per route rather than default-deny. Reports findings
with the exact fix; does not edit files.

---

## MCP servers

Configured in `.mcp.json` (committed — the whole team gets them).

### context7

Fetches **live SDK documentation** at query time. Eliminates the "Claude
wrote SQLAlchemy 1.4 syntax" class of failure for libraries with breaking
API changes in Claude's training window.

Active for: FastAPI, SQLModel, SQLAlchemy 2.x async, Alembic, Pydantic v2,
OpenTelemetry, structlog. No explicit invocation needed — Claude fetches docs
automatically when working with these libraries.

### postgres (read-only)

Runs `@modelcontextprotocol/server-postgres` via `npx`, which executes every
query inside a `READ ONLY` transaction — so Claude can introspect the live
schema (tables, columns, indexes, constraints) before editing a model or
reviewing a migration, but cannot mutate data. Connects to the local **dev**
DB by default (`postgresql://postgres:postgres@localhost:5432/app_db`);
override with the `QUOIN_MCP_DATABASE_URI` environment variable. **Never point
it at production.** Requires the dev DB running (`just db`).

> Chosen over `crystaldba/postgres-mcp` (`uvx`) because that package's
> `pglast` dependency has no Python 3.14 wheel and fails to build in this
> repo's toolchain. The npx reference server is build-free and read-only.

---

## Extending the setup

- **New skill:** create `.claude/skills/<name>/SKILL.md`. Follow the
  existing skills as a template. Trigger description is the most important
  part — be specific about what phrases should invoke it.
- **New hook:** add a script to `.claude/hooks/` and wire it in
  `.claude/settings.json`. Pipe-test before committing.
- **New subagent:** create `.claude/agents/<name>.md` with a `description`
  (when to invoke) and a restricted `tools` list.
- **New plugin:** add to `enabledPlugins` in `.claude/settings.json`.
- **New MCP server:** add to `.mcp.json`. Commit so the team gets it.

For broader automation ideas, run the `claude-automation-recommender`
skill (say "recommend Claude automations for this project").
