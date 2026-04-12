import importlib
import os
from unittest.mock import patch

from app.core.config import Environment, Settings


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
        POSTGRES_PASSWORD="mypass",
        POSTGRES_DB="mydb",
    )
    db_url = str(settings.DATABASE_URL)
    assert "postgresql+asyncpg" in db_url
    assert "myhost" in db_url
    assert "5433" in db_url
    assert "myuser" in db_url
    assert "mydb" in db_url
