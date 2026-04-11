import os
from enum import StrEnum

from pydantic import PostgresDsn, computed_field
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
        extra="allow",
    )

    # Application
    ENV: Environment = Environment.development
    LOG_LEVEL: str = "INFO"
    OTEL_ENABLED: bool = True

    # Database
    POSTGRES_DRIVER: str = "postgresql+asyncpg"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "app_db"

    @computed_field
    @property
    def DATABASE_URL(self) -> PostgresDsn:
        """Assemble the database URL."""
        return MultiHostUrl.build(  # type: ignore[return-value]
            scheme=self.POSTGRES_DRIVER,
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1", "test", "*.orb.local"]
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]


settings = Settings()
