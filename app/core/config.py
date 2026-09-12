import os
from enum import StrEnum
from typing import Literal

import structlog
from pydantic import PostgresDsn, SecretStr, field_validator
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger(__name__)


class Environment(StrEnum):
    """Application environment."""

    development = "development"
    test = "test"
    production = "production"


#: Supported `QUOIN_LOG_LEVEL` values; case-insensitive on input.
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

# Only QUOIN_ENV is read. A bare ENV would select a different env file
# while Settings.ENV below stayed "development", skipping the production
# fail-fast checks and docs-disable guard that key off it.
env = Environment(os.getenv("QUOIN_ENV", Environment.development))

# Select env file based on environment
match env:
    case Environment.test:
        env_file = ".env.test"
    case Environment.production:
        env_file = ".env.production"
    case _:
        env_file = ".env"


#: Development-only Host allow-list. A production boot that still
#: carries these has not set `QUOIN_ALLOWED_HOSTS`, and would 400 every
#: real request — see `validate_production_settings`.
DEFAULT_ALLOWED_HOSTS = ("localhost", "127.0.0.1", "test", "*.orb.local")

#: Development-only CORS origins, warned about on a production boot.
DEFAULT_CORS_ORIGINS = ("http://localhost:3000", "http://localhost:8000")

#: Host substrings that mark an origin as local-development-only.
_LOCAL_ORIGIN_MARKERS = ("localhost", "127.0.0.1", "[::1]")


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_prefix="quoin_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_file=env_file,
        env_ignore_empty=True,
        extra="ignore",
    )

    # Application
    ENV: Environment = Environment.development
    LOG_LEVEL: LogLevel = "INFO"
    ACCESS_LOG_ENABLED: bool = True
    OTEL_ENABLED: bool = True
    REQUEST_ID_HEADER: str = "X-Request-ID"
    REQUEST_TIMEOUT_SECONDS: float = 30.0
    SHUTDOWN_DRAIN_TIMEOUT: float = 30.0

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> object:
        """Upper-case the log level so `debug` is accepted as `DEBUG`.

        Pydantic matches a `Literal` exactly, and `settings` is built at
        import time, so an unmatched case would crash anything importing
        this module — Alembic included. Genuine typos still fail.

        Args:
            value: The raw value from the environment or an `.env` file.

        Returns:
            The upper-cased value if it is a string, else unchanged.
        """
        return value.upper() if isinstance(value, str) else value

    # Database
    POSTGRES_DRIVER: str = "postgresql+asyncpg"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: SecretStr = SecretStr("postgres")
    POSTGRES_DB: str = "app_db"

    # Database connection pool — the first knobs any real deployment
    # tunes. Promoted out of the hardcoded engine defaults.
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: float = 30.0  # seconds to wait for a checked-out conn
    DB_POOL_RECYCLE: int = 1800  # recycle conns older than N s; -1 disables
    DB_POOL_PRE_PING: bool = True

    @property
    def DATABASE_URL(self) -> PostgresDsn:  # noqa: N802
        """Assemble the database URL.

        A plain ``@property`` (not a ``@computed_field``) so the
        credential-bearing URL is never emitted by ``model_dump()``,
        the OpenAPI schema, or any future config-dump endpoint. The
        password itself is a ``SecretStr`` and is redacted in dumps.
        """
        return MultiHostUrl.build(  # type: ignore
            scheme=self.POSTGRES_DRIVER,
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(),
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    ALLOWED_HOSTS: list[str] = list(DEFAULT_ALLOWED_HOSTS)
    BACKEND_CORS_ORIGINS: list[str] = list(DEFAULT_CORS_ORIGINS)
    BACKEND_CORS_ALLOW_METHODS: list[str] = [
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ]
    # REQUEST_ID_HEADER is added to both header lists when CORS is
    # configured, so renaming it needs no CORS change.
    BACKEND_CORS_ALLOW_HEADERS: list[str] = [
        "Authorization",
        "Content-Type",
    ]
    # Response headers a browser script may read; the rest stay hidden.
    BACKEND_CORS_EXPOSE_HEADERS: list[str] = ["Deprecation", "Sunset", "Link"]
    BACKEND_CORS_ALLOW_CREDENTIALS: bool = True

    # Security headers
    SECURITY_HEADERS_ENABLED: bool = True
    SECURITY_HSTS_MAX_AGE: int = 31_536_000
    SECURITY_HSTS_INCLUDE_SUBDOMAINS: bool = True
    SECURITY_HSTS_PRELOAD: bool = False
    SECURITY_CSP: str = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com"
        " https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' https://cdn.simpleicons.org"
        " https://fastapi.tiangolo.com; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    )
    # Swagger UI bootstraps itself from an inline <script> that FastAPI
    # generates and draws its toolbar icons from data: URIs, so /docs
    # cannot be served under the default policy. Scoped to that one
    # path by SecurityHeadersMiddleware, and moot in production, where
    # the docs routes are not registered at all.
    SECURITY_CSP_DOCS: str = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com"
        " https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https://cdn.simpleicons.org"
        " https://fastapi.tiangolo.com; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    )
    # ReDoc needs no inline script, but it renders anchor icons from
    # data: URIs, pulls its "powered by" logo from cdn.redoc.ly, and
    # builds its search index in a blob: worker (which falls back to
    # script-src when worker-src is unset). Same path scoping, same
    # production irrelevance, as SECURITY_CSP_DOCS above.
    SECURITY_CSP_REDOC: str = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com"
        " https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https://cdn.simpleicons.org"
        " https://fastapi.tiangolo.com https://cdn.redoc.ly; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "worker-src 'self' blob:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    )
    SECURITY_REFERRER_POLICY: str = "strict-origin-when-cross-origin"
    SECURITY_PERMISSIONS_POLICY: str = (
        "geolocation=(), camera=(), microphone=()"
    )

    # Request size limit (in bytes); <=0 disables the cap
    MAX_REQUEST_BODY_BYTES: int = 1_048_576  # 1 MiB

    # OAuth 2.0 / OIDC
    OAUTH_JWKS_URI: str | None = None
    OAUTH_ISSUER: str | None = None
    OAUTH_AUDIENCE: str | None = None
    OAUTH_ROLES_CLAIM: str = "roles"
    # Role that bypasses every require_roles() check, and the switch
    # that turns the bypass off for deployments whose IdP might issue
    # this role name to callers that should not hold global authority.
    # A separate flag rather than an empty role name, because
    # `env_ignore_empty` above makes an empty env value mean "unset".
    OAUTH_SUPERUSER_ROLE: str = "api.superuser"
    OAUTH_SUPERUSER_ENABLED: bool = True
    # Minimum seconds between JWKS refetches triggered by an unknown
    # kid — bounds outbound calls when tokens with garbage kids are
    # sprayed (negative cache / backoff).
    OAUTH_JWKS_MIN_REFRESH_SECONDS: float = 30.0

    # Outbound HTTP client (finer backoff/breaker/pool tuning lives as
    # constants in app/http/client.py)
    HTTP_TIMEOUT_SECONDS: float = 10.0
    HTTP_RETRY_ATTEMPTS: int = 3


settings = Settings()


def validate_production_settings(s: Settings = settings) -> None:
    """Fail fast on a misconfigured production deployment.

    In ``production`` the OAuth trust anchors must all be present and
    the JWKS endpoint must be ``https://`` — otherwise an on-path
    attacker could substitute signing keys — and ``ALLOWED_HOSTS`` must
    be set explicitly, because the development default rejects every
    real Host with a 400 and so reads as an outage rather than as the
    config error it is. Called from ``create_app()`` (not on import) so
    the API server crash-loops on a misconfigured boot while data-plane
    tooling that only imports settings — Alembic migrations, scripts —
    is unaffected. Development and test are no-ops.

    Localhost CORS origins are warned about rather than rejected: they
    are a smell in production but harmless on their own, and a deployment
    may legitimately keep one for a bastion.

    Args:
        s: The settings instance to validate (defaults to the module
            singleton; injectable for tests).

    Raises:
        RuntimeError: If production is missing any OAuth trust anchor,
            the JWKS URI is not ``https://``, or ``ALLOWED_HOSTS`` is
            unset.
    """
    if s.ENV != Environment.production:
        return

    _validate_production_oauth(s)
    _validate_production_hosts(s)
    _warn_on_local_cors_origins(s)


def _validate_production_oauth(s: Settings) -> None:
    """Require a complete, https OAuth trust anchor.

    Args:
        s: The settings instance to validate.

    Raises:
        RuntimeError: If a trust anchor is missing or JWKS is not https.
    """
    missing = [
        name
        for name, value in (
            ("QUOIN_OAUTH_JWKS_URI", s.OAUTH_JWKS_URI),
            ("QUOIN_OAUTH_ISSUER", s.OAUTH_ISSUER),
            ("QUOIN_OAUTH_AUDIENCE", s.OAUTH_AUDIENCE),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Production requires OAuth to be fully configured; "
            f"missing: {', '.join(missing)}."
        )
    if not s.OAUTH_JWKS_URI.startswith("https://"):  # type: ignore
        raise RuntimeError(
            "QUOIN_OAUTH_JWKS_URI must use https:// in production "
            "to prevent signing-key substitution."
        )


def _validate_production_hosts(s: Settings) -> None:
    """Require an explicit Host allow-list in production.

    Args:
        s: The settings instance to validate.

    Raises:
        RuntimeError: If ``ALLOWED_HOSTS`` is empty or still the
            development default.
    """
    if not s.ALLOWED_HOSTS or tuple(s.ALLOWED_HOSTS) == DEFAULT_ALLOWED_HOSTS:
        raise RuntimeError(
            "Production requires an explicit QUOIN_ALLOWED_HOSTS; the "
            "development default rejects every real Host header with a "
            "400. Set it to the hostnames this service is served on."
        )


def _warn_on_local_cors_origins(s: Settings) -> None:
    """Log a warning for any localhost CORS origin in production.

    Args:
        s: The settings instance to inspect.
    """
    local = [
        origin
        for origin in s.BACKEND_CORS_ORIGINS
        if any(marker in origin for marker in _LOCAL_ORIGIN_MARKERS)
    ]
    if local:
        logger.warning(
            "production_local_cors_origins",
            origins=local,
            hint="Set QUOIN_BACKEND_CORS_ORIGINS to the real browser "
            "origins, or an empty list if no browser calls this API.",
        )
