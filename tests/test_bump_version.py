from pathlib import Path

import pytest

from scripts import bump_version
from scripts.bump_version import next_version


@pytest.mark.parametrize(
    ("current", "part", "rc", "expected"),
    [
        ("0.12.0", "patch", False, "0.12.1"),
        ("0.12.3", "minor", False, "0.13.0"),
        ("0.14.2", "major", False, "1.0.0"),
        ("0.14.0", "major", True, "1.0.0-rc.1"),
        ("1.0.0", "minor", True, "1.1.0-rc.1"),
        ("1.0.0-rc.1", "rc", False, "1.0.0-rc.2"),
        ("1.0.0-rc.9", "rc", False, "1.0.0-rc.10"),
        ("1.0.0-rc.2", "release", False, "1.0.0"),
    ],
)
def test_next_version(current: str, part: str, rc: bool, expected: str) -> None:
    """Final versions bump as before; candidates advance or finalise."""
    assert next_version(current, part, rc=rc) == expected


@pytest.mark.parametrize(
    ("current", "part", "rc", "message"),
    [
        ("1.0.0-rc.2", "major", False, "is a release candidate"),
        ("1.0.0-rc.2", "patch", True, "is a release candidate"),
        ("1.0.0", "rc", False, "is not a release candidate"),
        ("1.0.0", "release", False, "is not a release candidate"),
        ("1.0.0-rc.1", "rc", True, "cannot be combined"),
        ("1.0.0", "build", False, "unknown part"),
        ("1.0", "patch", False, "unrecognised version"),
        ("1.0.0-beta.1", "patch", False, "unrecognised version"),
    ],
)
def test_next_version_rejects_bumps_that_do_not_apply(
    current: str, part: str, rc: bool, message: str
) -> None:
    """A bump that would silently skip or corrupt a version is refused."""
    with pytest.raises(ValueError, match=message):
        next_version(current, part, rc=rc)


def _write_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pyproject: str, init: str
) -> tuple[Path, Path]:
    """Point the script at temporary version files."""
    pyproject_path = tmp_path / "pyproject.toml"
    init_path = tmp_path / "__init__.py"
    pyproject_path.write_text(
        '[project]\nname = "x"\n'
        f'version = "{pyproject}"\n\n'
        '[tool.uv]\nrequired-version = ">=0.11.19"\n'
    )
    init_path.write_text(f'__version__ = "{init}"\n')
    monkeypatch.setattr(bump_version, "PYPROJECT_PATH", pyproject_path)
    monkeypatch.setattr(bump_version, "INIT_PATH", init_path)
    return pyproject_path, init_path


def test_bump_version_writes_both_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both version strings move together; nothing else is touched."""
    pyproject_path, init_path = _write_versions(
        tmp_path, monkeypatch, "0.14.0", "0.14.0"
    )

    assert bump_version.main(["major", "--rc"]) == 0

    assert 'version = "1.0.0-rc.1"' in pyproject_path.read_text()
    assert 'required-version = ">=0.11.19"' in pyproject_path.read_text()
    assert init_path.read_text() == '__version__ = "1.0.0-rc.1"\n'


def test_bump_version_refuses_mismatched_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Diverged version files are an error, not a silent overwrite."""
    pyproject_path, _ = _write_versions(
        tmp_path, monkeypatch, "0.14.0", "0.13.0"
    )

    with pytest.raises(SystemExit):
        bump_version.bump_version("patch")

    assert 'version = "0.14.0"' in pyproject_path.read_text()


def test_bump_version_reports_inapplicable_bump(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An invalid bump exits non-zero and leaves the files unchanged."""
    _, init_path = _write_versions(tmp_path, monkeypatch, "1.0.0", "1.0.0")

    with pytest.raises(SystemExit):
        bump_version.bump_version("rc")

    assert init_path.read_text() == '__version__ = "1.0.0"\n'


def test_bump_version_requires_a_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file without a recognisable version is an error."""
    pyproject_path, _ = _write_versions(
        tmp_path, monkeypatch, "0.14.0", "0.14.0"
    )
    pyproject_path.write_text('[project]\nname = "x"\n')

    with pytest.raises(SystemExit):
        bump_version.bump_version("patch")
