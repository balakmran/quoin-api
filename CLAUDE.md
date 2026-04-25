# CLAUDE.md

Guidance for Claude Code (and other agents via the `AGENTS.md` / `GEMINI.md` symlinks) working in this repo.

## Project

QuoinAPI (pronounced "koyn") — FastAPI + SQLModel + PostgreSQL backend. Doubles as a working API and a Copier template (`copier.yml`, `scripts/copier_setup.py.jinja`). Astral stack throughout: `uv`, `ruff`, `ty`.

## Architecture in one screen

- `app/main.py` — app factory; lifecycle, middleware, exception handlers
- `app/api.py` — router registration; everything user-facing under `/api/v1/`
- `app/core/` — infrastructure: `config`, `logging`, `security` (JWT + `require_roles`), `exceptions` (`QuoinError` base), `exception_handlers`, `middlewares`, `telemetry`
- `app/modules/<feature>/` — DDD modules; each has `models, schemas, repository, service, routes, exceptions, __init__`
- `tests/` — integration tests over a real DB; per-test SAVEPOINT rollback; fixtures in `tests/conftest.py`

Request flow: **route → `require_roles` → service → repository → SQLModel/asyncpg → Postgres**. Don't skip layers.

## Commands

`just` is the task runner; `.env` auto-loads. Run `just --list` for the full menu. The ones you'll reach for most:

- `just dev` — DB + OAuth + migrations + dev server
- `just db` — start Postgres only (required for tests)
- `just check` — format → lint → typecheck → test
- `just migrate-gen "<msg>"` / `just migrate-up` / `just migrate-down`
- `just new <module>` — scaffold a DDD module skeleton
- `just token` — mint a signed JWT against the local mock OAuth

Single test: `uv run pytest tests/modules/user/test_routes.py::test_create_user -v`.

## Universal conventions

These apply on every change. Workflow-specific rules live in skills and `docs/guides/`.

- **Run `just check` after every code change.** Format, lint, typecheck, and tests must all pass before you end a turn.
- **100% type hints.** Use blanket `# type: ignore` — never `# type: ignore[arg-type]` or other MyPy-style tags. The project uses `ty` (Pyright), which rejects unrecognized tag names.
- **FastAPI exception handlers** registered via `app.add_exception_handler` must type the `exc` parameter as `Any` (Pyright requirement).
- **80-char line limit** for Python and Markdown. Tables and code blocks are exempt.
- **Async-first** — every DB call, repository method, and service method is `async def`.
- **Google-style docstrings** on public functions and classes.
- **Never raise `HTTPException`** in service or repository code. Raise a domain exception (`NotFoundError`, `ConflictError`, `BadRequestError`, `ForbiddenError`, `InternalServerError` from `app/core/exceptions`) and let the global handler translate it.
- **Never modify the schema by hand.** Update the SQLModel, then `just migrate-gen "<msg>"`, review the generated script, then `just migrate-up`.
- **All endpoints under `/api/v1/`.** The prefix is applied centrally in `app/api.py`; declare module routers as `APIRouter(prefix="/<module>", ...)`.
- **No emojis or icons in `justfile` echo commands** (terminal compatibility). Use `@` to suppress command echoing.
- **Conventional Commits** — `<type>(<scope>): <description>`; types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`. Feature branches off `main`, merge via PR.

## Automated quality gates

This repo enforces quality at three points — assume they exist when reasoning about what's safe to ship:

- **End of every Claude turn** — a `Stop` hook in `.claude/settings.json` runs `just format && just lint && just typecheck` whenever the working tree is dirty. Failures block the turn until fixed. Tests are deliberately excluded here (too slow per turn).
- **`git commit`** — `prek` runs ruff format, ruff check, and `ty` on changed files (configured in `prek.toml`).
- **`git push`** — `prek` runs the full pytest suite. **Postgres must be running** (`just db`) or the push aborts. Use `git push --no-verify` only in emergencies; it defeats the gate.

`just setup` installs both commit and pre-push hooks for new clones.

## Configuration

All env vars use the `QUOIN_` prefix. See `.env.example` for the full list; `.env.test` overrides apply automatically during `just test`. `QUOIN_ENV` selects the profile (`development` | `test` | `production`).

Docker gotchas:
- Postgres persistence volumes must map to `/var/lib/postgresql` (not `/data`) for Postgres 18.
- The Dockerfile runs as non-root user `quoin`.

## Where to look for more

- **Workflows** (creating a module, migrations, testing patterns, auth, releases) — see the skills in `.claude/skills/` and the long-form guides in `docs/guides/`.
- **Reference module to mirror** — `app/modules/user/`.
- **Architecture decisions** — `docs/architecture/decision-log.md`.
