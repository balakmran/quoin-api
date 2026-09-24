---
name: api-docs-audit
description: Use when checking QuoinAPI's documentation against the code, in
  both directions — docs that no longer match the code, and code that no page
  documents. Not for fixing a broken docs build or syncing root docs into
  `docs/project/` (both are `just docb`), or writing the guide for a feature
  you just shipped (do that inline, per CLAUDE.md).
allowed-tools: Read, Edit, Grep, Glob, Bash, WebFetch
---

# Auditing QuoinAPI Docs Against the Code

Periodic sweep in **both directions**: docs that no longer match the code
(drift), and code that no page documents at all (coverage). It is
read-and-report first — propose fixes, then apply them in the same turn once
the user agrees.

## Scope

Audit everything under `docs/`, plus `README.md`, `CONTRIBUTING.md`, and
`SECURITY.md`. Skip `docs/project/*.md` — those are build artifacts synced by
`just docb` from the root files (`CHANGELOG.md`, `CONTRIBUTING.md`,
`ROADMAP.md`, `SECURITY.md`, `LICENSE`); fix the root source, not the synced
copy.

`docs/api/` and `docs/architecture/` matter as much as `docs/guides/`: the
reference is where an undocumented module hides, and the architecture overview
is where duplication accumulates.

## Direction 1 — docs → code (drift)

Start from what a page claims and check it against the code.

1. **Settings table vs `config.py`.** The settings table in
   `docs/guides/configuration.md` must list every `QUOIN_` setting in
   `app/core/config.py`, with matching names and defaults. Diff the two:
   - Settings in code but missing from the table → add them.
   - Settings in the table but gone from code → remove them.
   - Defaults that disagree → fix the doc.
   Also cross-check `.env.example` carries the same surface.

2. **Endpoint lists vs routers.** Where a guide enumerates routes, confirm they
   exist in `app/modules/*/routes.py` and `app/api.py`, all under `/api/v1/`.

3. **Commands vs `justfile`.** Any `just <recipe>` mentioned in docs must exist
   (`just --list`). Flag renamed/removed recipes.

4. **Version strings.** Sweep for stale versions — Python, key deps, GitHub
   Actions: `git grep -nE "3\.(12|13)"` and similar. Compare against
   `pyproject.toml` (`requires-python`) and the workflow files. (This overlaps
   with `api-deps-upgrade`'s sweep — reuse it.)

5. **Shields badges (`README.md` only).** The badge block lives in
   `README.md` and nowhere else — keep it that way. The FastAPI and SQLModel
   badges deliberately carry no version; flag any that regain one. The Python
   badge must match `requires-python` (the floor, which is lower than the
   container's Python — not a mismatch); the `PostgreSQL-<major>` badge must
   match `docker-compose.yml` (`postgres:18`).

   Prefer self-updating endpoint badges (CI/Docs status, Release, Ruff, uv,
   prek) over hardcoded version strings, which are the drift-prone kind.

6. **Referenced files/paths & README structure.** Backtick paths like
   `app/core/...`, `scripts/...`, `.claude/...` in docs should still resolve.
   A bare module reference (`app/core/exceptions`, no `.py`) and an example
   path (`app/modules/product/...`) are not broken — don't file them.

   Two trees claim to be the `app/` layout — the one under **What You Get** in
   `README.md` and the one in `docs/guides/getting-started.md`. Both list one
   line per directory and must name every directory that ships, `static/` and
   `templates/` included. The README has no table of contents by design, and
   its **Key Highlights** are deliberately link-free — don't flag either.

7. **Code samples that claim to run.** Spot-check that example snippets use
   current APIs (e.g. SQLModel/SQLAlchemy 2.x async, Pydantic v2). Use the
   `context7` MCP server to confirm current library syntax rather than guessing.

8. **Docs build.** Finish with `just docb` — an audit that breaks the build
   helps no one. It also catches a link to a heading that no longer exists.

## Direction 2 — code → docs (coverage)

Start from the code and check that something documents it. **Reading the docs
cannot find these**: an undocumented module is mentioned on no page, so nothing
prompts you to look for it.

`tests/test_docs_coverage.py` already enforces the mechanical half of this, so
`just check` fails on an undocumented core module, a feature module with no
reference page or nav entry, an orphaned page, and an exception or middleware
that no page names. Run the suite first; the commands below are for when you
want the findings without the traceback, or are auditing something the test
does not cover.

```bash
# Every app/core module, plus app/db/session.py and app/http/client.py, has
# a section in the Core reference. Sections are anchored by their
# `**Source:**` link, not by the heading, because a heading rarely matches
# the filename (config.py -> "Configuration").
for f in app/core/*.py app/db/session.py app/http/client.py; do
  [ "$(basename "$f")" = "__init__.py" ] && continue
  grep -q "\*\*Source:\*\* \[$f\]" docs/api/core.md || echo "undocumented: $f"
done

# Every feature module has a reference page and a nav entry.
for d in app/modules/*/; do
  m=$(basename "$d"); [ -f "$d/__init__.py" ] || continue
  [ -f "docs/api/$m.md" ] || echo "no reference page: docs/api/$m.md"
  grep -q "api/$m.md" zensical.toml || echo "not in nav: api/$m.md"
done

# Pages that exist but never made it into the nav.
for f in $(git ls-files 'docs/*.md' 'docs/**/*.md'); do
  case "$f" in docs/index.md|docs/project/*) continue;; esac
  grep -q "${f#docs/}" zensical.toml || echo "orphan page: $f"
done

# Every domain exception is in the hand-written error-handling table. The
# Core reference half needs no grep: `::: app.core.exceptions` renders every
# class, so a literal-name search of core.md reports all of them missing.
grep -oE "^class [A-Za-z]+\([A-Za-z]*Error\)" app/core/exceptions.py |
  sed -E 's/^class ([A-Za-z]+).*/\1/' | while read -r c; do
  grep -q "\b$c\b" docs/guides/error-handling.md || echo "missing from error-handling.md: $c"
done

# Every middleware class is described somewhere.
grep -oE "^class [A-Za-z]+Middleware" app/core/middlewares.py | awk '{print $2}' |
  while read -r c; do
  grep -rqs "$c" docs/guides docs/api || echo "undocumented middleware: $c"
done
```

Coverage items no grep will catch — check them by hand when the matching code
changed:

- **A new `just` recipe** belongs in the command tables in `CONTRIBUTING.md`
  and `docs/guides/getting-started.md`, not only in `just --list`.
- **A new skill, subagent, or hook** changes the counts asserted in three
  places: `README.md`, `docs/guides/ai-setup.md`, and `ROADMAP.md`. Compare
  against `ls .claude/skills | wc -l`, `ls .claude/agents | wc -l`, and the
  hook entries in `.claude/settings.json`.
- **A new middleware, or a change to the registration order**, belongs in the
  ordering list in `docs/guides/security.md` and the table in
  `docs/api/core.md`.

## Duplication between pages

Each page answers one question: `docs/api/` says *what a module provides*,
`docs/architecture/` says *how the layers fit together*, `docs/guides/` says
*how to do a task*. The same explanation in two of them will drift apart —
one gets updated, the other quietly rots. Keep it on the page whose question it
answers and link from the other.

The reference and the architecture overview collide most often:

```bash
# Names whose definition is shown in both the reference and architecture.
python3 - <<'PY'
import re, subprocess, collections
FENCE = chr(96) * 3  # built, not written: a literal fence would end this block
files = subprocess.check_output(
    ["git", "ls-files", "docs/api/*.md", "docs/architecture/*.md"], text=True
).split()
seen = collections.defaultdict(set)
for f in files:
    inc = False
    for line in open(f):
        s = line.strip()
        if s.startswith(FENCE):
            inc = not inc
            continue
        m = re.match(r"(?:async )?(?:def|class) ([A-Za-z_]\w*)", s) if inc else None
        if m:
            seen[m.group(1)].add(f)
for name, fs in sorted(seen.items()):
    if any(x.startswith("docs/api/") for x in fs) and any(
        x.startswith("docs/architecture/") for x in fs
    ):
        print(f"{name}: {', '.join(sorted(fs))}")
PY
```

A couple of hits are expected and fine — the decision log shows a `User` model
to illustrate why SQLModel was chosen, and the architecture overview shows
`create_user` in its concurrency section. A run that lists most of `app/core/`
means the architecture page has turned into a second reference.

## Output

Report findings grouped by file, each as: *what the doc says* → *what the code
says* → *proposed fix*. Then, once the user confirms, apply the edits and run
`just docb`. Don't silently rewrite docs — drift is sometimes the doc being
right and the code having regressed, which is worth surfacing, not papering
over.

## The reference is generated

`docs/api/core.md` and the Models/Schemas/Repository/Service sections of
`docs/api/user.md` are `::: app.core.<module>` blocks. The prose you see
on those pages is the module's **docstring** — fixing a wrong statement
there means editing the Python file, not the Markdown. Each section still
carries a hand-written `## Heading`, a `**Usage:**` link, and the
`**Source:**` link the coverage test matches on; those are the only parts
of the page to audit as Markdown.

Route sections stay hand-written — `docs/api/system.md` entirely, and
`user.md`'s Endpoints — because they document an HTTP contract, which no
docstring describes.

Two things to check on those pages:

- **A module with no module-level docstring** renders a section that
  opens straight into its first class; `ast.get_docstring(ast.parse(src))`
  finds any.
<!-- template-only -->

- **`QUOIN_` in a docstring.** Copier substitutes a longer prefix into
  generated projects, so a line with two prefix tokens can pass ruff here
  and break `ruff check` there. Keep it to one per line.
  `test_template_substitution.py` catches it.

<!-- /template-only -->

## Things that bite

- **Auditing in one direction only.** A check that starts from a doc can
  only find statements that are *wrong*; it cannot see a module no page
  mentions. Run Direction 2 as commands before reading a single page.
- **Skipping `docs/api/` and `docs/architecture/`.** That is where
  undocumented modules hide.
- **Forgetting this file is documentation too.** When a page it names by
  heading gets restructured, the check silently points at something that no
  longer exists. After restructuring a page this skill names, re-read the
  checks that mention it.
- **Editing `docs/project/*` directly.** Those are generated; your change will
  be overwritten on the next `just docb`. Edit the root source file.
- **Configuring a Markdown extension inline.** Options belong in their
  own `[project.markdown_extensions."<name>"]` table. Passing them as an
  inline table inside `[project.markdown] extensions` silently disables
  the extension — the build still says "No issues found".
- **Grepping built HTML to check a page rendered.** Syntax highlighting
  splits text across `<span>` tags, so a literal you search for may never
  appear contiguously even though it is on the page. Search for a string
  that can only come from the source you expect, and rebuild into a clean
  `site/` first.
- **Assuming a mismatch means the doc is wrong.** Sometimes the code drifted.
  Surface the discrepancy and let the user decide which side to fix.
- **Forgetting the settings table is the most drift-prone doc** — `config.py`
  changes land far more often than the table gets updated. Check it first.
- **Flagging `just` aliases as missing recipes.** A naive diff of `just <x>`
  mentions against `just --list` reports `docb`, `pi`, and `pr` as nonexistent
  — they are aliases (`docs-build`, `prek-install`, `prek-run`). Resolve
  aliases before reporting, or you'll file three false positives.
- **Reading defaults off a live `Settings()` instance.** The local `.env`
  overrides them, so a doc that is correct looks wrong (`OTEL_ENABLED` reads
  `False` in dev but is declared `True`). Compare against
  `Settings.model_fields[name].default`, not `getattr(settings, name)`.
