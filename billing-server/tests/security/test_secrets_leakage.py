import logging
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.core.redaction import redact_string
from app.routers.auth_models import LoginRequest


def test_settings_secret_str_repr():
    """Verify that settings repr masks secrets."""
    settings = Settings(
        postgres_password="SUPER_SECRET_DB_PASSWORD",
        secret_key="SUPER_SECRET_KEY",
        marzban_api_token="SUPER_SECRET_MARZBAN",
        razorpay_key_secret="SUPER_SECRET_RAZORPAY",
        razorpay_webhook_secret="SUPER_SECRET_WEBHOOK"
    )
    settings_repr = repr(settings)
    settings_str = str(settings)

    assert "**********" in settings_repr
    assert "SUPER_SECRET_DB_PASSWORD" not in settings_repr
    assert "SUPER_SECRET_KEY" not in settings_repr
    assert "SUPER_SECRET_MARZBAN" not in settings_repr
    
    assert "**********" in settings_str
    assert "SUPER_SECRET_DB_PASSWORD" not in settings_str
    assert "SUPER_SECRET_KEY" not in settings_str


def test_auth_model_secret_str():
    """Verify that LoginRequest master_token is a SecretStr and masks in repr/dump."""
    req = LoginRequest(
        account_id="RT-1234",
        master_token="THIS_IS_THE_MASTER_TOKEN",
        device_guid="DEVICE-123",
        client_type="desktop"
    )
    req_repr = repr(req)
    assert "**********" in req_repr
    assert "THIS_IS_THE_MASTER_TOKEN" not in req_repr
    
    dump = req.model_dump()
    # Pydantic v2 model_dump with SecretStr dumps the SecretStr object, which reprs to **********
    assert "THIS_IS_THE_MASTER_TOKEN" not in str(dump)


def test_redact_string_dynamic_secrets(monkeypatch):
    """Verify that redact_string dynamically pulls secrets from Settings and redacts them."""
    # We patch settings dynamically
    from app.config import settings
    monkeypatch.setattr(settings.postgres_password, "_secret_value", "UNIQUE_DB_PASS_123")
    monkeypatch.setattr(settings.secret_key, "_secret_value", "UNIQUE_SECRET_KEY_456")
    
    # Test a string that would normally be logged
    raw_log_message = "Failed to connect to db with password UNIQUE_DB_PASS_123 and key UNIQUE_SECRET_KEY_456!"
    
    redacted_message = redact_string(raw_log_message)
    
    assert "UNIQUE_DB_PASS_123" not in redacted_message
    assert "UNIQUE_SECRET_KEY_456" not in redacted_message
    assert "***REDACTED***" in redacted_message
    assert "Failed to connect to db with password" in redacted_message


def test_redact_string_regexes():
    """Verify that regex redaction works for JWTs, bearer tokens, etc."""
    raw_log = "Error validating Bearer 1234567890abcdef. Also jwt eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c failed."
    redacted = redact_string(raw_log)
    
    assert "1234567890abcdef" not in redacted
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted
    assert "***REDACTED***" in redacted
