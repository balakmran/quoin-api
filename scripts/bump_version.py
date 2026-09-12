"""Bump the version in `pyproject.toml` and `app/__init__.py`.

Versions are `X.Y.Z`, or a release candidate `X.Y.Z-rc.N`:

    just bump                0.12.0     -> 0.12.1
    just bump minor          0.12.0     -> 0.13.0
    just bump major --rc     0.14.0     -> 1.0.0-rc.1
    just bump rc             1.0.0-rc.1 -> 1.0.0-rc.2
    just bump release        1.0.0-rc.2 -> 1.0.0

From a candidate, `major`, `minor`, and `patch` are refused: turning
`1.0.0-rc.2` into `2.0.0` is almost never what was meant.
"""

import argparse
import re
import sys
from pathlib import Path

PYPROJECT_PATH = Path("pyproject.toml")
INIT_PATH = Path("app/__init__.py")

PARTS = ("major", "minor", "patch", "rc", "release")

_VERSION = r"\d+\.\d+\.\d+(?:-rc\.\d+)?"
_PARSE_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:-rc\.(\d+))?")
_PYPROJECT_RE = re.compile(rf'^version = "({_VERSION})"', re.MULTILINE)
_INIT_RE = re.compile(rf'__version__ = "({_VERSION})"')


def next_version(current: str, part: str, *, rc: bool = False) -> str:
    """Compute the version that follows ``current``.

    Args:
        current: The current version, ``X.Y.Z`` or ``X.Y.Z-rc.N``.
        part: One of ``major``, ``minor``, ``patch``, ``rc``, ``release``.
        rc: Make the bumped version the first release candidate. Only
            valid with ``major``, ``minor``, or ``patch``.

    Returns:
        The new version string.

    Raises:
        ValueError: If ``current`` is malformed or the bump does not apply
            to it.
    """
    match = _PARSE_RE.fullmatch(current)
    if match is None:
        raise ValueError(f"unrecognised version {current!r}")
    major, minor, patch = (int(group) for group in match.groups()[:3])
    candidate = match.group(4)
    base = f"{major}.{minor}.{patch}"

    if part in ("rc", "release"):
        if rc:
            raise ValueError(f"--rc cannot be combined with {part!r}")
        if candidate is None:
            raise ValueError(
                f"{current} is not a release candidate; start one with "
                "`just bump <major|minor|patch> --rc`"
            )
        return f"{base}-rc.{int(candidate) + 1}" if part == "rc" else base

    bumped = {
        "major": f"{major + 1}.0.0",
        "minor": f"{major}.{minor + 1}.0",
        "patch": f"{major}.{minor}.{patch + 1}",
    }
    if part not in bumped:
        raise ValueError(f"unknown part {part!r}; use one of {PARTS}")
    if candidate is not None:
        raise ValueError(
            f"{current} is a release candidate; use `rc` for the next "
            "candidate or `release` to finalise it"
        )
    return f"{bumped[part]}-rc.1" if rc else bumped[part]


def bump_version(part: str, *, rc: bool = False) -> str:
    """Write the next version to `pyproject.toml` and `app/__init__.py`.

    Args:
        part: The bump to apply; see `next_version`.
        rc: Make the bumped version the first release candidate.

    Returns:
        The new version string.

    Raises:
        SystemExit: If either file lacks a version, the two disagree, or
            the bump does not apply.
    """
    pyproject = PYPROJECT_PATH.read_text(encoding="utf-8")
    init = INIT_PATH.read_text(encoding="utf-8")
    pyproject_match = _PYPROJECT_RE.search(pyproject)
    init_match = _INIT_RE.search(init)
    if pyproject_match is None or init_match is None:
        print(f"Error: no version found in {PYPROJECT_PATH} or {INIT_PATH}")
        raise SystemExit(1)

    current = pyproject_match.group(1)
    if init_match.group(1) != current:
        print(
            f"Error: {PYPROJECT_PATH} says {current} but {INIT_PATH} says "
            f"{init_match.group(1)}; reconcile them first."
        )
        raise SystemExit(1)

    try:
        new = next_version(current, part, rc=rc)
    except ValueError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from None

    PYPROJECT_PATH.write_text(
        _PYPROJECT_RE.sub(f'version = "{new}"', pyproject, count=1),
        encoding="utf-8",
    )
    INIT_PATH.write_text(
        _INIT_RE.sub(f'__version__ = "{new}"', init, count=1),
        encoding="utf-8",
    )
    print(f"Bumped version {current} -> {new}")
    return new


def main(argv: list[str] | None = None) -> int:
    """Entry point.

    Args:
        argv: Argument list, defaulting to `sys.argv[1:]`.

    Returns:
        0 on success; failures raise SystemExit instead.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("part", nargs="?", default="patch", choices=PARTS)
    parser.add_argument(
        "--rc",
        action="store_true",
        help="Make the bumped version the first release candidate.",
    )
    args = parser.parse_args(argv)

    bump_version(args.part, rc=args.rc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
