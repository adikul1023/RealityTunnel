"""
tests/core/test_configuration_hardening.py — Automated tests for Phase 3.1 Configuration Hardening.

Covers:
  - Missing and invalid JWT keys
  - Missing admin key
  - Missing DB URL
  - Explicit environment profile parsing & invalid environment rejection
  - Production placeholder secret rejection & debug mode rejection
  - Localhost callback rejection in production
  - Feature flag parsing
  - Fingerprint generation (verifying zero secrets leak)
  - Redaction utility (strings, data structures, and logging formatter)
  - Startup validator report and fail-fast exception raising
"""
import logging
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from app.config import Settings
from app.core.profiles import EnvironmentProfile, parse_environment_profile
from app.core.feature_flags import FeatureFlags
from app.core.redaction import redact_string, redact_data, is_sensitive_key, RedactingFormatter, REDACTED_STR
from app.core.secret_registry import secret_registry, SecretDefinition
from app.core.fingerprint import compute_configuration_fingerprint
from app.core.startup_validator import validate_startup_configuration, ConfigurationError, ConfigurationReport


# ── 1. Environment Profiles Tests ─────────────────────────────────────────────

def test_environment_profiles():
    assert parse_environment_profile("development") == EnvironmentProfile.DEVELOPMENT
    assert parse_environment_profile("TESTING") == EnvironmentProfile.TESTING
    assert parse_environment_profile(" staging ") == EnvironmentProfile.STAGING
    assert parse_environment_profile("production") == EnvironmentProfile.PRODUCTION

    assert EnvironmentProfile.PRODUCTION.is_production is True
    assert EnvironmentProfile.DEVELOPMENT.is_production is False

    with pytest.raises(ValueError, match="must be explicitly set"):
        parse_environment_profile("")

    with pytest.raises(ValueError, match="Invalid environment profile"):
        parse_environment_profile("prod-local")

    with pytest.raises(ValueError, match="No implicit profile inference is permitted"):
        parse_environment_profile("unknown_env")


# ── 2. Feature Flags Tests ───────────────────────────────────────────────────

def test_feature_flag_parsing():
    env_mock = {
        "PAYMENTS_ENABLED": "false",
        "PROVISIONING_ENABLED": "0",
        "WEBHOOKS_ENABLED": "no",
        "ADMIN_API_ENABLED": "true",
        "BACKGROUND_JOBS_ENABLED": "1",
        "METRICS_ENABLED": "yes",
    }
    flags = FeatureFlags.from_env(env_mock)
    assert flags.payments_enabled is False
    assert flags.provisioning_enabled is False
    assert flags.webhooks_enabled is False
    assert flags.admin_api_enabled is True
    assert flags.background_jobs_enabled is True
    assert flags.metrics_enabled is True

    flags_dict = flags.to_dict()
    assert flags_dict["PAYMENTS_ENABLED"] is False
    assert flags_dict["ADMIN_API_ENABLED"] is True


# ── 3. Redaction Utility Tests ───────────────────────────────────────────────

def test_redaction_utility():
    assert is_sensitive_key("user_password") is True
    assert is_sensitive_key("jwt_private_key") is True
    assert is_sensitive_key("marzban_api_token") is True
    assert is_sensitive_key("database_url") is False
    assert is_sensitive_key("app_version") is False

    # String redaction
    url_test = "postgresql://billing:SuperSecretPass123@localhost:5432/billing"
    redacted_url = redact_string(url_test)
    assert "SuperSecretPass123" not in redacted_url
    assert REDACTED_STR in redacted_url
    assert "billing" in redacted_url

    bearer_test = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    redacted_bearer = redact_string(bearer_test)
    assert "eyJhbGciOi" not in redacted_bearer
    assert REDACTED_STR in redacted_bearer

    key_val_test = "secret_key = 'my-super-secret-key-value'"
    redacted_kv = redact_string(key_val_test)
    assert "my-super-secret-key-value" not in redacted_kv
    assert REDACTED_STR in redacted_kv

    # Data structure redaction
    data_test = {
        "account_id": "acc-123",
        "marzban_api_token": "token-xyz-987",
        "nested": {
            "password": "plain-text-pass",
            "host": "localhost",
        },
        "list_items": ["safe-item", "secret_key=abcd"],
    }
    redacted_data = redact_data(data_test)
    assert redacted_data["account_id"] == "acc-123"
    assert redacted_data["marzban_api_token"] == REDACTED_STR
    assert redacted_data["nested"]["password"] == REDACTED_STR
    assert redacted_data["nested"]["host"] == "localhost"
    assert REDACTED_STR in redacted_data["list_items"][1]

    # Logging formatter test
    formatter = RedactingFormatter("%(message)s")
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="Connecting to postgresql://user:secretpass@localhost:5432/db",
        args=(), exc_info=None,
    )
    formatted_msg = formatter.format(record)
    assert "secretpass" not in formatted_msg
    assert REDACTED_STR in formatted_msg


# ── 4. Configuration Fingerprint Tests ────────────────────────────────────────

def test_fingerprint_generation():
    settings = Settings(
        environment="staging",
        app_version="1.2.3",
        debug=False,
        razorpay_key_id="rzp_live_123",
        marzban_base_url="https://vpn.example.com",
    )
    flags = FeatureFlags(payments_enabled=True, provisioning_enabled=True)
    fingerprint = compute_configuration_fingerprint(settings, flags)

    assert fingerprint["environment"] == "staging"
    assert fingerprint["version"] == "1.2.3"
    assert "razorpay" in fingerprint["enabled_providers"]
    assert "marzban" in fingerprint["enabled_providers"]
    assert fingerprint["debug_mode"] is False

    # Assure zero secrets leak in fingerprint
    fp_str = str(fingerprint)
    assert "rzp_live_123" not in fp_str
    assert "secret" not in fp_str.lower()
    assert "password" not in fp_str.lower()


# ── 5. Startup Validator & Production Guard Tests ─────────────────────────────

def test_startup_validator_success_development():
    settings = Settings(
        environment="development",
        postgres_host="localhost",
        postgres_user="user",
        postgres_db="db",
        postgres_password="pass",
        database_url="postgresql+asyncpg://user:pass@localhost/db",
    )
    flags = FeatureFlags(payments_enabled=False, provisioning_enabled=False)
    report = validate_startup_configuration(settings, flags)
    assert report.status == "ok"
    assert report.checks["Database"] is True


def test_missing_db_url():
    settings = Settings(
        environment="development",
        postgres_host="",
        database_url="",
    )
    flags = FeatureFlags(payments_enabled=False, provisioning_enabled=False)
    with pytest.raises(ConfigurationError, match="Database URL or connection credentials incomplete"):
        validate_startup_configuration(settings, flags)


def test_missing_and_invalid_jwt_keys_in_production():
    settings = Settings(
        environment="production",
        debug=False,
        secret_key="A_very_strong_random_secret_key_1234567890",
        postgres_host="localhost", postgres_user="u", postgres_db="db", postgres_password="p",
        database_url="postgresql+asyncpg://u:p@localhost/db",
        marzban_base_url="https://vpn.example.com",
    )
    flags = FeatureFlags(payments_enabled=False, provisioning_enabled=False)

    # Mock secret registry get to simulate missing customer JWT keys
    with patch.object(secret_registry, "get", side_effect=lambda k: None if "jwt" in k else "dummy"):
        with pytest.raises(ConfigurationError, match="Customer JWT Ed25519 signing keypair missing or invalid"):
            validate_startup_configuration(settings, flags)


def test_missing_admin_key_in_production():
    settings = Settings(
        environment="production",
        debug=False,
        secret_key="A_very_strong_random_secret_key_1234567890",
        postgres_host="localhost", postgres_user="u", postgres_db="db", postgres_password="p",
        database_url="postgresql+asyncpg://u:p@localhost/db",
        marzban_base_url="https://vpn.example.com",
    )
    flags = FeatureFlags(payments_enabled=False, provisioning_enabled=False)

    # Mock secret registry get to simulate valid customer JWT but missing admin JWT keys
    def mock_get(key: str):
        if key in ("jwt_private_key", "jwt_public_key"):
            return "BEGIN PRIVATE KEY\n...\nEND PRIVATE KEY"
        if key in ("admin_jwt_private_key", "admin_jwt_public_key"):
            return None
        return "dummy"

    with patch.object(secret_registry, "get", side_effect=mock_get):
        with pytest.raises(ConfigurationError, match="Admin JWT Ed25519 signing keypair missing or invalid"):
            validate_startup_configuration(settings, flags)


def test_production_placeholder_rejection():
    # 1. Test rejection of default secret_key placeholder by Settings model validator
    with pytest.raises(RuntimeError, match="SECRET_KEY must be set to a strong random value"):
        Settings(
            environment="production",
            debug=False,
            secret_key="CHANGE_ME_BEFORE_PRODUCTION",
            postgres_host="localhost", postgres_user="u", postgres_db="db", postgres_password="p",
            database_url="postgresql+asyncpg://u:p@localhost/db",
            marzban_base_url="https://vpn.example.com",
        )

    # 2. Test rejection of short (<32 chars) secret keys by startup validator
    settings = Settings(
        environment="production",
        debug=False,
        secret_key="too_short_key_12345",
        postgres_host="localhost", postgres_user="u", postgres_db="db", postgres_password="p",
        database_url="postgresql+asyncpg://u:p@localhost/db",
        marzban_base_url="https://vpn.example.com",
    )
    flags = FeatureFlags(payments_enabled=False, provisioning_enabled=False)

    with patch.object(secret_registry, "get", return_value="BEGIN KEY\n...\nEND KEY"):
        with pytest.raises(ConfigurationError, match="secret_key is default, short"):
            validate_startup_configuration(settings, flags)


def test_production_debug_mode_rejection():
    settings = Settings(
        environment="production",
        debug=True,
        secret_key="A_very_strong_random_secret_key_1234567890",
        postgres_host="localhost", postgres_user="u", postgres_db="db", postgres_password="p",
        database_url="postgresql+asyncpg://u:p@localhost/db",
        marzban_base_url="https://vpn.example.com",
    )
    flags = FeatureFlags(payments_enabled=False, provisioning_enabled=False)

    with patch.object(secret_registry, "get", return_value="BEGIN KEY\n...\nEND KEY"):
        with pytest.raises(ConfigurationError, match="debug mode must be False in production"):
            validate_startup_configuration(settings, flags)


def test_production_localhost_callback_rejection():
    settings = Settings(
        environment="production",
        debug=False,
        secret_key="A_very_strong_random_secret_key_1234567890",
        postgres_host="localhost", postgres_user="u", postgres_db="db", postgres_password="p",
        database_url="postgresql+asyncpg://u:p@localhost/db",
        marzban_base_url="http://localhost:8000",
    )
    flags = FeatureFlags(payments_enabled=False, provisioning_enabled=True)

    with patch.object(secret_registry, "get", return_value="BEGIN KEY\n...\nEND KEY"):
        with pytest.raises(ConfigurationError, match="localhost or non-HTTPS gateway URLs prohibited"):
            validate_startup_configuration(settings, flags)


def test_production_test_keys_rejection():
    settings = Settings(
        environment="production",
        debug=False,
        secret_key="A_very_strong_random_secret_key_1234567890",
        postgres_host="localhost", postgres_user="u", postgres_db="db", postgres_password="p",
        database_url="postgresql+asyncpg://u:p@localhost/db",
        marzban_base_url="https://vpn.example.com",
        razorpay_key_id="rzp_test_123456",
        razorpay_key_secret="some_secret_key_value_here",
    )
    flags = FeatureFlags(payments_enabled=True, provisioning_enabled=False, webhooks_enabled=False)

    with patch.object(secret_registry, "get", return_value="BEGIN KEY\n...\nEND KEY"):
        with pytest.raises(ConfigurationError, match="test payment or webhook keys detected"):
            validate_startup_configuration(settings, flags)


def test_startup_validator_report():
    settings = Settings(
        environment="staging",
        debug=False,
        secret_key="Staging_strong_secret_key_value_9999",
        postgres_host="localhost", postgres_user="u", postgres_db="db", postgres_password="p",
        database_url="postgresql+asyncpg://u:p@localhost/db",
        marzban_base_url="https://vpn.staging.com",
    )
    flags = FeatureFlags(payments_enabled=False, provisioning_enabled=True)

    with patch.object(secret_registry, "get", return_value="BEGIN KEY\n...\nEND KEY"):
        report = validate_startup_configuration(settings, flags)
        assert report.status == "ok"
        report_str = report.to_string()
        assert "RealityTunnel Configuration Report" in report_str
        assert "✓ Database" in report_str
        assert "✓ Marzban Gateway" in report_str
        # Verify zero secrets in string output
        assert "Staging_strong" not in report_str


# ── 6. Health & Admin Endpoint Fingerprint Exposure Tests ─────────────────────

@pytest.mark.asyncio
async def test_health_endpoint_fingerprint_exposure(async_client, admin_user_factory):
    # 1. Unauthenticated request -> no fingerprint
    resp_anon = await async_client.get("/health")
    assert resp_anon.status_code in (200, 503)
    data_anon = resp_anon.json()
    assert data_anon.get("fingerprint") is None

    # 2. Authenticated Admin request -> fingerprint included
    password = "AdminPassword2026!"
    await admin_user_factory(username="health_admin", password=password, is_super_admin=True)
    login_resp = await async_client.post(
        "/api/admin/login",
        json={"username": "health_admin", "password": password},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp_admin = await async_client.get("/health", headers=headers)
    assert resp_admin.status_code in (200, 503)
    data_admin = resp_admin.json()
    assert data_admin.get("fingerprint") is not None
    assert "environment" in data_admin["fingerprint"]
    assert "version" in data_admin["fingerprint"]


@pytest.mark.asyncio
async def test_admin_system_health_endpoint_fingerprint(async_client, admin_user_factory):
    password = "AdminPassword2026!"
    await admin_user_factory(username="syshealth_admin", password=password, is_super_admin=True)
    login_resp = await async_client.post(
        "/api/admin/login",
        json={"username": "syshealth_admin", "password": password},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await async_client.get("/api/admin/system-health", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "fingerprint" in data and data["fingerprint"] is not None
    assert "enabled_providers" in data["fingerprint"]
