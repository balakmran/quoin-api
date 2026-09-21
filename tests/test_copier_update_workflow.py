"""Run the Copier Update Check's baseline-tag selection against real tags.

The workflow picks the tags to verify an update *from* with a one-line
shell pipeline. It is exercised only when a tag is pushed, so a wrong
sort order would surface after a release rather than before one.

Template-only. The skip keys on the Copier setup script, not on the
workflow: `0.10.0` and `0.11.0` generated the workflow into projects
before `_exclude` covered it, and `copier update` leaves that stale copy
in place while shipping this file, so a file-presence check would run
these assertions against a workflow the template no longer maintains.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "copier-update.yml"
SETUP_TEMPLATE = ROOT / "scripts" / "copier_setup.py.jinja"

TAGS = (
    "v0.12.0",
    "v0.13.0",
    "v0.14.0",
    "v1.0.0-rc.1",
    "v1.0.0-rc.2",
    "v1.0.0",
    "v1.0.1",
)

pytestmark = pytest.mark.skipif(
    not SETUP_TEMPLATE.is_file(),
    reason="only the template repository maintains the update check",
)


@pytest.fixture(scope="module")
def tagged_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A throwaway repository holding final and candidate tags."""
    repo = tmp_path_factory.mktemp("tags")
    git = [
        "git",
        "-c",
        "user.email=test@example.com",
        "-c",
        "user.name=test",
        "-c",
        "commit.gpgsign=false",
    ]
    subprocess.run([*git, "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        [*git, "commit", "-q", "--allow-empty", "--no-verify", "-m", "x"],
        cwd=repo,
        check=True,
    )
    for tag in TAGS:
        subprocess.run([*git, "tag", tag], cwd=repo, check=True)
    return repo


def _previous_tags_command() -> str:
    """Extract the workflow's `PREV_TAGS=...` line verbatim."""
    match = re.search(
        r"^\s*(PREV_TAGS=\$\(.*\))\s*$",
        WORKFLOW.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert match is not None, "PREV_TAGS assignment not found in workflow"
    return match.group(1)


@pytest.mark.parametrize(
    ("current", "expected"),
    [
        ("v1.0.1", ["v1.0.0", "v0.14.0"]),
        ("v1.0.0", ["v1.0.0-rc.2", "v0.14.0"]),
        ("v1.0.0-rc.2", ["v1.0.0-rc.1", "v0.14.0"]),
        ("v1.0.0-rc.1", ["v0.14.0", "v0.13.0"]),
        ("v0.13.0", ["v0.12.0"]),
        ("v0.12.0", []),
    ],
)
def test_update_check_verifies_from_two_baselines(
    tagged_repo: Path, current: str, expected: list[str]
) -> None:
    """The preceding tag, then the newest final release before it."""
    script = (
        f'CURRENT_TAG="{current}"\n'
        f"{_previous_tags_command()}\n"
        'printf %s "$PREV_TAGS"'
    )
    result = subprocess.run(
        ["bash", "-c", script],
        cwd=tagged_repo,
        capture_output=True,
        text=True,
        check=True,
    )

    assert json.loads(result.stdout) == expected
