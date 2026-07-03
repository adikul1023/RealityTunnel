"""
test_connection_signals_integration.py — Integration tests for connection signal recording across HTTP endpoints.

Phase 1.4.4: Verifies auth & device endpoints emit correct signal event types, record success/failure,
and maintain exception safety when signal recording fails.
"""
import secrets
import uuid
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

from app.dependencies import get_signal_service
from app.main import app
from app.models.connection_signal import ConnectionEventType
from app.security import hash_master_token
from app.services import ConnectionSignalService
from app.services.exceptions import ConnectionSignalServiceError


@pytest.mark.asyncio
async def test_login_records_signals(async_client: AsyncClient, account_factory, signal_service: ConnectionSignalService):
    """Verify login success and login failure emit LOGIN signals."""
    master_token = secrets.token_hex(32)
    acc = await account_factory(account_id="SIG-LOGIN-1", master_token_hash=hash_master_token(master_token))

    # Successful login
    resp = await async_client.post(
        "/api/auth/login",
        json={"account_id": "SIG-LOGIN-1", "master_token": master_token, "device_guid": "dev-login-1"},
    )
    assert resp.status_code == 200
    signals = await signal_service.get_recent_signals(acc.id)
    login_signals = [s for s in signals if s.event_type == ConnectionEventType.LOGIN and s.success is True]
    assert len(login_signals) >= 1
    assert login_signals[0].device_guid == "dev-login-1"

    # Failed login (wrong master token)
    resp_fail = await async_client.post(
        "/api/auth/login",
        json={"account_id": "SIG-LOGIN-1", "master_token": "wrong-token", "device_guid": "dev-login-fail"},
    )
    assert resp_fail.status_code == 401
    signals_after = await signal_service.get_recent_signals_for_device("dev-login-fail")
    fail_signals = [s for s in signals_after if s.event_type == ConnectionEventType.LOGIN and s.success is False]
    assert len(fail_signals) >= 1
    assert fail_signals[0].device_guid == "dev-login-fail"


@pytest.mark.asyncio
async def test_refresh_and_logout_record_signals(async_client: AsyncClient, account_factory, signal_service: ConnectionSignalService):
    """Verify refresh, logout, and logout-all emit appropriate signal event types."""
    master_token = secrets.token_hex(32)
    acc = await account_factory(account_id="SIG-REF-1", master_token_hash=hash_master_token(master_token))

    login_resp = await async_client.post(
        "/api/auth/login",
        json={"account_id": "SIG-REF-1", "master_token": master_token, "device_guid": "dev-ref-1"},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    # Refresh
    ref_resp = await async_client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert ref_resp.status_code == 200
    new_refresh_token = ref_resp.json()["refresh_token"]

    signals = await signal_service.get_recent_signals(acc.id)
    ref_signals = [s for s in signals if s.event_type == ConnectionEventType.REFRESH and s.success is True]
    assert len(ref_signals) >= 1

    # Logout
    logout_resp = await async_client.post("/api/auth/logout", json={"refresh_token": new_refresh_token})
    assert logout_resp.status_code == 200
    signals_after_logout = await signal_service.get_recent_signals(acc.id)
    logout_signals = [s for s in signals_after_logout if s.event_type == ConnectionEventType.LOGOUT and s.success is True]
    assert len(logout_signals) >= 1

    # Logout all
    logout_all_resp = await async_client.post("/api/auth/logout-all", json={"refresh_token": "any-token"})
    assert logout_all_resp.status_code == 200


@pytest.mark.asyncio
async def test_device_lifecycle_records_signals(async_client: AsyncClient, auth_headers_factory, signal_service: ConnectionSignalService):
    """Verify device registration, rename, deactivation, and reactivation emit signals."""
    headers, account = await auth_headers_factory("SIG-DEV-1")

    # Register
    reg_resp = await async_client.post(
        "/api/devices",
        json={"device_guid": "guid-sig-dev", "friendly_name": "Initial Name"},
        headers=headers,
    )
    assert reg_resp.status_code == 200

    # Rename
    rem_resp = await async_client.patch(
        "/api/devices/guid-sig-dev",
        json={"friendly_name": "New Name"},
        headers=headers,
    )
    assert rem_resp.status_code == 200

    # Deactivate
    deact_resp = await async_client.delete("/api/devices/guid-sig-dev", headers=headers)
    assert deact_resp.status_code == 200

    # Reactivate
    react_resp = await async_client.post("/api/devices/guid-sig-dev/reactivate", headers=headers)
    assert react_resp.status_code == 200

    signals = await signal_service.get_recent_signals(account.id, limit=20)
    event_types = {s.event_type for s in signals if s.success is True}
    assert ConnectionEventType.DEVICE_REGISTER in event_types
    assert ConnectionEventType.DEVICE_RENAME in event_types
    assert ConnectionEventType.DEVICE_DEACTIVATE in event_types
    assert ConnectionEventType.DEVICE_REACTIVATE in event_types


@pytest.mark.asyncio
async def test_exception_safety_in_signal_recording(async_client: AsyncClient, account_factory):
    """Verify endpoint execution completes normally even if signal recording raises an exception."""
    master_token = secrets.token_hex(32)
    await account_factory(account_id="SIG-SAFE-1", master_token_hash=hash_master_token(master_token))

    mock_service = AsyncMock(spec=ConnectionSignalService)
    mock_service.record_signal.side_effect = ConnectionSignalServiceError("Mock signal database error")

    async def override_get_signal_service():
        return mock_service

    app.dependency_overrides[get_signal_service] = override_get_signal_service
    try:
        resp = await async_client.post(
            "/api/auth/login",
            json={"account_id": "SIG-SAFE-1", "master_token": master_token, "device_guid": "dev-safe-1"},
        )
        assert resp.status_code == 200, "Login must succeed even when signal recording fails"
        assert "access_token" in resp.json()
    finally:
        app.dependency_overrides.pop(get_signal_service, None)
