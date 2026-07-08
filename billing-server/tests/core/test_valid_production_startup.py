import pytest
from app.core.startup_validator import validate_startup_configuration
from app.config import Settings
import os

@pytest.fixture
def mock_valid_production_env(monkeypatch, tmp_path):
    # Minimal valid production configuration
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("POSTGRES_PASSWORD", "supersecret123")
    monkeypatch.setenv("MARZBAN_API_TOKEN", "valid_token")
    monkeypatch.setenv("JWT_SECRET", "12345678901234567890123456789012")
    
    # We must disable payments/webhooks unless we want to mock those secrets too
    monkeypatch.setenv("PAYMENTS_ENABLED", "false")
    monkeypatch.setenv("WEBHOOKS_ENABLED", "false")
    
    # Needs redis in production
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    
    # Provide valid keys to satisfy requirements
    monkeypatch.setenv("SECRET_KEY", "super_secret_key_that_is_long_enough")
    monkeypatch.setenv("COOKIE_SIGNING_KEY", "super_secret_key_that_is_long_enough")
    monkeypatch.setenv("ENCRYPTION_KEY", "super_secret_key_that_is_long_enough")
    
    # We also need Ed25519 keys on disk. We can monkeypatch the check or create dummy files
    def mock_collect_missing(*args, **kwargs):
        return []
    
    monkeypatch.setattr("app.core.startup_validator.collect_missing_ed25519_key_files", mock_collect_missing)
    
    # Also bypass the actual key content checks (which require valid PEM)
    def mock_check_permissions(*args, **kwargs):
        return True, []
    monkeypatch.setattr("app.core.startup_validator._check_private_key_file_permissions", mock_check_permissions, raising=False)
    
    # Secret registry reads keys from disk in prod; mock it so it doesn't crash on read
    monkeypatch.setenv("JWT_PRIVATE_KEY", "dummy_private")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "dummy_public")
    monkeypatch.setenv("ADMIN_JWT_PRIVATE_KEY", "dummy_private")
    monkeypatch.setenv("ADMIN_JWT_PUBLIC_KEY", "dummy_public")
    
    yield

def test_valid_production_config_succeeds(mock_valid_production_env):
    report = validate_startup_configuration()
    
    # If it didn't raise ConfigurationError, it succeeded.
    assert report.status == "ok"
    assert len(report.warnings) == 0
