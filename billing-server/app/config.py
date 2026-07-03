"""
Application configuration via pydantic-settings.
All values are loaded from environment variables / .env file.
"""
from functools import lru_cache

from pydantic import PostgresDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────
    app_version: str = "0.1.0"
    environment: str = "development"          # development | staging | production
    debug: bool = False
    log_level: str = "INFO"

    # ── Database ───────────────────────────────────────────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "billing"
    postgres_user: str = "billing"
    postgres_password: str = ""

    # Built lazily from components so individual vars are composable
    database_url: str = ""

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        if not self.database_url:
            self.database_url = (
                f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        return self

    @property
    def database_url_safe(self) -> str:
        """URL with password redacted for logging."""
        return self.database_url.replace(self.postgres_password, "***")

    # ── Server ─────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8080

    # ── Security ───────────────────────────────────────────────────────────
    secret_key: str = "CHANGE_ME_BEFORE_PRODUCTION"
    jwt_issuer: str = "RealityTunnel Billing/Auth"
    jwt_audience: str = "RealityTunnel Client"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
