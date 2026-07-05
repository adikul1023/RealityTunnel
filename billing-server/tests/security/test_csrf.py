"""
test_csrf.py — Integration tests for CSRF defense and input validation (Phase 3.5).
"""
import pytest
from httpx import AsyncClient

from app.observability.metrics import metrics_registry
from app.security_hardening.validators import validate_uuid_string, validate_json_payload
from app.security_hardening.exceptions import InputValidationError


@pytest.mark.asyncio
async def test_csrf_rejection_on_untrusted_origin(async_client: AsyncClient):
    """Verify state-changing admin requests from untrusted browser origins are rejected (HTTP 403)."""
    initial_cnt = metrics_registry.get_summary().get("csrf_rejections_total", 0)

    # 1. Request from untrusted origin -> HTTP 403 CSRF rejection
    res = await async_client.post(
        "/api/admin/recovery/backups",
        headers={"Origin": "http://evil-attacker-site.com"},
    )
    assert res.status_code == 403
    data = res.json()
    assert data["error_type"] == "csrf_validation_error"
    assert "untrusted origin" in data["detail"]

    new_cnt = metrics_registry.get_summary().get("csrf_rejections_total", 0)
    assert new_cnt == initial_cnt + 1

    # 2. Programmatic Bearer token request without origin or cookie -> passes CSRF (will fail auth 401)
    res_api = await async_client.post(
        "/api/admin/recovery/backups",
        headers={"Authorization": "Bearer some_programmatic_token_123"},
    )
    assert res_api.status_code == 401


def test_malformed_request_and_input_validation():
    """Verify rejection of malformed UUIDs, oversized payloads, and invalid JSON."""
    # 1. Invalid UUID
    with pytest.raises(InputValidationError) as exc_uuid:
        validate_uuid_string("not-a-valid-uuid-string")
    assert "Invalid UUID format" in exc_uuid.value.message

    # 2. Valid UUID
    valid_id = "12345678-1234-5678-1234-567812345678"
    assert str(validate_uuid_string(valid_id)) == valid_id

    # 3. Malformed JSON
    with pytest.raises(InputValidationError) as exc_json:
        validate_json_payload('{"missing": "closing_bracket"')
    assert "Malformed JSON payload" in exc_json.value.message


@pytest.mark.asyncio
async def test_oversized_payload_rejection(async_client: AsyncClient):
    """Verify HTTP 413 rejection when Content-Length exceeds maximum allowed limit."""
    res = await async_client.post(
        "/api/admin/auth/login",
        content=b"x" * 10,
        headers={"Content-Length": "10000000"},  # 10 MB claim > 1 MB default limit
    )
    assert res.status_code == 413
    assert "exceeds maximum allowed limit" in res.json()["detail"]
