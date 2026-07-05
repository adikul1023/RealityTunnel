"""
test_rotation.py — Unit and integration tests for SecretRotationService (Phase 3.5).
"""
import pytest
from app.security_hardening.rotation import SecretRotationService
from app.security_hardening.exceptions import SecretRotationError
from app.observability.metrics import metrics_registry


def test_secret_rotation_overlap_and_expiry():
    """Verify secret rotation lifecycle, overlap window validity, and old key expiration."""
    srv = SecretRotationService()
    initial_cnt = metrics_registry.get_summary().get("secret_rotations_total", 0)

    # 1. Initial state
    active_old = srv.get_active_secret("webhook_secret")
    valid_initial = srv.get_valid_secrets("webhook_secret")
    assert active_old in valid_initial

    # 2. Rotate secret with 3600s overlap
    new_gen = srv.rotate_secret("webhook_secret", "super_new_webhook_secret_999", overlap_seconds=3600)
    assert new_gen == 2
    assert srv.get_active_secret("webhook_secret") == "super_new_webhook_secret_999"

    # Both old and new remain valid during overlap
    valid_during_overlap = srv.get_valid_secrets("webhook_secret")
    assert "super_new_webhook_secret_999" in valid_during_overlap
    assert active_old in valid_during_overlap
    assert len(valid_during_overlap) >= 2

    # Check metric increment
    new_cnt = metrics_registry.get_summary().get("secret_rotations_total", 0)
    assert new_cnt == initial_cnt + 1

    # 3. Rotate with 0s overlap (expired immediately)
    srv.rotate_secret("webhook_secret", "newest_secret_888", overlap_seconds=-1)
    valid_after_expiry = srv.get_valid_secrets("webhook_secret")
    assert "newest_secret_888" in valid_after_expiry
    assert "super_new_webhook_secret_999" not in valid_after_expiry

    # 4. Error on invalid secret type
    with pytest.raises(SecretRotationError):
        srv.rotate_secret("unknown_secret_type", "val")
