import importlib
import os
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from app.core.config import (
    Environment,
    Settings,
    validate_production_oauth,
)


def test_environment_enum_values() -> None:
    """Test Environment enum has correct values."""
    assert Environment.development == "development"
    assert Environment.test == "test"
    assert Environment.production == "production"


def test_settings_defaults() -> None:
    """Test Settings default values."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None)  # type: ignore
        assert settings.ENV == Environment.development
        assert settings.LOG_LEVEL == "INFO"
        assert settings.OTEL_ENABLED is True
        assert settings.POSTGRES_HOST == "localhost"
        assert settings.POSTGRES_PORT == 5432  # noqa: PLR2004


def test_settings_with_env_prefix() -> None:
    """Test that settings correctly uses QUOIN_ prefix."""
    with patch.dict(
        os.environ,
        {
            "QUOIN_LOG_LEVEL": "DEBUG",
            "QUOIN_POSTGRES_HOST": "testhost",
            "QUOIN_POSTGRES_PORT": "3306",
        },
        clear=True,
    ):
        settings = Settings()
        assert settings.LOG_LEVEL == "DEBUG"
        assert settings.POSTGRES_HOST == "testhost"
        assert settings.POSTGRES_PORT == 3306  # noqa: PLR2004


def test_env_file_selection_test() -> None:
    """Test that .env.test is selected when ENV=test."""
    with patch.dict(os.environ, {"QUOIN_ENV": "test"}, clear=True):
        # Re-import to trigger env file selection logic
        from app.core import config  # noqa: PLC0415

        importlib.reload(config)
        # The env_file should be .env.test
        assert config.env_file == ".env.test"


def test_env_file_selection_production() -> None:
    """Test that .env.production is selected when ENV=production."""
    with patch.dict(os.environ, {"QUOIN_ENV": "production"}, clear=True):
        # Re-import to trigger env file selection logic
        from app.core import config  # noqa: PLC0415

        importlib.reload(config)
        # The env_file should be .env.production
        assert config.env_file == ".env.production"


def test_env_file_selection_default() -> None:
    """Test that .env is selected for development."""
    with patch.dict(os.environ, {"QUOIN_ENV": "development"}, clear=True):
        # Re-import to trigger env file selection logic
        from app.core import config  # noqa: PLC0415

        importlib.reload(config)
        # The env_file should be .env
        assert config.env_file == ".env"


def test_database_url_construction() -> None:
    """Test DATABASE_URL is correctly constructed."""
    settings = Settings(
        POSTGRES_DRIVER="postgresql+asyncpg",
        POSTGRES_HOST="myhost",
        POSTGRES_PORT=5433,
        POSTGRES_USER="myuser",
        POSTGRES_PASSWORD=SecretStr("mypass"),
        POSTGRES_DB="mydb",
    )
    db_url = str(settings.DATABASE_URL)
    assert "postgresql+asyncpg" in db_url
    assert "myhost" in db_url
    assert "5433" in db_url
    assert "myuser" in db_url
    assert "mydb" in db_url


def _prod(**overrides: object) -> Settings:
    """Build a production Settings with OAuth overrides, no env file."""
    base: dict[str, object] = {
        "_env_file": None,
        "ENV": Environment.production,
        "OAUTH_JWKS_URI": "https://issuer.example/jwks",
        "OAUTH_ISSUER": "https://issuer.example",
        "OAUTH_AUDIENCE": "api",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore


def test_production_oauth_fully_configured_boots() -> None:
    """A fully-configured production profile validates clean (S3)."""
    with patch.dict(os.environ, {}, clear=True):
        validate_production_oauth(_prod())  # no raise


@pytest.mark.parametrize(
    "missing",
    ["OAUTH_JWKS_URI", "OAUTH_ISSUER", "OAUTH_AUDIENCE"],
)
def test_production_missing_oauth_crash_loops(missing: str) -> None:
    """Production fails fast when any OAuth trust anchor is unset (S3)."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match=missing):
            validate_production_oauth(_prod(**{missing: None}))


def test_production_requires_https_jwks() -> None:
    """Production rejects a non-https JWKS URI (S7)."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="https"):
            validate_production_oauth(
                _prod(OAUTH_JWKS_URI="http://issuer.example/jwks")
            )


def test_development_skips_oauth_validation() -> None:
    """Development is a no-op even with no OAuth configured (S3)."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None, ENV=Environment.development)  # type: ignore
        validate_production_oauth(settings)  # no raise
        assert settings.OAUTH_ISSUER is None


def test_unknown_quoin_var_is_ignored() -> None:
    """A mistyped QUOIN_* var is dropped, not accepted as extra (S5)."""
    with patch.dict(os.environ, {"QUOIN_OAUTH_JWKS_URL": "typo"}, clear=True):
        settings = Settings(_env_file=None)  # type: ignore
        # The real setting keeps its default; the typo is not attached.
        assert settings.OAUTH_JWKS_URI is None
        assert not hasattr(settings, "OAUTH_JWKS_URL")


def test_password_is_secret_and_url_redacted() -> None:
    """Password is a SecretStr and DATABASE_URL never dumps (S4)."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(
            _env_file=None,  # type: ignore
            POSTGRES_PASSWORD=SecretStr("topsecret"),
        )
        assert isinstance(settings.POSTGRES_PASSWORD, SecretStr)
        assert settings.POSTGRES_PASSWORD.get_secret_value() == "topsecret"
        # The credential still flows into the real connection URL...
        assert "topsecret" in str(settings.DATABASE_URL)
        # ...but never into a dump or the OpenAPI schema.
        dumped = settings.model_dump()
        assert "DATABASE_URL" not in dumped
        assert "topsecret" not in str(dumped)
