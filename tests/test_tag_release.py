import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts import tag_release


@pytest.mark.parametrize("version", ["0.13.0", "1.0.0-rc.1", "1.0.0-rc.12"])
def test_read_version_accepts_final_and_candidate_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, version: str
) -> None:
    """`just tag` can read the version a release candidate bump writes."""
    init_path = tmp_path / "__init__.py"
    init_path.write_text(f'__version__ = "{version}"\n')
    monkeypatch.setattr(tag_release, "INIT_PATH", init_path)

    assert tag_release.read_version() == version


@pytest.mark.parametrize(
    ("tag_name", "prerelease"),
    [("v1.0.0", False), ("v1.0.0-rc.1", True)],
)
def test_publish_release_marks_candidates_as_prerelease(
    monkeypatch: pytest.MonkeyPatch, tag_name: str, prerelease: bool
) -> None:
    """Only a release candidate is published as a GitHub pre-release."""
    calls: list[list[str]] = []

    def fake_run(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, returncode=0)

    monkeypatch.setattr(tag_release, "release_exists", lambda _: False)
    monkeypatch.setattr(tag_release.subprocess, "run", fake_run)

    tag_release.publish_release(tag_name, "notes")

    (create,) = calls
    assert create[:4] == ["gh", "release", "create", tag_name]
    assert ("--prerelease" in create) is prerelease
