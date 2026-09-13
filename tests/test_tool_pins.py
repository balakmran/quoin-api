"""Keep CI and the image on the same pinned build tooling.

Dependabot bumps the Dockerfile's uv image but not the `version:` input
of `setup-uv`, so without this check the two drift apart silently.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = ROOT / "Dockerfile"
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))

_UV_IMAGE = re.compile(r"ghcr\.io/astral-sh/uv:(\S+?)@sha256:[0-9a-f]{64}")
_SETUP_UV = re.compile(
    r"uses: astral-sh/setup-uv@\S+.*\n\s+with:\n(?:\s+#.*\n)*"
    r"\s+version: \"([^\"]+)\""
)


def _dockerfile_uv_version() -> str:
    """Return the uv version the Dockerfile copies its binary from."""
    match = _UV_IMAGE.search(DOCKERFILE.read_text(encoding="utf-8"))
    assert match is not None, "Dockerfile has no digest-pinned uv image"
    return match.group(1)


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda p: p.name)
def test_workflows_install_the_dockerfile_uv(workflow: Path) -> None:
    """Every `setup-uv` step pins the version the image is built with."""
    text = workflow.read_text(encoding="utf-8")
    uses = text.count("uses: astral-sh/setup-uv@")
    versions = _SETUP_UV.findall(text)

    assert len(versions) == uses, f"{workflow.name}: setup-uv without version"
    assert set(versions) <= {_dockerfile_uv_version()}


def test_dockerfile_base_images_are_digest_pinned() -> None:
    """Every `FROM` names an immutable digest, not only a mutable tag."""
    from_lines = [
        line
        for line in DOCKERFILE.read_text(encoding="utf-8").splitlines()
        if line.startswith("FROM ")
    ]

    assert from_lines
    for line in from_lines:
        assert re.search(r"@sha256:[0-9a-f]{64}", line), line
