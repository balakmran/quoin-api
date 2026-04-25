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

Walks through the full DDD module scaffold:
`just new <module>` → models → schemas → repository → service → routes →
exceptions → register router → generate and review migration → write tests
→ `just check`.

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

### `quoin-write-tests`

**Triggers on:** "write tests for", "add a test", "test this endpoint",
"I need coverage for"

Project fixture map (`client`, `read_client`, `admin_client`, `db_session`,
`caller_read`, `caller_admin`), SAVEPOINT isolation behaviour, adding
domain-specific callers for new modules, and common test anti-patterns to
avoid.

### `quoin-pre-pr`

**Triggers on:** "create a PR", "open a pull request", "I'm done with this
feature", "ready to merge", "ship this"

Two-step pre-PR checklist: update `CHANGELOG.md [Unreleased]` with a concise
entry for the work → run `just docb` to verify the docs build is clean →
then create the PR.

### `quoin-release`

**Triggers on:** "cut a release", "bump the version", "tag the release",
"prepare the changelog"

Five-step release ritual: curate `[Unreleased]` → `just bump part="..."` →
promote changelog heading → commit and merge to `main` → `just tag`. Covers
changelog section ordering, tag-from-main-only rule, and what to do if the
GitHub Actions release workflow fails.

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

### PreToolUse hook — block sensitive files (automatic)

Script at `.claude/hooks/block-sensitive.sh`. Fires before any
`Edit` / `Write` / `MultiEdit` tool call.

Refuses edits to:

| File pattern | Reason |
|---|---|
| `.env`, `.env.*` (except `.env.example`) | Credential leak risk |
| `uv.lock` | Must change via `uv add` / `uv remove` / `uv sync` |
| `alembic/versions/*.py` | Applied migrations must not be rewritten |

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

## MCP server — context7

Configured in `.mcp.json` (committed — the whole team gets it).

Fetches **live SDK documentation** at query time. Eliminates the "Claude
wrote SQLAlchemy 1.4 syntax" class of failure for libraries with breaking
API changes in Claude's training window.

Active for: FastAPI, SQLModel, SQLAlchemy 2.x async, Alembic, Pydantic v2,
OpenTelemetry, structlog.

No explicit invocation needed — Claude fetches docs automatically when
working with these libraries.

---

## Extending the setup

- **New skill:** create `.claude/skills/<name>/SKILL.md`. Follow the
  existing skills as a template. Trigger description is the most important
  part — be specific about what phrases should invoke it.
- **New hook:** add a script to `.claude/hooks/` and wire it in
  `.claude/settings.json`. Pipe-test before committing.
- **New plugin:** add to `enabledPlugins` in `.claude/settings.json`.
- **New MCP server:** add to `.mcp.json`. Commit so the team gets it.

For broader automation ideas, run the `claude-automation-recommender`
skill (say "recommend Claude automations for this project").
