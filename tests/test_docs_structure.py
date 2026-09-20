"""Hold every guide to the same skeleton.

A reader who has read one guide should be able to predict the shape of
the next one: what it does, how to test it, where to go next. Before
this test that shape was aspirational — five of twenty-two guides had a
Testing section and the rest each invented their own ending.

Only the two load-bearing sections are enforced. A guide that tells you
how to build something and not how to test it has handed you the easy
half, and a guide that stops dead has nowhere to send a reader who is
not finished. Everything between those two is the author's business.

The list of guides that need a Testing section is derived from the nav
rather than hardcoded, so a guide added under Build or API Design is
held to the rule on the day it appears.
"""

import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
NAV = ROOT / "zensical.toml"

#: Nav sections whose guides describe behaviour you write code against,
#: and therefore behaviour you can test.
_TESTABLE_SECTIONS = ("Build", "API Design")

#: `getting-started.md` closes with a "What's Next?" table, which does
#: the same job for a first-run page and does it better.
_NO_SEE_ALSO = ("guides/getting-started.md",)


def _nav() -> list[dict[str, object]]:
    """Return the raw nav entries from `zensical.toml`."""
    return tomllib.loads(NAV.read_text(encoding="utf-8"))["project"]["nav"]


def _child_pages(section: str) -> list[str]:
    """Return the pages under `section`, excluding its index page.

    `navigation.indexes` attaches a section's index page as a bare
    string entry; its children are `{label = path}` tables. Skipping the
    strings leaves the guides themselves.
    """
    for entry in _nav():
        children = entry.get(section)
        if isinstance(children, list):
            return [
                next(iter(child.values()))
                for child in children
                if isinstance(child, dict)
            ]
    raise AssertionError(f"no {section!r} section in the nav")


def _testable_guides() -> list[str]:
    """Return every guide that must document how to test it."""
    return [
        page for section in _TESTABLE_SECTIONS for page in _child_pages(section)
    ]


def _guide_pages() -> list[str]:
    """Return every hand-written guide, excluding section indexes."""
    indexes = {"build.md", "api-design.md", "ship.md"}
    return sorted(
        f"guides/{p.name}"
        for p in (DOCS / "guides").glob("*.md")
        if p.name not in indexes
    )


def _headings(page: str) -> list[str]:
    """Return the `##` headings of `page`, in order."""
    return [
        line.removeprefix("## ").strip()
        for line in (DOCS / page).read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    ]


@pytest.mark.parametrize("page", _testable_guides())
def test_guide_documents_how_to_test_it(page: str) -> None:
    """Every Build and API Design guide has a Testing section.

    The heading is spelled exactly `## Testing` so a reader scanning the
    table of contents finds the same word on every page.
    """
    assert "Testing" in _headings(page), (
        f"docs/{page} has no `## Testing` section. Say how to test the "
        f"behaviour it describes, naming the fixtures from "
        f"tests/conftest.py that a reader would actually use."
    )


@pytest.mark.parametrize("page", _guide_pages())
def test_guide_ends_with_see_also(page: str) -> None:
    """Every guide closes by pointing somewhere else."""
    if page in _NO_SEE_ALSO:
        pytest.skip(f"{page} closes with its own next-steps table")

    headings = _headings(page)

    assert headings and headings[-1] == "See Also", (
        f"docs/{page} should end with a `## See Also` section listing "
        f"the two or three pages a reader wants next. Its last heading "
        f"is {headings[-1]!r}."
        if headings
        else f"docs/{page} has no `##` headings at all."
    )
