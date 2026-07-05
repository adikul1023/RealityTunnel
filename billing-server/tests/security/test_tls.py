"""
test_tls.py — Unit tests for HTTPS and TLS validation enforcement (Phase 3.5).
"""
import pytest
from app.config import settings
from app.security_hardening.tls import validate_tls_url, get_secure_client_ssl_context
from app.security_hardening.exceptions import TLSValidationError
from app.observability.metrics import metrics_registry


def test_tls_url_validation_in_production(monkeypatch: pytest.MonkeyPatch):
    """Verify that insecure HTTP URLs are rejected in production profile while HTTPS is permitted."""
    initial_cnt = metrics_registry.get_summary().get("tls_validation_failures_total", 0)

    # 1. Development profile permits HTTP
    monkeypatch.setattr(settings, "environment", "development")
    validate_tls_url("http://insecure.example.com/callback", url_type="callback")

    # 2. Production profile rejects HTTP
    monkeypatch.setattr(settings, "environment", "production")
    with pytest.raises(TLSValidationError) as exc_info:
        validate_tls_url("http://insecure.example.com/webhook", url_type="webhook")
    assert "must use https://" in exc_info.value.message

    new_cnt = metrics_registry.get_summary().get("tls_validation_failures_total", 0)
    assert new_cnt == initial_cnt + 1

    # 3. Production profile permits HTTPS
    validate_tls_url("https://secure.example.com/webhook", url_type="webhook")

    # 4. SSL Context options check
    ctx = get_secure_client_ssl_context()
    assert ctx["verify"] is True
