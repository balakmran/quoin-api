# AI-Assisted Development

QuoinAPI ships a Claude Code setup that holds an assistant to the same
gate you work under: 12 skills, 2 subagents, 6 hooks, 5 plugins, and 2
MCP servers. It activates the first time you open the project in Claude
Code; approve the `context7` MCP server when prompted.

```
CLAUDE.md              ← always-on conventions
.claude/skills/        ← workflow skills, loaded when a request matches
.claude/agents/        ← project subagents, own context and toolset
.claude/hooks/         ← enforcement scripts
.claude/settings.json  ← hook wiring + enabled plugins
.mcp.json              ← MCP server config (committed, team-wide)
prek.toml              ← git-level quality gates
```

`just setup` installs the git hooks. The pre-push hook runs the full
test suite, so Postgres must be up (`just db`) when you push.

## Skills

Claude loads a skill when your request matches its trigger, or you call
it with `/<skill-name>`. Each lives in `.claude/skills/<name>/SKILL.md`;
the `api-` prefix keeps them from colliding with your own skills.

| Skill | Use it to |
| :--- | :--- |
| `api-new-module` | Scaffold a new module end to end: `just new`, every layer, migration, tests |
| `api-add-endpoint` | Add one route to an existing module, working up schema → repository → service → route |
| `api-db-migration` | Change a column, index, or table, with a migration review checklist |
| `api-auth-route` | Add or change `require_roles()` on a route, plus the 200/403/401 test triple |
| `api-observability` | Add logs or spans, and know what is already instrumented |
| `api-write-tests` | Write route, service, or repository tests with the project fixtures |
| `api-coverage` | Close gaps in a coverage report with real tests, not pragmas |
| `api-pre-pr` | Run `just check`, update the changelog, run `just docb`, then open the PR |
| `api-deps-upgrade` | Upgrade Python packages, Python itself, the Astral tools, or pinned Actions |
| `api-docs-audit` | Find docs that disagree with the code, and code no page documents |
| `api-release` | Cut a release: curate the changelog, `just bump`, `just tag` |
| `api-hotfix` | Ship one urgent fix as a patch release, branched from `main` |

## Hooks

| Hook | When | What it does |
| :--- | :--- | :--- |
| Quality gate | End of a turn with a dirty tree | Runs `just format && just lint && just typecheck`; a failure blocks the turn. Tests wait for push |
| Config drift | End of a dirty turn | Warns when `app/core/config.py` changed but `.env.example` and `docs/guides/configuration.md` didn't |
| Migration reminder | End of a dirty turn | Warns when a `models.py` changed but no migration was added |
| `HTTPException` check | End of a dirty turn | Warns when a changed `service.py` or `repository.py` mentions `HTTPException` |
| Auto-format | After each edit | Runs `ruff format` on the edited `.py` file |
| Sensitive-file guard | Before each edit or write-like `Bash` command | Refuses the files below |

The three warnings never block, since a hit can be a false positive.

The guard refuses:

| File | Why |
| :--- | :--- |
| `.env`, `.env.*` (except `.env.example`, `.env.test`) | Credential leak risk |
| `uv.lock` | Changes through `uv add` / `uv remove` / `uv lock` |
| `alembic/versions/*.py` | Applied migrations must not be rewritten |
| `docs/project/*.md` | Synced by `just docb`; edit the root file |

It matches `Bash` command text, so a command that only names one of
these paths next to a redirect or interpreter is refused too. Reword the
command rather than working around it.

Outside Claude, `prek` runs ruff and `ty` on `git commit`, and the full
test suite on `git push`.

## Plugins

Enabled in `.claude/settings.json`:

- **`commit-commands`** — Conventional Commits for the `commit` skill.
- **`pr-review-toolkit`** — `/review-pr` runs six reviewers in parallel:
  code, comments, tests, silent failures, type design, and
  simplification. The silent-failure reviewer checks exactly the
  "raise a domain exception, never swallow" rule.
- **`security-guidance`** — warns during edits that look like injection,
  XSS, hard-coded secrets, or unsafe deserialization.
- **`claude-md-management`** — `/revise-claude-md` turns a session's
  learnings into `CLAUDE.md` updates.
- **`claude-code-setup`** — suggests new hooks, skills, and MCP servers
  for the codebase.

## Subagents

Project agents in `.claude/agents/` run with their own context and a
restricted toolset. Neither edits files.

- **`migration-reviewer`** — checks the newest Alembic script against
  the schema-change checklist and returns `APPROVE`, `CHANGES NEEDED`,
  or `DO NOT APPLY`. Run it between `just migrate-gen` and
  `just migrate-up`.
- **`rbac-route-auditor`** — finds routes with neither
  `require_roles()` nor a deliberate public marking. Auth is opt-in per
  route, so a missing check returns 200 to anyone.

## MCP servers

Configured in `.mcp.json`, so the whole team gets them.

- **context7** — fetches current docs for FastAPI, SQLModel, SQLAlchemy,
  Alembic, Pydantic, OpenTelemetry, and structlog, so generated code
  matches today's APIs.
- **postgres** — read-only access to the local dev database, for
  inspecting the live schema before a model change. It defaults to
  `postgresql://postgres:postgres@localhost:5432/app_db`; override with
  `QUOIN_MCP_DATABASE_URI`. Needs `just db`. **Never point it at
  production.**

## Extending the setup

- **Skill** — add `.claude/skills/api-<name>/SKILL.md`. The trigger
  description matters most: name the phrases that should invoke it.
- **Hook** — add a script to `.claude/hooks/` and wire it in
  `.claude/settings.json`.
- **Subagent** — add `.claude/agents/<name>.md` with a `description` and
  a restricted `tools` list.
- **Plugin or MCP server** — add it to `enabledPlugins` or `.mcp.json`
  and commit.

## See Also

- [Quality Checks](quality-checks.md) — the gate the hooks enforce
- [Creating a Module](creating-a-module.md) — the conventions the
  skills encode
- [Contributing](../project/contributing.md) — working on the template
  itself
