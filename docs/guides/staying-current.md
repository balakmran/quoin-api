# Staying Current

How a project generated from this template takes a later template
release.

This is the adopter's side of the [API Stability &
SemVer](api-stability.md) policy. That guide says *what* counts as
breaking; this one says what to do about it on a Tuesday afternoon,
with ten modules of your own in the tree.

---

## What `copier update` actually does

When you generated your project, Copier wrote
`.copier-answers.yml` recording every answer you gave and — the
important part — a `_commit` field naming the template tag you
generated from.

An update is a three-way merge, not an overwrite. Copier:

1. Regenerates the project as it *would have been* at your recorded
   `_commit`, using your saved answers.
2. Regenerates it again at the new tag.
3. Applies the difference between those two to your working tree.

The consequence worth internalising: **Copier diffs the template
against itself, then replays that diff onto your code.** Files you
never touched update silently. Files you edited get a merge. Files
you added are invisible to the process and are never at risk.

!!! warning "It reads your git history, so commit first"

    The merge needs a clean tree to work against. Commit or stash
    everything before starting; an update applied over uncommitted work
    leaves you unable to tell your changes from the template's.

---

## The update

```bash
git checkout -b chore/template-update
uvx copier update --trust --conflict rej
just install
just check
```

Three of those deserve a note.

`--trust` is required because the template runs a post-generation
script. It is the same flag you used to generate, and you should read
what it runs — `scripts/copier_setup.py.jinja` in the template repository —
before granting it.

`--conflict rej` is worth preferring over Copier's default. The
default (`inline`) writes conflict markers into your source files,
which makes a conflicted merge look superficially like a normal one.
`rej` leaves the file alone and drops a `.rej` file beside it, so
`find . -name '*.rej'` gives you an exact, greppable list of everything
that needs a human. The template's own CI uses `rej` for this reason.

`just check` at the end is not optional. It is the only thing that
tells you whether the merged result actually works, and it is the same
gate the template's CI runs against a freshly updated project.

To update to a specific release rather than the newest:

```bash
uvx copier update --trust --conflict rej --vcs-ref v1.2.0
```

---

## Reading the changelog first

Every release classifies its changes. Read `CHANGELOG.md` for each
version between yours and your target **before** running the update —
the entries tell you where to expect work.

| What you see | What it means for you |
| :--- | :--- |
| Nothing said | Update-safe. It merges, or it touches files you never edited. |
| **Manual reconciliation** | A template-owned file you have likely edited or copied a pattern from. The entry names the change; you apply it to your own code. |
| A new `<PREFIX>_` setting | Additive with a preserving default. Adopt it when you need it. |
| A renamed or removed setting | Breaking. Set the new name before deploying, not after. |

A **manual reconciliation** note is not a warning that the update will
fail. Usually it merges fine and is still wrong afterwards, because
the pattern it changed also lives in code Copier does not manage — your
modules. That is the whole reason the label exists.

### A worked example

From the template's own history — release `0.11.0`, whose entries you
will find in the template repository rather than your project's
changelog. Four of them carried the label, and only one was something
`copier update` could do for you:

- **`SessionDep`** — the session dependency changed scope so the
  transaction commits *before* the response is sent. Copier updates
  `app/db/session.py` and the `user` module. It cannot update
  `app/modules/yours/routes.py`, where you wrote
  `Depends(get_session)` by hand. Every one of those needs to become
  `SessionDep` or it keeps the old, wrong behaviour.
- **`validate_production_oauth()` → `validate_production_settings()`**
  — a rename. Fine unless you import it, which the update cannot see.
- **`QUOIN_ALLOWED_HOSTS` now required in production** — a deployment
  change, not a code one. Nothing in your repository will tell you it
  is missing; the app will refuse to boot.
- **100% coverage enforcement** — `fail_under = 100` arrives in
  `pyproject.toml` and your suite is now measured against it. Either
  add the missing tests or lower the number, deliberately.

The shape generalises: **the update handles the template's copy of a
pattern, and leaves every copy you made of it.** Grep for the old form
after any reconciliation entry.

---

## When it conflicts

A `.rej` file means Copier could not apply a hunk. It is a normal diff:

```bash
find . -name '*.rej'
cat app/core/config.py.rej
```

Apply it by hand, delete the `.rej`, and move on. Three situations
account for almost all of them:

- **You edited a template-owned file.** Expected, and the reason the
  label exists. Re-apply your edit on top of the new version rather
  than the reverse — the template's version has moved for a reason.
- **You deleted something the template still ships.** Copier tries to
  patch a file that is not there. If the deletion was deliberate,
  discard the hunk.
- **You are several releases behind.** Conflicts compound. Update one
  tag at a time (`--vcs-ref` each release in order) rather than
  crossing three releases in a jump; each step is smaller and the
  changelog for each step is the one you just read.

!!! tip "Never resolve a conflict you don't understand"

    `git checkout --theirs` on a file you have customised silently
    discards your work, and `--ours` silently discards a security fix.
    If a hunk is unclear, find the change in `CHANGELOG.md` and read
    the reasoning before choosing.

---

## What is never touched

Copier only manages files the template ships. Anything you created —
your modules, your migrations, your tests — is invisible to an update
and cannot conflict.

The boundary is documented in [the template surface
list](api-stability.md#the-template-surface-this-policy-covers). The
short version: `app/core/`, tooling, and CI are the template's;
`app/modules/<yours>/` is yours. **Keeping that boundary clean is what
keeps updates cheap** — the more template-owned code you edit in place,
the more reconciliation you buy for every future release.

When you must change template-owned behaviour, prefer a seam the
template offers — a setting, a dependency override, a subclass in your
own module — over editing the file. A setting you flip survives every
update; a line you changed in `app/core/` is a conflict on every
release that touches it.

---

## If you have diverged too far

Updating is not mandatory, and a project that has been heavily
customised for two years may be past the point where it pays. That is
a legitimate end state: you own the code, and the template made no
claim on it.

What you give up is the security fixes. If you stop updating, watch
[the security policy](../project/security-policy.md) and apply
advisories by hand, and keep
[`just audit`](dependency-scanning.md) in your own CI so dependency
CVEs still reach you.

---

## See also

- [API Stability & SemVer](api-stability.md) — what counts as breaking
- [Release Notes](../project/changelog.md) — the per-version entries
  this guide tells you to read
- [Quality Checks](quality-checks.md) — what `just check` runs
