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

from pydantic import model_validator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application [Public Config / Development Only] ───────────────────────
    app_version: str = "1.0.0"  # [Public Config]
    git_commit: str = "unknown"  # [Public Config]
    build_date: str = "unknown"  # [Public Config]
    docker_image: str = "billing-server-billing-api:latest"  # [Public Config]
    environment: str = "development"  # [Development Only / Profile]: development | testing | staging | production
    debug: bool = False  # [Development Only]: Must be False in production
    log_level: str = "INFO"  # [Operational Parameter]

    # ── Database [Internal Config / Infrastructure Secret] ───────────────────
    postgres_host: str = "localhost"  # [Internal Config]
    postgres_port: int = 5432  # [Internal Config]
    postgres_db: str = "billing"  # [Internal Config]
    postgres_user: str = "billing"  # [Internal Config]
    postgres_password: SecretStr = SecretStr("")  # [Infrastructure Secret]: Redacted in logs

    # Built lazily from components so individual vars are composable
    database_url: SecretStr = SecretStr("")  # [Internal Config]

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        if not self.database_url.get_secret_value():
            pwd = self.postgres_password.get_secret_value()
            self.database_url = SecretStr(
                f"postgresql+asyncpg://{self.postgres_user}:{pwd}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        return self

    @property
    def database_url_safe(self) -> str:
        """URL with password redacted for logging [Internal Config]."""
        pwd = self.postgres_password.get_secret_value()
        db_url_str = self.database_url.get_secret_value()
        return (
            db_url_str.replace(pwd, "***")
            if pwd
            else db_url_str
        )

    # ── Server [Public Config] ─────────────────────────────────────────────
    host: str = "0.0.0.0"  # [Public Config]
    port: int = 8080  # [Public Config]

    # ── Security [Security Secret / Public Config] ───────────────────────────
    # secret_key is reserved for future HMAC-based operations (e.g., cookie signing).
    # In production, this MUST be overridden via environment variable SECRET_KEY.
    secret_key: SecretStr = SecretStr("CHANGE_ME_BEFORE_PRODUCTION")  # [Security Secret]
    jwt_issuer: str = "RealityTunnel Billing/Auth"  # [Public Config]
    jwt_audience: str = "RealityTunnel Client"  # [Public Config]
    admin_jwt_issuer: str = "RealityTunnel Admin"  # [Public Config]
    admin_jwt_audience: str = "RealityTunnel Admin Panel"  # [Public Config]

    # ── VPN Provisioning (Marzban Integration) [Internal Config / Secret] ────
    marzban_base_url: str = "http://localhost:8000"  # [Internal Config / Public ID]
    marzban_rpc_url: str | None = None  # [Internal Config] Backend-to-backend RPC url.
    marzban_api_token: SecretStr = SecretStr("")  # [Infrastructure Secret]
    marzban_timeout_seconds: float = 10.0  # [Operational Parameter]
    marzban_max_retries: int = 3  # [Operational Parameter]
    marzban_create_user_path: str = "/api/user"  # [Internal Config]
    marzban_get_user_path: str = "/api/user/{username}"  # [Internal Config]
    marzban_update_user_path: str = "/api/user/{username}"  # [Internal Config]
    marzban_delete_user_path: str = "/api/user/{username}"  # [Internal Config]
    marzban_reset_user_path: str = "/api/user/{username}/reset"  # [Internal Config]
    marzban_system_stats_path: str = "/api/system"  # [Internal Config]
    marzban_cert_path: str | None = None  # [Internal Config] path to Marzban's self-signed CA bundle if applicable

    # ── Payment Gateway (Razorpay Integration) [Internal Config / Secret] ────
    razorpay_key_id: str = ""  # [Internal Config / Public ID]
    razorpay_key_secret: SecretStr = SecretStr("")  # [Security Secret]
    razorpay_webhook_secret: SecretStr = SecretStr("")  # [Security Secret]
    razorpay_base_url: str = "https://api.razorpay.com/v1"  # [Internal Config]
    razorpay_timeout_seconds: float = 10.0  # [Operational Parameter]
    razorpay_max_retries: int = 3  # [Operational Parameter]
    razorpay_orders_path: str = "/orders"  # [Internal Config]
    razorpay_payments_path: str = "/payments/{payment_id}"  # [Internal Config]
    razorpay_refunds_path: str = "/payments/{payment_id}/refund"  # [Internal Config]

    # ── Observability & Monitoring [Operational Parameter / Config] ──────────
    log_format: str = "json"  # [Operational Parameter]: json | console
    log_sampling_rate: float = 1.0  # [Operational Parameter]: 1.0 = 100%, 0.1 = 10%
    slow_request_threshold_ms: float = (
        500.0  # [Operational Parameter]: threshold in milliseconds
    )
    metrics_auth_required: bool = (
        False  # [Security Config]: whether /metrics requires Admin JWT. Always True in production (enforced by validator).
    )

    # ── Rate Limiting & Abuse Protection [Operational Parameter / Security] ──
    rate_limit_enabled: bool = True  # [Operational Parameter]
    trust_proxy: bool = False  # [Security Config]: Trust X-Forwarded-For / X-Real-IP
    rate_limit_allow_localhost: bool = (
        False  # [Operational Parameter]: Configurable exemption
    )
    rate_limit_allow_internal_ips: bool = (
        False  # [Operational Parameter]: Configurable exemption
    )
    rate_limit_allow_healthchecks: bool = (
        True  # [Operational Parameter]: Configurable exemption
    )
    rate_limit_anonymous: str = "100/minute"  # [Operational Parameter]
    rate_limit_login: str = "10/minute"  # [Operational Parameter]
    rate_limit_login_account: str = "10/minute"  # [Operational Parameter]
    rate_limit_register: str = "5/minute"  # [Operational Parameter]
    rate_limit_refresh: str = "30/minute"  # [Operational Parameter]
    rate_limit_device_register: str = "20/hour"  # [Operational Parameter]
    rate_limit_admin_login: str = "5/minute"  # [Operational Parameter]
    rate_limit_admin_login_account: str = "5/minute"  # [Operational Parameter]
    rate_limit_admin_endpoints: str = "100/minute"  # [Operational Parameter]
    rate_limit_webhook: str = "unlimited"  # [Operational Parameter]
    rate_limit_health: str = "unlimited"  # [Operational Parameter]
    trusted_proxy_ips: str = ""  # [Security Config]: comma-separated trusted reverse-proxy IPs/CIDRs (e.g. "10.0.0.0/8,172.16.0.5"). Only consulted when trust_proxy=True.
    rate_limit_backend: str = "memory"  # [Operational Parameter]: memory | redis. Production requires "redis" (see startup_validator.py).

    # ── Redis (shared connection; currently backs the Redis rate limit storage backend) ──
    redis_url: str = "redis://localhost:6379/0"  # [Internal Config]

    # ── Phase 3.4 — Disaster Recovery & Backup Settings ───────────────────
    backup_directory: str = "./backups"  # [Operational Parameter]
    backup_retention_days: int = 30  # [Operational Parameter]
    backup_max_count: int = 50  # [Operational Parameter]
    backup_max_storage_mb: int = 1024  # [Operational Parameter]
    backup_compression_algorithm: str = "gzip"  # [Operational Parameter]

    # ── Phase 3.5 — Security Hardening & Production Defense Settings ──────────
    security_headers_enabled: bool = True  # [Operational Parameter]
    security_hsts: str = (
        "max-age=31536000; includeSubDomains; preload"  # [Operational Parameter]
    )
    security_csp: str = "default-src 'self'; frame-ancestors 'none'; form-action 'self'"  # [Operational Parameter]
    security_x_frame_options: str = "DENY"  # [Operational Parameter]
    security_x_content_type_options: str = "nosniff"  # [Operational Parameter]
    security_referrer_policy: str = (
        "strict-origin-when-cross-origin"  # [Operational Parameter]
    )
    security_permissions_policy: str = (
        "geolocation=(), microphone=(), camera=()"  # [Operational Parameter]
    )
    security_coop: str = "same-origin"  # [Operational Parameter]
    security_corp: str = "same-origin"  # [Operational Parameter]
    security_coep: str = "require-corp"  # [Operational Parameter]
    max_payload_size_bytes: int = 1048576  # [Operational Parameter] 1 MB default
    csrf_allowed_origins: str = "http://localhost:8080,http://127.0.0.1:8080"  # [Internal Config] comma-separated

    # ── Phase 3.6 — Performance, Scalability & Load Testing Settings ─────────
    db_pool_size: int = 5  # [Operational Parameter]
    db_max_overflow: int = 10  # [Operational Parameter]
    db_pool_timeout: float = 30.0  # [Operational Parameter]
    db_pool_recycle: int = 1800  # [Operational Parameter] 30 minutes
    db_pool_pre_ping: bool = True  # [Operational Parameter]
    cache_enabled: bool = True  # [Operational Parameter]
    cache_backend: str = "memory"  # [Operational Parameter] memory | redis
    cache_ttl_seconds: int = 300  # [Operational Parameter] 5 minutes default
    profiler_enabled: bool = True  # [Operational Parameter]
    slow_query_threshold_ms: float = 200.0  # [Operational Parameter]

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.environment.lower() == "production":
            if self.secret_key.get_secret_value() == "CHANGE_ME_BEFORE_PRODUCTION":
                raise RuntimeError(
                    "SECRET_KEY must be set to a strong random value in production. "
                    "The default placeholder is not permitted."
                )
            # M-6: Metrics endpoint must require authentication in production.
            if not self.metrics_auth_required:
                import warnings
                warnings.warn(
                    "metrics_auth_required is False in production — forcing to True. "
                    "Set METRICS_AUTH_REQUIRED=true explicitly to suppress this warning.",
                    stacklevel=2,
                )
                object.__setattr__(self, "metrics_auth_required", True)
        return self

    @property
    def docs_url_effective(self) -> str | None:
        """M-7: Disable Swagger UI in production."""
        return None if self.environment.lower() == "production" else "/docs"

    @property
    def redoc_url_effective(self) -> str | None:
        """M-7: Disable ReDoc in production."""
        return None if self.environment.lower() == "production" else "/redoc"

    @property
    def openapi_url_effective(self) -> str | None:
        """M-7: Disable OpenAPI schema endpoint in production."""
        return None if self.environment.lower() == "production" else "/openapi.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
