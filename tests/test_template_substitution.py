"""Check a project generated with worst-case Copier answers.

Copier rewrites template identifiers with the adopter's answers. A
longer answer lengthens every line that carries one -- including
docstrings and comments, which no formatter reflows -- and any
identifier the map misses ships the template's name to the adopter.
This runs the real post-generation setup over a copy of the tree, so
`just check` here fails before an adopter's project does.

The copy is every tracked file minus the template config's excludes,
because a narrower scan is how the brand leaked last time: skill
directories, a stylesheet and two screenshot filenames all sat outside
the handful of directories this used to read.
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
COPIER_CONFIG = ROOT / "copier.yml"

# Tool caches written into the tree while the tests run; not source.
CACHE_DIRS = {".ruff_cache", "__pycache__"}

# The post-generation steps that shape the shipped tree. format_sources()
# is left out: the lint test below runs the same passes itself.
SETUP_STEPS = (
    "run_replacements",
    "write_clean_changelog",
    "reset_readme",
    "clean_index",
    "clean_zensical",
    "strip_removed_links",
    "strip_screenshots",
    "rewrite_security_policy",
    "strip_template_only",
    "brand_logo",
    "prune_sync_docs",
)

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

# The template's brand and the maintainer's identity. Matched without
# regard to case: the brand leaked for a release as lowercase CSS class
# and directory names while a case-sensitive scan read every one of them
# and passed. Split into pieces so this file never matches itself -- the
# scaffold smoke job's equivalent grep still reads it in the repo.
TEMPLATE_IDENTITY = re.compile(
    "|".join(
        (
            "(?<![A-Za-z])" + "quo" + "in",
            "bala" + "kmran",
            "bala" + "kumaran",
            "mano" + "haran",
        )
    ),
    re.IGNORECASE,
)

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


def _copier_excludes() -> list[str]:
    """Return the ``_exclude`` patterns from the Copier config.

    Parsed by hand: PyYAML is not a declared dependency.
    """
    lines = COPIER_CONFIG.read_text(encoding="utf-8").splitlines()
    start = lines.index("_exclude:") + 1
    patterns: list[str] = []
    for line in lines[start:]:
        if line and not line.startswith(" "):
            break
        match = re.fullmatch(r'\s+-\s+"([^"]+)"', line)
        if match:
            patterns.append(match.group(1))
    return patterns


def _text_lines(path: Path) -> list[str]:
    """Return a file's lines, or none for a binary file.

    The setup script skips files that are not UTF-8 too, so an image can
    neither carry nor receive a substitution.
    """
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return []


def _tracked_files() -> list[str]:
    """Return every path `git ls-files` reports for the template."""
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.split()


@pytest.fixture(scope="module")
def generated_tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A copy of the shipped tree with worst-case answers substituted."""
    root = tmp_path_factory.mktemp("generated")
    for name in _tracked_files():
        source = ROOT / name
        if not source.is_file() or CACHE_DIRS.intersection(Path(name).parts):
            continue
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    # Copier never ships these, so they may keep the template's name.
    for pattern in _copier_excludes():
        for path in root.glob(pattern):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    # Copier renders the config away rather than excluding it.
    (root / COPIER_CONFIG.name).unlink(missing_ok=True)

    setup = _load_setup_script(WORST_CASE_ANSWERS, root)
    with redirect_stdout(StringIO()):
        for step in SETUP_STEPS:
            setup[step]()

    # Guard against a vacuous pass if the substitution stops matching.
    prefix = WORST_CASE_ANSWERS["env_prefix"].lower()
    config = (root / "app" / "core" / "config.py").read_text()
    assert f'env_prefix="{prefix}_"' in config
    return root


def test_generated_project_lints_with_worst_case_answers(
    generated_tree: Path,
) -> None:
    """Long answers still leave a generated project passing ruff."""
    # Mirror format_sources(): fix and format, then lint what is left.
    _ruff("check", "--fix", ".", cwd=generated_tree)
    _ruff("format", ".", cwd=generated_tree)
    result = _ruff(
        "check", "--output-format", "concise", ".", cwd=generated_tree
    )

    assert result.returncode == 0, result.stdout


def test_generated_sources_carry_no_template_identity(
    generated_tree: Path,
) -> None:
    """No branded identifier or maintainer detail survives substitution."""
    # Generation renders and then deletes the setup script; the raw
    # template copied here still holds the map's keys.
    sources = [
        path
        for path in sorted(generated_tree.rglob("*"))
        if path.is_file()
        and path.name != SETUP_TEMPLATE.name
        and not CACHE_DIRS.intersection(path.parts)
    ]
    # Filenames are scanned too: a screenshot whose name carried the
    # brand shipped its old name while the substitution rewrote every
    # link to it, leaving an embed pointing at nothing.
    leaks = [
        f"{path.relative_to(generated_tree)}: filename"
        for path in sources
        if TEMPLATE_IDENTITY.search(str(path.relative_to(generated_tree)))
    ]
    leaks += [
        f"{path.relative_to(generated_tree)}:{lineno}: {line.strip()}"
        for path in sources
        for lineno, line in enumerate(_text_lines(path), start=1)
        if TEMPLATE_IDENTITY.search(line)
    ]

    assert not leaks, "\n".join(leaks)
