# Quality Checks

One command, `just check`, is the gate for every change. It runs the
same steps locally, in git hooks, and in CI, so a green run here means a
green pull request.

## `just check`

| Step | Command | Fails when |
| :--- | :--- | :--- |
| Format | `just format` | Never; Ruff rewrites files in place |
| Lint | `just lint` | Ruff finds a violation (unused import, undefined name, ...) |
| Typecheck | `just typecheck` | `ty` finds a type error or a missing annotation |
| Migration check | `just migrate-check` | A model has drifted from what the migrations build |
| Test | `just test` | A test fails, or coverage drops below 100% |

`just check` starts Postgres if it isn't running.

The standards behind it: 100% type hints, 100% line and branch
coverage, and 80-column lines. The formatter wraps code at 80, but lint
(E501) only fails past 100. That slack is for generated projects, whose
longer settings prefix is substituted into docstrings and comments that
no formatter reflows.

## Git Hooks

`just setup` installs both hooks; `just pi` reinstalls them, and
`just pr` runs the commit hooks over every file.

| Hook | Runs | Why there |
| :--- | :--- | :--- |
| **pre-commit** | ruff format, ruff check, `ty` on changed files | Fast enough for every commit |
| **pre-push** | the full pytest suite | Too slow per commit; stops breakage before the remote |

!!! warning "The pre-push hook needs Postgres"
    Start it with `just db` or the push aborts; the hook doesn't start
    it for you. `git push --no-verify` skips the gate. Keep it for
    emergencies.

## CI Integration

GitHub Actions runs `just check` on every push, on the Python version in
`.python-version`. A second job, **Tests (Python 3.12)**, runs
`just test` on the `requires-python` floor, so both ends of the
supported range are tested. Pull requests can't merge until both pass.

<!-- template-only -->

A separate workflow runs the same gate somewhere else: **Scaffold Smoke Test**
([`scaffold-smoke.yml`](../../.github/workflows/scaffold-smoke.yml))
generates a project from the branch under review and runs *its* `just
check`, then fails if that gate modified the generated tree. `ci.yml`
proves this repo is healthy; only the smoke job proves the project an
adopter receives is.

The smoke job generates a single project: `--defaults` for every answer
except a long `project_name` ("Northwind Traders Platform API"). The
default name is short enough to fit every line it is substituted into,
so on its own it would hide lines that overflow once an adopter picks a
longer one. The long name derives a 30-character settings prefix, which
is what the lint headroom is sized for. Because that prefix also
differs from this repo's `QUOIN`, a missed substitution leaves the
generated project ignoring the CI database settings and the gate fails.

With default author answers the maintainer's identity is expected in
the generated tree, so the job only fails if the template's brand name
leaks.
The maintainer-identity scan, with long non-default author answers,
runs in `tests/test_template_substitution.py` as part of `just check`.

Then it rehearses day two inside the generated project: `just new
widget`, a one-table `Widget` model, `just migrate-up` (the gate's
tests leave the database at base), `just migrate-gen "add widget"`
(which must emit a `create_table`), and `just check` again. That proves
the scaffold and autogenerate where the settings prefix, base exception,
and problem URN are the adopter's, not this repo's.

<!-- /template-only -->

Dependency CVE scanning isn't part of `just check`: it needs the network,
and an advisory filed overnight would fail pull requests that changed
nothing. It runs weekly instead; see
[Dependency Scanning](dependency-scanning.md#uv-audit).

## Troubleshooting

### Type Errors

- A function can return `None`: add `| None` to its return type.
- A bare `list` or `dict`: add type parameters, such as `list[User]`.

### Coverage Below Threshold

`Required test coverage of 100.0% not reached` means a line or branch
went untested. The terminal report lists them under `Missing`, and
`just test` also writes `htmlcov/index.html`. Add tests; if a line truly
can't be covered, mark it `# pragma: no cover` with a reason.

## See Also

- [Testing](testing.md) — writing the tests this gate runs
- [AI-Assisted Development](ai-setup.md) — the Claude hooks that run
  the same checks
- [Contributing Guide](../project/contributing.md) — development
  workflow
