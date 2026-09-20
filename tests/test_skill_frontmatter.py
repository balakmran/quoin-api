"""Keep every skill and subagent's frontmatter parseable.

A description is what makes a skill trigger. When its YAML fails to parse the
loader falls back to the file's heading, and the trigger phrases never reach
the model — silently, because the skill still *appears* in the listing. That
happened to `quoin-pre-pr`, which advertised itself as "Pre-PR Checklist" for
several releases.

The usual cause is a colon inside an unquoted description ("Do NOT use for:
..."), which YAML reads as a nested mapping.
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLAUDE = ROOT / ".claude"

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def _definitions() -> list[Path]:
    """Return every skill and subagent definition file."""
    return sorted(CLAUDE.glob("skills/*/SKILL.md")) + sorted(
        CLAUDE.glob("agents/*.md")
    )


@pytest.mark.parametrize(
    "path", _definitions(), ids=lambda p: p.parent.name + "/" + p.name
)
def test_frontmatter_parses_and_describes(path: Path) -> None:
    """Frontmatter is valid YAML carrying a name and a description."""
    match = _FRONTMATTER.match(path.read_text(encoding="utf-8"))
    assert match is not None, f"{path} has no `---` frontmatter block"

    try:
        parsed = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:  # pragma: no cover - only on a bad edit
        pytest.fail(
            f"{path} frontmatter is not valid YAML, so the loader will fall "
            f"back to the heading and lose the trigger phrases. A colon "
            f"followed by a space inside an unquoted value is the usual "
            f"cause — rephrase it or quote the whole value.\n{exc}"
        )

    assert isinstance(parsed, dict), f"{path} frontmatter is not a mapping"
    assert parsed.get("name"), f"{path} frontmatter has no `name`"
    assert parsed.get("description"), f"{path} frontmatter has no `description`"
