"""Run the Copier Update Check's previous-tag selection against real tags.

The workflow picks the tag to verify an update *from* with a one-line
shell pipeline. It is exercised only when a tag is pushed, so a wrong
sort order would surface after a release rather than before one.
"""

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "copier-update.yml"

TAGS = (
    "v0.12.0",
    "v0.14.0",
    "v1.0.0-rc.1",
    "v1.0.0-rc.2",
    "v1.0.0",
    "v1.0.1",
)

pytestmark = pytest.mark.skipif(
    not WORKFLOW.is_file(),
    reason="generated projects do not ship the template's update check",
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


def _previous_tag_command() -> str:
    """Extract the workflow's `PREV_TAG=...` line verbatim."""
    match = re.search(
        r"^\s*(PREV_TAG=\$\(.*\))\s*$",
        WORKFLOW.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert match is not None, "PREV_TAG assignment not found in workflow"
    return match.group(1)


@pytest.mark.parametrize(
    ("current", "expected"),
    [
        ("v1.0.1", "v1.0.0"),
        ("v1.0.0", "v1.0.0-rc.2"),
        ("v1.0.0-rc.2", "v1.0.0-rc.1"),
        ("v1.0.0-rc.1", "v0.14.0"),
        ("v0.12.0", ""),
    ],
)
def test_update_check_verifies_from_the_preceding_tag(
    tagged_repo: Path, current: str, expected: str
) -> None:
    """Candidates sort below their final release, not above it."""
    script = (
        f'CURRENT_TAG="{current}"\n'
        f"{_previous_tag_command()}\n"
        'printf %s "$PREV_TAG"'
    )
    result = subprocess.run(
        ["bash", "-c", script],
        cwd=tagged_repo,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout == expected
