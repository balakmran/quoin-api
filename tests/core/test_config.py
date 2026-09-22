import importlib
import os
from unittest.mock import patch

import pytest
from pydantic import SecretStr
from structlog.testing import capture_logs

from app.core.config import (
    DEFAULT_ALLOWED_HOSTS,
    Environment,
    Settings,
    validate_production_settings,
)


def test_environment_enum_values() -> None:
    """Test Environment enum has correct values."""
    assert Environment.development == "development"
    assert Environment.test == "test"
    assert Environment.production == "production"


def test_settings_defaults() -> None:
    """Test Settings default values."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None)
        assert settings.ENV == Environment.development
        assert settings.LOG_LEVEL == "INFO"
        assert settings.OTEL_ENABLED is True
        assert settings.POSTGRES_HOST == "localhost"
        assert settings.POSTGRES_PORT == 5432  # noqa: PLR2004


def test_db_pool_defaults() -> None:
    """Connection-pool settings expose the previous engine literals."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None)
        assert settings.DB_POOL_SIZE == 20  # noqa: PLR2004
        assert settings.DB_MAX_OVERFLOW == 10  # noqa: PLR2004
        assert settings.DB_POOL_TIMEOUT == 30.0  # noqa: PLR2004
        assert settings.DB_POOL_RECYCLE == 1800  # noqa: PLR2004
        assert settings.DB_POOL_PRE_PING is True


def test_db_pool_overrides_from_env() -> None:
    """QUOIN_DB_POOL_* env vars override the pool defaults."""
    with patch.dict(
        os.environ,
        {
            "QUOIN_DB_POOL_SIZE": "5",
            "QUOIN_DB_MAX_OVERFLOW": "0",
            "QUOIN_DB_POOL_PRE_PING": "false",
        },
        clear=True,
    ):
        settings = Settings()
        assert settings.DB_POOL_SIZE == 5  # noqa: PLR2004
        assert settings.DB_MAX_OVERFLOW == 0
        assert settings.DB_POOL_PRE_PING is False


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


def test_bare_env_var_is_ignored_for_file_selection() -> None:
    """B5 regression: a bare ENV must not select a different env file."""
    with patch.dict(os.environ, {"ENV": "production"}, clear=True):
        from app.core import config  # noqa: PLC0415

        importlib.reload(config)
        assert config.env == Environment.development
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
    """Build a valid production Settings, no env file."""
    base: dict[str, object] = {
        "_env_file": None,
        "ENV": Environment.production,
        "OAUTH_JWKS_URI": "https://issuer.example/jwks",
        "OAUTH_ISSUER": "https://issuer.example",
        "OAUTH_AUDIENCE": "api",
        "ALLOWED_HOSTS": ["api.example.com"],
        "BACKEND_CORS_ORIGINS": ["https://app.example.com"],
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore


def test_production_oauth_fully_configured_boots() -> None:
    """A fully-configured production profile validates clean (S3)."""
    with patch.dict(os.environ, {}, clear=True):
        validate_production_settings(_prod())  # no raise


@pytest.mark.parametrize(
    "missing",
    ["OAUTH_JWKS_URI", "OAUTH_ISSUER", "OAUTH_AUDIENCE"],
)
def test_production_missing_oauth_crash_loops(missing: str) -> None:
    """Production fails fast when any OAuth trust anchor is unset (S3)."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match=missing):
            validate_production_settings(_prod(**{missing: None}))


def test_production_requires_https_jwks() -> None:
    """Production rejects a non-https JWKS URI (S7)."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="https"):
            validate_production_settings(
                _prod(OAUTH_JWKS_URI="http://issuer.example/jwks")
            )


def test_production_requires_explicit_allowed_hosts() -> None:
    """Production rejects the development Host allow-list (S5)."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="QUOIN_ALLOWED_HOSTS"):
            validate_production_settings(
                _prod(ALLOWED_HOSTS=list(DEFAULT_ALLOWED_HOSTS))
            )


def test_production_rejects_empty_allowed_hosts() -> None:
    """An empty Host allow-list is a config error, not a lockdown (S5)."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="QUOIN_ALLOWED_HOSTS"):
            validate_production_settings(_prod(ALLOWED_HOSTS=[]))


def test_production_warns_on_localhost_cors_origin() -> None:
    """Localhost CORS origins warn in production but still boot (S5)."""
    with patch.dict(os.environ, {}, clear=True), capture_logs() as cap_logs:
        validate_production_settings(
            _prod(
                BACKEND_CORS_ORIGINS=[
                    "https://app.example.com",
                    "http://localhost:3000",
                ]
            )
        )
    warnings = [
        log
        for log in cap_logs
        if log["event"] == "production_local_cors_origins"
    ]
    assert len(warnings) == 1
    assert warnings[0]["origins"] == ["http://localhost:3000"]


def test_production_silent_on_remote_cors_origins() -> None:
    """A production-only CORS list emits no warning (S5)."""
    with patch.dict(os.environ, {}, clear=True), capture_logs() as cap_logs:
        validate_production_settings(_prod())
    assert not [
        log
        for log in cap_logs
        if log["event"] == "production_local_cors_origins"
    ]


def test_production_warns_on_default_database_password() -> None:
    """The development DB password warns in production but still boots."""
    with patch.dict(os.environ, {}, clear=True), capture_logs() as cap_logs:
        validate_production_settings(_prod())
    events = [log["event"] for log in cap_logs]
    assert events.count("production_default_database_password") == 1


def test_production_warns_on_superuser_bypass() -> None:
    """An enabled superuser bypass warns in production but still boots."""
    with patch.dict(os.environ, {}, clear=True), capture_logs() as cap_logs:
        validate_production_settings(_prod(OAUTH_SUPERUSER_ENABLED=True))
    events = [log["event"] for log in cap_logs]
    assert events.count("production_superuser_bypass_enabled") == 1


def test_production_silent_when_superuser_bypass_is_off() -> None:
    """The default (bypass off) emits no warning."""
    with patch.dict(os.environ, {}, clear=True), capture_logs() as cap_logs:
        validate_production_settings(_prod())
    events = [log["event"] for log in cap_logs]
    assert "production_superuser_bypass_enabled" not in events


def test_production_silent_on_a_real_database_password() -> None:
    """A password other than the default emits no warning."""
    with patch.dict(os.environ, {}, clear=True), capture_logs() as cap_logs:
        validate_production_settings(_prod(POSTGRES_PASSWORD="a-real-one"))
    events = [log["event"] for log in cap_logs]
    assert "production_default_database_password" not in events


def test_superuser_bypass_is_configurable() -> None:
    """The bypass role and its on/off switch are both settings (S3).

    A flag rather than an empty role name because `env_ignore_empty`
    makes an empty env value mean "unset", not "disabled".
    """
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None)
        assert settings.OAUTH_SUPERUSER_ROLE == "api.superuser"
        assert settings.OAUTH_SUPERUSER_ENABLED is False
    with patch.dict(
        os.environ,
        {
            "QUOIN_OAUTH_SUPERUSER_ROLE": "ops.break_glass",
            "QUOIN_OAUTH_SUPERUSER_ENABLED": "true",
        },
        clear=True,
    ):
        settings = Settings(_env_file=None)
        assert settings.OAUTH_SUPERUSER_ROLE == "ops.break_glass"
        assert settings.OAUTH_SUPERUSER_ENABLED is True


def test_default_csp_forbids_inline_scripts() -> None:
    """The default policy allows no inline script; only /docs does (S6)."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None)
    script_src = next(
        d
        for d in settings.SECURITY_CSP.split("; ")
        if d.startswith("script-src")
    )
    assert "'unsafe-inline'" not in script_src
    assert "'unsafe-inline'" in settings.SECURITY_CSP_DOCS


def test_default_csp_names_no_third_party_host() -> None:
    """Only the scoped policies allow CDNs; the default allows none."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None)
    assert "https://" not in settings.SECURITY_CSP
    assert "script-src 'self';" in settings.SECURITY_CSP_HOME
    assert "https://cdn.simpleicons.org" in settings.SECURITY_CSP_HOME
    assert "cdn.jsdelivr.net" not in settings.SECURITY_CSP_HOME
    assert "cdn.jsdelivr.net" in settings.SECURITY_CSP_DOCS


def test_development_skips_oauth_validation() -> None:
    """Development is a no-op even with no OAuth configured (S3)."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None, ENV=Environment.development)
        validate_production_settings(settings)  # no raise
        assert settings.OAUTH_ISSUER is None


def test_unknown_quoin_var_is_ignored() -> None:
    """A mistyped QUOIN_* var is dropped, not accepted as extra (S5)."""
    with patch.dict(os.environ, {"QUOIN_OAUTH_JWKS_URL": "typo"}, clear=True):
        settings = Settings(_env_file=None)
        # The real setting keeps its default; the typo is not attached.
        assert settings.OAUTH_JWKS_URI is None
        assert not hasattr(settings, "OAUTH_JWKS_URL")


def test_password_is_secret_and_url_redacted() -> None:
    """Password is a SecretStr and DATABASE_URL never dumps (S4)."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(
            _env_file=None,
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
