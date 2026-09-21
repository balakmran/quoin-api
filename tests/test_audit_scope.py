"""Keep `just audit-prod` narrowed to what ships in the container.

`uv audit --locked` audits the whole lock unless each group is excluded
by name: `--no-default-groups` and `--no-dev` are both silently no-ops
for it. The recipe therefore lists the groups one by one, which drifts
the moment a new one is declared -- and the failure is invisible, since
a widened scan still passes.
"""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JUSTFILE = ROOT / "justfile"
PYPROJECT = ROOT / "pyproject.toml"


def _declared_groups() -> set[str]:
    """Return every dependency group declared in `pyproject.toml`."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return set(data.get("dependency-groups", {}))


def _excluded_groups() -> set[str]:
    """Return the groups the `audit-prod` recipe excludes."""
    match = re.search(
        r"^audit-prod:\n((?:\s+.*\n)+)",
        JUSTFILE.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert match is not None, "audit-prod recipe not found"
    return set(re.findall(r"--no-group (\S+)", match.group(1)))


def test_audit_prod_excludes_every_declared_group() -> None:
    """A new dependency group must be excluded, or the scan widens."""
    declared = _declared_groups()
    assert declared, "no dependency groups declared"
    missing = declared - _excluded_groups()
    assert not missing, (
        f"just audit-prod does not exclude {sorted(missing)}, so it scans "
        "more than the container ships. Add --no-group for each."
    )
