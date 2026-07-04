"""
Application configuration via pydantic-settings.
All values are loaded from environment variables / .env file.

── Phase 3.1.1 Configuration Classification Audit ─────────────────────────────
Every configuration parameter is categorized into one of the following domains:
  - [Public Config]: Safe to display or expose publicly (e.g., version, host, port).
  - [Internal Config]: System topology and routing (e.g., database URL, endpoint paths).
  - [Security Secret]: Cryptographic keys, HMAC tokens, and signing secrets.
  - [Infrastructure Secret]: Database passwords and external service tokens.
  - [Operational Parameter]: Tuning variables, timeouts, retries, and log levels.
  - [Development Only]: Local debugging flags prohibited in production environments.
───────────────────────────────────────────────────────────────────────────────
"""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application [Public Config / Development Only] ───────────────────────
    app_version: str = "0.1.0"                # [Public Config]
    environment: str = "development"          # [Development Only / Profile]: development | testing | staging | production
    debug: bool = False                       # [Development Only]: Must be False in production
    log_level: str = "INFO"                   # [Operational Parameter]

    # ── Database [Internal Config / Infrastructure Secret] ───────────────────
    postgres_host: str = "localhost"          # [Internal Config]
    postgres_port: int = 5432                 # [Internal Config]
    postgres_db: str = "billing"              # [Internal Config]
    postgres_user: str = "billing"            # [Internal Config]
    postgres_password: str = ""               # [Infrastructure Secret]: Redacted in logs

    # Built lazily from components so individual vars are composable
    database_url: str = ""                    # [Internal Config]

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
        """URL with password redacted for logging [Internal Config]."""
        return self.database_url.replace(self.postgres_password, "***") if self.postgres_password else self.database_url

    # ── Server [Public Config] ─────────────────────────────────────────────
    host: str = "0.0.0.0"                     # [Public Config]
    port: int = 8080                          # [Public Config]

    # ── Security [Security Secret / Public Config] ───────────────────────────
    # secret_key is reserved for future HMAC-based operations (e.g., cookie signing).
    # In production, this MUST be overridden via environment variable SECRET_KEY.
    secret_key: str = "CHANGE_ME_BEFORE_PRODUCTION"  # [Security Secret]
    jwt_issuer: str = "RealityTunnel Billing/Auth"   # [Public Config]
    jwt_audience: str = "RealityTunnel Client"       # [Public Config]
    admin_jwt_issuer: str = "RealityTunnel Admin"    # [Public Config]
    admin_jwt_audience: str = "RealityTunnel Admin Panel"  # [Public Config]

    # ── VPN Provisioning (Marzban Integration) [Internal Config / Secret] ────
    marzban_base_url: str = "http://localhost:8000"  # [Internal Config]
    marzban_api_token: str = ""               # [Infrastructure Secret]
    marzban_timeout_seconds: float = 10.0     # [Operational Parameter]
    marzban_max_retries: int = 3              # [Operational Parameter]
    marzban_create_user_path: str = "/api/user"              # [Internal Config]
    marzban_get_user_path: str = "/api/user/{username}"      # [Internal Config]
    marzban_update_user_path: str = "/api/user/{username}"   # [Internal Config]
    marzban_delete_user_path: str = "/api/user/{username}"   # [Internal Config]
    marzban_reset_user_path: str = "/api/user/{username}/reset"  # [Internal Config]
    marzban_system_stats_path: str = "/api/system"           # [Internal Config]

    # ── Payment Gateway (Razorpay Integration) [Internal Config / Secret] ────
    razorpay_key_id: str = ""                 # [Internal Config / Public ID]
    razorpay_key_secret: str = ""             # [Security Secret]
    razorpay_webhook_secret: str = ""         # [Security Secret]
    razorpay_base_url: str = "https://api.razorpay.com/v1"   # [Internal Config]
    razorpay_timeout_seconds: float = 10.0    # [Operational Parameter]
    razorpay_max_retries: int = 3             # [Operational Parameter]
    razorpay_orders_path: str = "/orders"                    # [Internal Config]
    razorpay_payments_path: str = "/payments/{payment_id}"   # [Internal Config]
    razorpay_refunds_path: str = "/payments/{payment_id}/refund"  # [Internal Config]

    # ── Observability & Monitoring [Operational Parameter / Config] ──────────
    log_format: str = "json"                  # [Operational Parameter]: json | console
    log_sampling_rate: float = 1.0            # [Operational Parameter]: 1.0 = 100%, 0.1 = 10%
    slow_request_threshold_ms: float = 500.0  # [Operational Parameter]: threshold in milliseconds
    metrics_auth_required: bool = False       # [Security Config]: whether /metrics requires Admin JWT

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.environment.lower() == "production":
            if self.secret_key == "CHANGE_ME_BEFORE_PRODUCTION":
                raise RuntimeError(
                    "SECRET_KEY must be set to a strong random value in production. "
                    "The default placeholder is not permitted."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
