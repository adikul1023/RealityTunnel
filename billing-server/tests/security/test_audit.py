"""
test_audit.py — Unit and integration tests for immutable audit logging (Phase 3.5).
"""
import pytest
from app.security_hardening.audit import AuditService
from app.security_hardening.exceptions import SecurityHardeningError
from app.observability.metrics import metrics_registry


@pytest.mark.asyncio
async def test_audit_event_immutability_and_zero_secret_redaction():
    """Verify audit event creation, deep secret scrubbing, and immutability protection."""
    srv = AuditService()
    initial_cnt = metrics_registry.get_summary().get("audit_events_total", 0)

    details = {
        "action": "login_attempt",
        "username": "admin_user",
        "password": "my_super_secret_password_123!",
        "jwt_token": "ey123456789.ey987654321.signature12345",
        "vless_uri": "vless://11112222-3333-4444-5555-666677778888@vpn.example.com:443?encryption=none",
        "nested": {
            "payment_secret": "rzp_test_secret_key_888",
            "normal_field": "safe_value",
        },
    }

    event = await srv.record_event(
        event_type="admin_login",
        actor_id="admin_user_id",
        target_id="system",
        details=details,
        ip_hash="hash_192_168_1_100",
    )

    assert event.event_type == "admin_login"
    assert event.actor_id == "admin_user_id"

    # Verify zero-secret scrubbing
    scrubbed = event.details
    assert scrubbed["password"] == "***REDACTED***"
    assert scrubbed["jwt_token"] == "***REDACTED***"
    assert "11112222-3333-4444" not in scrubbed["vless_uri"]
    assert "***REDACTED***" in scrubbed["vless_uri"]
    assert scrubbed["nested"]["payment_secret"] == "***REDACTED***"
    assert scrubbed["nested"]["normal_field"] == "safe_value"

    # Verify metric increment
    new_cnt = metrics_registry.get_summary().get("audit_events_total", 0)
    assert new_cnt == initial_cnt + 1

    # Verify immutability
    with pytest.raises(SecurityHardeningError):
        srv.modify_or_delete_event(event.event_id)

    # Verify queue status
    status = await srv.get_queue_status()
    assert status["immutable"] is True
    assert status["total_events_recorded"] >= 1
