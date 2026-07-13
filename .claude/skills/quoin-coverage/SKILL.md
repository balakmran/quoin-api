---
name: quoin-coverage
description: Use this skill whenever the user wants to raise or close test
  coverage on existing QuoinAPI code — driving a module to 100%, filling the
  gaps in a coverage report, or covering specific missing lines/branches.
  Triggers include "make coverage 100%", "get this to 100%", "fill the
  coverage gaps", "cover the missing lines", "improve coverage", "why is this
  line uncovered", or pasting a `pytest --cov` / coverage table with a
  `Missing` column. Do NOT use for scaffolding a brand-new module's test suite
  from scratch (that is `quoin-write-tests`) or for configuring pytest itself.
allowed-tools: Read, Edit, Write, Bash, Grep, Glob
---

# Closing Coverage Gaps in QuoinAPI

This is the *gap-closing loop*: you have a coverage report and need to drive
the number up, usually to 100%. For the fixture toolkit, the test-file
anatomy, and the auth-triple pattern, this skill builds on
[quoin-write-tests](../quoin-write-tests/SKILL.md) — read that for the
mechanics; this skill is about the loop and the judgement calls.

## Prerequisites

Postgres must be running. `just test` now auto-starts it (via `_db-check`), so
just run the suite — no separate `just db` step needed.

## The loop

### 1. Get a fresh report

```bash
just test
```

The terminal report uses `--cov-report=term:skip-covered`, so only files with
gaps appear. Read the `Missing` column — it lists uncovered statement lines
and `partial` branches (e.g. `42->44`, meaning the `42→44` edge never fired).

### 2. Classify each gap before writing anything

Map each `Missing` range back to the source line in `app/...` and decide what
kind of gap it is:

| Gap | Action |
|---|---|
| Unhit **error path** (a `raise NotFoundError`, a `409` branch) | Write a test that triggers it — usually the missing leg of the auth/4xx triple |
| Unhit **branch** (`BrPart` / `a->b` partial) | Add a case for the *other* side of the conditional; one input rarely covers both |
| **Dead / unreachable** code | Don't test it — flag it to the user for removal; tests should not prop up dead code |
| Genuinely **defensive / unreachable** guard (belt-and-suspenders that can't fire) | Candidate for `# pragma: no cover` — but see below |

### 3. Write the targeted tests

Use the existing fixtures (`client`, `read_client`, `admin_client`,
`db_session`) and patterns from `quoin-write-tests`. Most coverage gaps in this
codebase are a missing leg of the route triple (401 / 403 / 404 / 409 / 422) or
a service-layer domain-exception path. Seed via `db_session` when the missing
branch needs state the route can't set up directly.

### 4. Re-run and repeat

Run `just test` again, re-read `Missing`, and keep going until the target is
met. Coverage is monotonic here — each test should shrink the column.

## Prefer real exercise over pragmas

Reach for a test, not `# pragma: no cover`. Only mark a line `no cover` when it
is *genuinely unreachable* (e.g. a defensive `else` that a type invariant
forbids), and when you do, **say so explicitly to the user** with the reason —
don't silently paper over a gap that a real test could close.

## Things that bite

- **Branch coverage needs both sides.** A line can be 100% statement-covered
  but show as a partial branch (`BrPart`) until *both* outcomes of its
  conditional are exercised. Add the missing input, don't just re-assert the
  happy path.
- **`async def` paths need `@pytest.mark.asyncio`.** Without it the test is
  collected but never awaited — coverage won't move and nothing actually ran.
- **Mocking the DB hides the gap.** The SAVEPOINT fixture is what production
  uses; mocking `AsyncSession` makes a line look covered while the real path
  stays untested. Use the fixtures.
- **Chasing 100% on dead code.** If a branch can't be reached by any valid
  input, the fix is deletion, not a contrived test.
