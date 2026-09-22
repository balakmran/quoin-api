"""Fail when code ships with no documentation at all.

A docs sweep that starts from the docs can only find statements that are
*wrong*; it is blind to a module that no page mentions, because nothing
points at it to check. That is how `app/core/security.py`, `schemas.py`,
`lifecycle.py`, `openapi.py`, and the whole `system` module shipped with no
entry in the API reference. These tests walk the other way — from the code to
the docs — so the next one fails the gate instead of going unnoticed.

Each test asserts only that *something* documents the subject. Whether the
prose is any good is a review question, not one a test can answer.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
NAV = ROOT / "zensical.toml"

CORE_REFERENCE = DOCS / "api" / "core.md"
ERROR_GUIDE = DOCS / "guides" / "error-handling.md"

_EXCEPTION_CLASS = re.compile(r"^class ([A-Za-z]+)\([A-Za-z]*Error\)", re.M)
_MIDDLEWARE_CLASS = re.compile(r"^class ([A-Za-z]+Middleware)\b", re.M)


#: Infrastructure outside `app/core/` that modules import directly.
#: `app/db/base.py` is left out: it only registers models for Alembic.
_SHARED_MODULES = ("db/session.py", "http/client.py")


def _core_modules() -> list[Path]:
    """Return every module the Core reference must document."""
    core = (
        p for p in (ROOT / "app" / "core").glob("*.py") if p.stem != "__init__"
    )
    shared = (ROOT / "app" / rel for rel in _SHARED_MODULES)
    return sorted([*core, *shared])


def _feature_modules() -> list[Path]:
    """Return every package under `app/modules/`."""
    return sorted(
        p
        for p in (ROOT / "app" / "modules").iterdir()
        if (p / "routes.py").is_file()
    )


def _doc_pages() -> list[Path]:
    """Return every Markdown page under `docs/`."""
    return sorted(DOCS.rglob("*.md"))


def _read(path: Path) -> str:
    """Return the file's text."""
    return path.read_text(encoding="utf-8")


#: A `::: app.core.config` mkdocstrings block.
_INCLUDE = re.compile(r"^::: +([\w.]+)\s*$", re.M)


def _rendered(path: Path) -> str:
    """Return a page's text with every mkdocstrings block resolved.

    A generated section names only its module, so the symbols it
    documents live in the source file rather than in the Markdown. These
    checks ask "does anything document this", and generated output
    counts, so the module's source is appended before searching.
    """
    body = _read(path)
    for dotted in _INCLUDE.findall(body):
        source = ROOT.joinpath(*dotted.split(".")).with_suffix(".py")
        if source.is_file():
            body += "\n" + _read(source)
    return body


@pytest.mark.parametrize(
    "module",
    _core_modules(),
    ids=lambda p: p.relative_to(ROOT / "app").as_posix(),
)
def test_core_module_has_a_reference_section(module: Path) -> None:
    """Every shared-infrastructure module is in the Core reference.

    Sections are matched on their closing `**Source:**` link rather than
    their heading, because a heading rarely matches the filename (`config.py`
    is documented under "Configuration"). Matching the link rather than a
    bare mention of the path keeps a passing reference in someone else's
    prose from counting as documentation.
    """
    path = module.relative_to(ROOT).as_posix()
    link = rf"\*\*Source:\*\* \[{re.escape(path)}\]"

    assert re.search(link, _read(CORE_REFERENCE)), (
        f"{path} has no section in docs/api/core.md. Add one ending in "
        f"`**Source:** [{path}](...)`, and list it in docs/api/overview.md."
    )


@pytest.mark.parametrize("module", _feature_modules(), ids=lambda p: p.name)
def test_feature_module_has_a_reference_page(module: Path) -> None:
    """Every module under `app/modules/` has its own reference page."""
    page = DOCS / "api" / f"{module.name}.md"

    assert page.is_file(), (
        f"app/modules/{module.name}/ has no docs/api/{module.name}.md. "
        f"Mirror docs/api/user.md."
    )


@pytest.mark.parametrize("module", _feature_modules(), ids=lambda p: p.name)
def test_feature_module_page_is_in_the_nav(module: Path) -> None:
    """A reference page nobody can navigate to is not documentation."""
    assert f"api/{module.name}.md" in _read(NAV), (
        f"docs/api/{module.name}.md is missing from the nav in zensical.toml."
    )


@pytest.mark.parametrize("page", _doc_pages(), ids=lambda p: p.name)
def test_doc_page_is_reachable_from_the_nav(page: Path) -> None:
    """No page is orphaned — every one is listed in `zensical.toml`.

    Including `index.md`: the home page is the site root, but the nav
    still names it, so it needs no exemption.
    """
    relative = page.relative_to(DOCS).as_posix()

    assert relative in _read(NAV), (
        f"docs/{relative} is not in the nav in zensical.toml, so the built "
        f"site has no route to it."
    )


@pytest.mark.parametrize(
    "name",
    _EXCEPTION_CLASS.findall(_read(ROOT / "app" / "core" / "exceptions.py")),
)
def test_domain_exception_is_documented(name: str) -> None:
    """Every domain exception appears in both places that list them.

    The Core reference half is self-satisfying while that section is
    generated — `:::` documents every public class in the module, which
    is the point of generating it. It stays here so the guard returns
    automatically if the section is ever hand-written again. The
    error-handling guide is hand-written, and is what this really pins.
    """
    for doc in (ERROR_GUIDE, CORE_REFERENCE):
        assert re.search(rf"\b{name}\b", _rendered(doc)), (
            f"{name} is missing from docs/{doc.relative_to(DOCS)}. Both the "
            f"error-handling guide and the Core reference list every "
            f"exception with its status code."
        )


@pytest.mark.parametrize(
    "name",
    _MIDDLEWARE_CLASS.findall(_read(ROOT / "app" / "core" / "middlewares.py")),
)
def test_middleware_is_documented(name: str) -> None:
    """Every middleware is described somewhere under `docs/`.

    The stack is split across the security guide (what each layer enforces
    and why the order matters) and the Core reference (the table), so this
    only asserts that one of them mentions it.
    """
    mentioned = any(
        re.search(rf"\b{name}\b", _rendered(page))
        for page in _doc_pages()
        if page.parent.name in ("guides", "api")
    )

    assert mentioned, (
        f"{name} is documented nowhere. Add it to the ordering list in "
        f"docs/guides/security.md and the table in docs/api/core.md."
    )
