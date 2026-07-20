#!/usr/bin/env python3
"""Verify that `copier update` applies cleanly across a template release.

QuoinAPI is a Copier template, and `copier update` is how a project
generated from it takes later template improvements. That path is easy to
silently break — nothing in the normal test suite exercises it, since it
only runs against a *generated* project, not this repository itself.

This script proves the mechanism still works between two tags: generate a
project from the older tag, commit it as its own git repo (required for
`copier update` to compute a diff), then update it to the newer tag and
check the result is clean. It intentionally does NOT run `just check` (or
any quality gate) against the generated project — the scaffold passing
`just check` out of the box is a separate, already-roadmapped concern
(see ROADMAP.md, "Template Completeness"); this script only answers
"does `copier update` itself work", not "is the scaffold polished".

Usage:
    uv run python scripts/verify_template_update.py <previous-tag> <current-tag>
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_COMMIT_LINE = re.compile(r"^_commit:\s*(\S+)\s*$", re.MULTILINE)
EXPECTED_ARGS = 3


def _run(
    args: list[str], *, cwd: Path, env: dict[str, str] | None = None
) -> None:
    """Run a subprocess, raising with combined output on failure.

    Args:
        args: The command and its arguments.
        cwd: Working directory to run the command in.
        env: Optional environment overrides merged onto the current one.

    Raises:
        SystemExit: If the command exits non-zero.
    """
    result = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        print(f"[verify-template-update] command failed: {' '.join(args)}")
        print(result.stdout)
        print(result.stderr)
        raise SystemExit(1)


def _git_commit_all(repo: Path, message: str) -> None:
    """Init a git repo (if needed) and commit everything in it.

    `copier update` requires the destination to be a git repository so it
    can three-way-merge template changes against local evolution.
    """
    if not (repo / ".git").exists():
        _run(["git", "init", "-q", "-b", "main"], cwd=repo)
    env = {
        "GIT_AUTHOR_NAME": "quoin-ci",
        "GIT_AUTHOR_EMAIL": "ci@quoin-api.invalid",
        "GIT_COMMITTER_NAME": "quoin-ci",
        "GIT_COMMITTER_EMAIL": "ci@quoin-api.invalid",
    }
    _run(["git", "add", "-A"], cwd=repo)
    _run(["git", "commit", "-q", "-m", message], cwd=repo, env=env)


def _check_no_conflicts(project: Path) -> None:
    """Fail if `copier update` left any `.rej` conflict files behind."""
    rejects = sorted(project.rglob("*.rej"))
    if not rejects:
        return
    print("[verify-template-update] copier update left conflict files:")
    for rej in rejects:
        print(f"\n--- {rej.relative_to(project)} ---")
        print(rej.read_text(errors="replace"))
    raise SystemExit(1)


def _check_recorded_commit(project: Path, expected_tag: str) -> None:
    """Fail unless `.copier-answers.yml` now records the expected tag."""
    answers_path = project / ".copier-answers.yml"
    if not answers_path.is_file():
        print(
            "[verify-template-update] .copier-answers.yml is missing "
            "after update"
        )
        raise SystemExit(1)
    match = _COMMIT_LINE.search(answers_path.read_text())
    recorded = match.group(1) if match else None
    if recorded != expected_tag:
        print(
            f"[verify-template-update] .copier-answers.yml records "
            f"'{recorded}', expected '{expected_tag}'"
        )
        raise SystemExit(1)


def verify(previous_tag: str, current_tag: str) -> None:
    """Generate from `previous_tag`, update to `current_tag`, and verify.

    Args:
        previous_tag: The older template tag to generate a project from.
        current_tag: The newer template tag to update that project to.
    """
    with tempfile.TemporaryDirectory(prefix="quoin-template-update-") as tmp:
        project = Path(tmp) / "generated-project"

        print(f"[verify-template-update] generating from {previous_tag}...")
        _run(
            [
                "uvx",
                "copier",
                "copy",
                "--defaults",
                "--trust",
                "--vcs-ref",
                previous_tag,
                str(REPO_ROOT),
                str(project),
            ],
            cwd=REPO_ROOT,
        )
        _git_commit_all(project, "initial")

        print(f"[verify-template-update] updating to {current_tag}...")
        _run(
            [
                "uvx",
                "copier",
                "update",
                "--defaults",
                "--trust",
                # Force .rej conflict files. Copier's default `inline`
                # mode writes conflict markers into the files and deletes
                # the .rej witnesses, which `_check_no_conflicts` (a .rej
                # glob) would then miss — silently passing a conflicted
                # update.
                "--conflict",
                "rej",
                "--vcs-ref",
                current_tag,
            ],
            cwd=project,
        )

        _check_no_conflicts(project)
        _check_recorded_commit(project, current_tag)

    print(
        f"[verify-template-update] OK: {previous_tag} -> {current_tag} "
        "applied cleanly."
    )


def main(argv: list[str]) -> int:
    """Entry point.

    Returns:
        0 on a clean update, non-zero if `copier` is missing or the
        update left conflicts or an unexpected recorded commit.
    """
    if len(argv) != EXPECTED_ARGS:
        print(
            "Usage: python scripts/verify_template_update.py "
            "<previous-tag> <current-tag>"
        )
        return 1
    if shutil.which("uvx") is None:
        print("[verify-template-update] 'uvx' not found on PATH.")
        return 1

    verify(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
