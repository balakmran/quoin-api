"""Lint a project generated with worst-case Copier answers.

Copier rewrites template identifiers with the adopter's answers, and a
longer answer lengthens every line that carries one -- including
docstrings and comments, which no formatter reflows. This runs the real
post-generation substitution over a copy of the tree and lints the
result, so `just check` here fails before an adopter's `just lint` does.
"""

import re
import shutil
import subprocess
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
SETUP_TEMPLATE = ROOT / "scripts" / "copier_setup.py.jinja"

# Everything `ruff check .` reads in a generated project.
LINTED_PATHS = ("alembic", "app", "scripts", "tests", "pyproject.toml")

# Sized to the lint headroom: prose is written to 80 columns and E501
# fires past 100, which absorbs a settings prefix of up to 30 characters.
_PROJECT_NAME = "Northwind Traders Platform API"
WORST_CASE_ANSWERS = {
    "project_name": _PROJECT_NAME,
    "project_slug": "northwind-traders-platform-api",
    "env_prefix": "NORTHWIND_TRADERS_PLATFORM_API",
    "description": "The Foundation for your Python backend API.",
    "long_description": (
        f"{_PROJECT_NAME} is a production-ready Python backend foundation "
        "built with FastAPI, SQLModel, and the Astral stack (uv, ruff, ty)."
    ),
    "author_name": "Maximiliana Featherstonehaugh",
    "author_email": "maximiliana@northwind-traders.example",
    "github_username": "northwind-traders",
    "google_analytics_id": "",
}

pytestmark = pytest.mark.skipif(
    not SETUP_TEMPLATE.is_file(),
    reason="only the template repository ships the Copier setup script",
)


def _load_setup_script(
    answers: dict[str, str], base_dir: Path
) -> dict[str, Any]:
    """Render the setup template with ``answers`` and execute it.

    Args:
        answers: A value for every Copier placeholder in the template.
        base_dir: The generated tree the script should operate on.

    Returns:
        The executed script's global namespace.
    """
    source = re.sub(
        r"\{\{ (\w+) \}\}",
        lambda match: answers[match.group(1)],
        SETUP_TEMPLATE.read_text(encoding="utf-8"),
    )
    namespace: dict[str, Any] = {"__name__": "copier_setup"}
    exec(compile(source, str(SETUP_TEMPLATE), "exec"), namespace)
    # BASE_DIR is bound to the cwd at import and read at call time.
    namespace["BASE_DIR"] = base_dir
    return namespace


def _ruff(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run the project's pinned ruff in ``cwd``."""
    return subprocess.run(
        [sys.executable, "-m", "ruff", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_generated_project_lints_with_worst_case_answers(
    tmp_path: Path,
) -> None:
    """Long answers still leave a generated project passing ruff."""
    for name in LINTED_PATHS:
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(
                source,
                tmp_path / name,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        else:
            shutil.copy2(source, tmp_path / name)

    setup = _load_setup_script(WORST_CASE_ANSWERS, tmp_path)
    with redirect_stdout(StringIO()):
        setup["run_replacements"]()

    # Guard against a vacuous pass if the substitution stops matching.
    prefix = WORST_CASE_ANSWERS["env_prefix"].lower()
    config = (tmp_path / "app" / "core" / "config.py").read_text()
    assert f'env_prefix="{prefix}_"' in config

    # Mirror format_sources(): fix and format, then lint what is left.
    _ruff("check", "--fix", ".", cwd=tmp_path)
    _ruff("format", ".", cwd=tmp_path)
    result = _ruff("check", "--output-format", "concise", ".", cwd=tmp_path)

    assert result.returncode == 0, result.stdout
