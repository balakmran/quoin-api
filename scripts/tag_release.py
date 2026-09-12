#!/usr/bin/env python3
"""Tag the current version and publish its GitHub Release.

`just tag` (alias `just release`) reads the version from
`app/__init__.py`, creates and pushes `vX.Y.Z`, then publishes a GitHub
Release whose body is that version's `CHANGELOG.md` section. Nothing
publishes the release for you otherwise: no tag-triggered workflow in
this repository creates one.

Both halves are idempotent, so re-running after a partial failure is
safe. An existing tag is not recreated (but is still pushed, which is a
no-op when the remote already has it), and an existing release is left
alone rather than aborting the run.

`gh` is required, and both its presence and its authentication are
checked *before* the tag is created — a missing prerequisite then costs
nothing, rather than leaving a pushed tag with no release. Pass
`--no-release` to tag only; that path needs no `gh` at all.

A release candidate (`X.Y.Z-rc.N`, from `just bump <part> --rc`) is
tagged the same way and published as a GitHub pre-release.
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

INIT_PATH = Path("app/__init__.py")
CHANGELOG_PATH = Path("CHANGELOG.md")
_VERSION_RE = re.compile(r'__version__ = "(\d+\.\d+\.\d+(?:-rc\.\d+)?)"')


def read_version() -> str:
    """Read the current version from `app/__init__.py`.

    Returns:
        The version string, e.g. "0.11.0".

    Raises:
        SystemExit: If the version cannot be found.
    """
    match = _VERSION_RE.search(INIT_PATH.read_text(encoding="utf-8"))
    if not match:
        print(f"Error: Could not find version in {INIT_PATH}")
        raise SystemExit(1)
    return match.group(1)


def changelog_section(version: str) -> str:
    """Extract one version's section from `CHANGELOG.md`.

    Returns everything between this version's `## [X.Y.Z] - date`
    heading and the next `## [` heading, which is the release-body shape
    every tag since v0.8.0 uses: starts at `### Added`, no heading line.

    Args:
        version: The version whose section to extract.

    Returns:
        The section text, stripped of surrounding blank lines.

    Raises:
        SystemExit: If the changelog has no section for this version.
    """
    text = CHANGELOG_PATH.read_text(encoding="utf-8")
    heading = re.compile(rf"^## \[{re.escape(version)}\].*$", re.MULTILINE)
    match = heading.search(text)
    if not match:
        print(f"Error: {CHANGELOG_PATH} has no section for [{version}].")
        print("Add the release section before tagging.")
        raise SystemExit(1)

    rest = text[match.end() :]
    following = re.search(r"^## \[", rest, re.MULTILINE)
    body = rest[: following.start()] if following else rest
    body = body.strip("\n")
    if not body:
        print(f"Error: the [{version}] changelog section is empty.")
        raise SystemExit(1)
    return body


def gh_blocker() -> str | None:
    """Check that `gh` is installed and authenticated.

    Returns:
        A human-readable reason it cannot be used, or None if it can.
    """
    if shutil.which("gh") is None:
        return "the GitHub CLI (gh) is not on PATH — see https://cli.github.com"
    status = subprocess.run(
        ["gh", "auth", "status"], capture_output=True, text=True, check=False
    )
    if status.returncode != 0:
        return "gh is not authenticated — run `gh auth login`"
    return None


def release_exists(tag_name: str) -> bool:
    """Report whether a GitHub Release already exists for `tag_name`."""
    result = subprocess.run(
        ["gh", "release", "view", tag_name],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def publish_release(tag_name: str, body: str) -> None:
    """Create the GitHub Release for `tag_name`.

    Args:
        tag_name: The tag to release, e.g. "v0.11.0".
        body: Release notes, passed on stdin so the changelog section
            never has to survive shell quoting.

    Raises:
        SystemExit: If `gh` fails to create the release.
    """
    if release_exists(tag_name):
        print(f"Release {tag_name} already exists; leaving it as is.")
        return

    print(f"Publishing release {tag_name}...")
    args = [
        "gh",
        "release",
        "create",
        tag_name,
        "--title",
        tag_name,
        # Fails loudly if the tag never reached origin, rather than
        # creating a release against a tag nobody else can fetch.
        "--verify-tag",
        "--notes-file",
        "-",
    ]
    if "-rc." in tag_name:
        args.append("--prerelease")
    result = subprocess.run(
        args,
        input=body,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"Error: failed to publish release {tag_name}.")
        print("The tag is already pushed — do not delete it. Fix the")
        print("problem and re-run `just tag`; it will skip the tag and")
        print("retry only the release.")
        raise SystemExit(1)
    print(f"Successfully published release {tag_name}")


def tag_release(*, publish: bool = True) -> None:
    """Create and push the version tag, then publish its release.

    Args:
        publish: Whether to publish the GitHub Release after tagging.
    """
    version = read_version()
    tag_name = f"v{version}"

    # Read the changelog and check gh before touching git: both failures
    # are common, and both are free to recover from while nothing has
    # been pushed yet.
    body = changelog_section(version) if publish else ""
    if publish:
        blocker = gh_blocker()
        if blocker is not None:
            print(f"Error: cannot publish the release because {blocker}.")
            print("Run `just tag --no-release` to create the tag only.")
            print(f"No tag was created; {tag_name} is untouched.")
            raise SystemExit(1)

    try:
        existing = subprocess.check_output(
            ["git", "tag"], text=True
        ).splitlines()
    except subprocess.CalledProcessError:
        print("Error: Failed to list git tags.")
        raise SystemExit(1) from None

    if tag_name in existing:
        print(f"Tag {tag_name} already exists; not recreating it.")
    else:
        print(f"Creating tag {tag_name}...")
        try:
            subprocess.run(["git", "tag", tag_name], check=True)
        except subprocess.CalledProcessError as exc:
            print(f"Error creating tag: {exc}")
            raise SystemExit(1) from None
        print(f"Successfully created tag {tag_name}")

    # Push unconditionally: a no-op when origin already has the tag, and
    # the thing that makes a re-run after a failed push actually work.
    print("Pushing tag to origin...")
    try:
        subprocess.run(["git", "push", "origin", tag_name], check=True)
    except subprocess.CalledProcessError as exc:
        print(f"Error pushing tag: {exc}")
        raise SystemExit(1) from None
    print(f"Successfully pushed tag {tag_name}")

    if publish:
        publish_release(tag_name, body)
    else:
        print("Skipping the GitHub Release (--no-release).")


def main(argv: list[str] | None = None) -> int:
    """Entry point.

    Args:
        argv: Argument list, defaulting to `sys.argv[1:]`.

    Returns:
        0 on success; non-zero paths raise SystemExit instead.
    """
    parser = argparse.ArgumentParser(
        description="Tag the current version and publish its GitHub Release."
    )
    parser.add_argument(
        "--no-release",
        action="store_true",
        help="Create and push the tag only; do not publish a release.",
    )
    args = parser.parse_args(argv)

    tag_release(publish=not args.no_release)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
