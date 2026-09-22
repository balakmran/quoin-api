"""Keep `.env.example` loadable and honest.

`cp .env.example .env` is the documented first step, and `just` loads
`.env` with a stricter parser than python-dotenv: an unquoted value with
spaces fails every recipe, and a double-quoted JSON list loses its inner
quotes before the app sees it.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from dotenv import dotenv_values

from app.core.config import Settings

ROOT = Path(__file__).resolve().parent.parent
ENV_EXAMPLE = ROOT / ".env.example"

#: Values deliberately set for local development, not the code default.
_DEV_OVERRIDES = {
    "OAUTH_JWKS_URI",
    "OAUTH_ISSUER",
    "OAUTH_AUDIENCE",
    "OAUTH_ROLES_CLAIM",
    "OAUTH_SUPERUSER_ENABLED",
}


def test_every_setting_is_listed() -> None:
    """`.env.example` names every setting, so it is the full reference."""
    prefix = Settings.model_config.get("env_prefix", "").upper()
    listed = {key.removeprefix(prefix) for key in dotenv_values(ENV_EXAMPLE)}
    assert set(Settings.model_fields) - listed == set()


def test_values_match_code_defaults() -> None:
    """Apart from the marked dev overrides, every value is the default."""
    with patch.dict(os.environ, {}, clear=True):
        example = Settings(_env_file=ENV_EXAMPLE)
        default = Settings(_env_file=None)
    differing = {
        name
        for name in Settings.model_fields
        if getattr(example, name) != getattr(default, name)
    }
    assert differing == _DEV_OVERRIDES


@pytest.mark.skipif(shutil.which("just") is None, reason="just not installed")
def test_just_loads_the_same_values(tmp_path: Path) -> None:
    """`just` exports exactly what python-dotenv reads from the file."""
    justfile = tmp_path / "justfile"
    justfile.write_text(
        "env:\n"
        f"    @{sys.executable} -c 'import json, os; "
        "print(json.dumps(dict(os.environ)))'\n"
    )
    result = subprocess.run(
        [
            "just",
            "--justfile",
            str(justfile),
            "--dotenv-path",
            str(ENV_EXAMPLE),
            "env",
        ],
        capture_output=True,
        text=True,
        check=True,
        # Clean env: dotenv-load never overrides an already-set variable,
        # and `just test` has exported the test profile's.
        env={"PATH": os.environ["PATH"]},
    )
    exported = json.loads(result.stdout)
    expected = dotenv_values(ENV_EXAMPLE)
    assert {key: exported.get(key) for key in expected} == expected
