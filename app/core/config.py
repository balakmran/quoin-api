import os
from enum import StrEnum

from pydantic import PostgresDsn, SecretStr
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Application environment."""

    development = "development"
    test = "test"
    production = "production"


# Resolve environment before Settings loads
env = Environment(
    os.getenv("QUOIN_ENV", os.getenv("ENV", Environment.development))
)

# Select env file based on environment
match env:
    case Environment.test:
        env_file = ".env.test"
    case Environment.production:
        env_file = ".env.production"
    case _:
        env_file = ".env"


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
    LOG_LEVEL: str = "INFO"
    OTEL_ENABLED: bool = True
    REQUEST_ID_HEADER: str = "X-Request-ID"
    REQUEST_TIMEOUT_SECONDS: float = 30.0
    SHUTDOWN_DRAIN_TIMEOUT: float = 30.0

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

    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1", "test", "*.orb.local"]
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]
    BACKEND_CORS_ALLOW_METHODS: list[str] = [
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ]
    BACKEND_CORS_ALLOW_HEADERS: list[str] = [
        "Authorization",
        "Content-Type",
        "X-Request-ID",
    ]
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
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
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
    # Minimum seconds between JWKS refetches triggered by an unknown
    # kid — bounds outbound calls when tokens with garbage kids are
    # sprayed (negative cache / backoff).
    OAUTH_JWKS_MIN_REFRESH_SECONDS: float = 30.0

    # Outbound HTTP client (finer backoff/breaker/pool tuning lives as
    # constants in app/http/client.py)
    HTTP_TIMEOUT_SECONDS: float = 10.0
    HTTP_RETRY_ATTEMPTS: int = 3


settings = Settings()


def validate_production_oauth(s: Settings = settings) -> None:
    """Fail fast on a misconfigured production deployment.

    In ``production`` the OAuth trust anchors must all be present and
    the JWKS endpoint must be ``https://`` — otherwise an on-path
    attacker could substitute signing keys. Called from
    ``create_app()`` (not on import) so the API server crash-loops on a
    misconfigured boot while data-plane tooling that only imports
    settings — Alembic migrations, scripts — is unaffected. Development
    and test are no-ops.

    Args:
        s: The settings instance to validate (defaults to the module
            singleton; injectable for tests).

    Raises:
        RuntimeError: If production is missing any OAuth trust anchor or
            the JWKS URI is not ``https://``.
    """
    if s.ENV != Environment.production:
        return

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
