"""Keep CI and the image on the same pinned build tooling.

Dependabot bumps the Dockerfile's uv image but not the `version:` input
of `setup-uv`, so without this check the two drift apart silently.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = ROOT / "Dockerfile"
SETUP_TEMPLATE = ROOT / "scripts" / "copier_setup.py.jinja"

# Template-maintenance CI, excluded from generation since 0.12.0. A
# project generated from 0.10.0 or 0.11.0 still carries a stale copy that
# `copier update` never touches, so outside the template these are not
# the project's workflows to keep pinned.
_TEMPLATE_ONLY = {"copier-update.yml", "scaffold-smoke.yml"}


def _workflows() -> list[Path]:
    """Return the workflows this repository is responsible for."""
    found = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    if SETUP_TEMPLATE.is_file():
        return found
    return [p for p in found if p.name not in _TEMPLATE_ONLY]


WORKFLOWS = _workflows()

_UV_IMAGE = re.compile(r"ghcr\.io/astral-sh/uv:(\S+)")
_SETUP_UV = re.compile(
    r"uses: astral-sh/setup-uv@\S+.*\n\s+with:\n(?:\s+#.*\n)*"
    r"\s+version: \"([^\"]+)\""
)


def _dockerfile_uv_version() -> str:
    """Return the uv version the Dockerfile copies its binary from."""
    match = _UV_IMAGE.search(DOCKERFILE.read_text(encoding="utf-8"))
    assert match is not None, "Dockerfile has no version-pinned uv image"
    return match.group(1)


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda p: p.name)
def test_workflows_install_the_dockerfile_uv(workflow: Path) -> None:
    """Every `setup-uv` step pins the version the image is built with."""
    text = workflow.read_text(encoding="utf-8")
    uses = text.count("uses: astral-sh/setup-uv@")
    versions = _SETUP_UV.findall(text)

    assert len(versions) == uses, f"{workflow.name}: setup-uv without version"
    assert set(versions) <= {_dockerfile_uv_version()}
