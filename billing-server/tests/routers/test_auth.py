"""
test_auth.py — Integration Tests for Authentication & Refresh API Endpoints (Phase 1.3.5)

Tests all endpoint logic, exception translation to HTTP status codes, replay detection,
idempotent logout flows, and multi-account session isolation.
Runs directly against PostgreSQL in Docker.
"""

from __future__ import annotations

import asyncio
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import jwt
import pytest
import pytest_asyncio
from app.database import get_db
from app.dependencies import get_jwt_service
from app.main import app
from app.models import SubscriptionStatus
from app.repositories import DeviceRepository, RefreshTokenRepository
from app.security import hash_master_token, hash_refresh_token
from app.services import DeviceService, RefreshTokenService
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Yield an httpx AsyncClient configured with overridden database dependencies."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()


# ── Login Tests ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, account_factory):
    """Valid login returns short-lived access token and rotated refresh token."""
    master_token = "a" * 64
    master_token_hash = hash_master_token(master_token)
    account = await account_factory(
        account_id="RT-VALID-0001", master_token_hash=master_token_hash
    )

    payload = {
        "account_id": "RT-VALID-0001",
        "master_token": master_token,
        "device_guid": "dev-guid-001",
    }
    resp = await async_client.post("/api/auth/login", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "Bearer"
    assert data["expires_in"] == 900
    assert len(data["refresh_token"]) == 64


@pytest.mark.asyncio
async def test_login_invalid_account_id(async_client: AsyncClient, account_factory):
    """Login with non-existent Account ID returns HTTP 401."""
    master_token = "a" * 64
    master_token_hash = hash_master_token(master_token)
    await account_factory(
        account_id="RT-REAL-0001", master_token_hash=master_token_hash
    )

    payload = {
        "account_id": "RT-FAKE-9999",
        "master_token": master_token,
        "device_guid": "dev-guid-001",
    }
    resp = await async_client.post("/api/auth/login", json=payload)
    assert resp.status_code == 401
    assert "Authentication failed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_invalid_master_token(async_client: AsyncClient, account_factory):
    """Login with incorrect Master Token returns HTTP 401."""
    master_token = "a" * 64
    master_token_hash = hash_master_token(master_token)
    await account_factory(
        account_id="RT-VALID-0002", master_token_hash=master_token_hash
    )

    payload = {
        "account_id": "RT-VALID-0002",
        "master_token": "f" * 64,
        "device_guid": "dev-guid-001",
    }
    resp = await async_client.post("/api/auth/login", json=payload)
    assert resp.status_code == 401
    assert "Authentication failed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_expired_subscription(async_client: AsyncClient, account_factory):
    """Login for an account with an expired subscription returns HTTP 401."""
    master_token = "b" * 64
    master_token_hash = hash_master_token(master_token)
    past_time = datetime.now(timezone.utc) - timedelta(days=5)
    await account_factory(
        account_id="RT-EXPIRED-001",
        master_token_hash=master_token_hash,
        subscription_expires_at=past_time,
    )

    payload = {
        "account_id": "RT-EXPIRED-001",
        "master_token": master_token,
        "device_guid": "dev-guid-001",
    }
    resp = await async_client.post("/api/auth/login", json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_suspended_account(async_client: AsyncClient, account_factory):
    """Login for a suspended account returns HTTP 401."""
    master_token = "c" * 64
    master_token_hash = hash_master_token(master_token)
    await account_factory(
        account_id="RT-SUSPEND-001",
        master_token_hash=master_token_hash,
        status=SubscriptionStatus.SUSPENDED,
    )

    payload = {
        "account_id": "RT-SUSPEND-001",
        "master_token": master_token,
        "device_guid": "dev-guid-001",
    }
    resp = await async_client.post("/api/auth/login", json=payload)
    assert resp.status_code == 401


# ── Login Device Auto-Registration Tests (Finding H-7) ─────────────────────────


@pytest.mark.asyncio
async def test_login_registers_new_device(
    async_client: AsyncClient, account_factory, db_session: AsyncSession
):
    """
    Login with a brand-new device_guid on an account with available device slots succeeds,
    and a corresponding Device row now exists (Finding H-7).
    """
    master_token = "a" * 64
    master_token_hash = hash_master_token(master_token)
    account = await account_factory(
        account_id="RT-DEVREG-001", master_token_hash=master_token_hash
    )

    payload = {
        "account_id": "RT-DEVREG-001",
        "master_token": master_token,
        "device_guid": "new-device-guid-001",
    }
    resp = await async_client.post("/api/auth/login", json=payload)
    assert resp.status_code == 200, resp.text

    device_repo = DeviceRepository(db_session)
    device = await device_repo.get_by_guid("new-device-guid-001")
    assert device is not None
    assert device.account_id == account.id
    assert device.is_active is True


@pytest.mark.asyncio
async def test_login_same_device_guid_no_duplicate_row(
    async_client: AsyncClient, account_factory, db_session: AsyncSession
):
    """
    Logging in again with the same device_guid succeeds, does not create a duplicate device
    row, and updates last_seen_at (Finding H-7).
    """
    master_token = "a" * 64
    master_token_hash = hash_master_token(master_token)
    account = await account_factory(
        account_id="RT-DEVREG-002", master_token_hash=master_token_hash
    )

    payload = {
        "account_id": "RT-DEVREG-002",
        "master_token": master_token,
        "device_guid": "repeat-device-guid",
    }
    resp1 = await async_client.post("/api/auth/login", json=payload)
    assert resp1.status_code == 200, resp1.text

    device_repo = DeviceRepository(db_session)
    device_after_first = await device_repo.get_by_guid("repeat-device-guid")
    assert device_after_first is not None
    first_seen_at = device_after_first.first_seen_at

    await asyncio.sleep(1.05)  # ensure a measurable last_seen_at delta

    resp2 = await async_client.post("/api/auth/login", json=payload)
    assert resp2.status_code == 200, resp2.text

    all_devices = await device_repo.get_devices_for_account(account.id)
    matching = [d for d in all_devices if d.device_guid == "repeat-device-guid"]
    assert len(matching) == 1, "Second login must not create a duplicate device row"

    device_after_second = matching[0]
    assert device_after_second.first_seen_at == first_seen_at
    assert device_after_second.last_seen_at > first_seen_at


@pytest.mark.asyncio
async def test_login_device_limit_exceeded_returns_403(
    async_client: AsyncClient, account_factory, device_service: DeviceService
):
    """
    Login with a new device_guid on an account already at its plan's device limit returns
    403 with the same structured device-limit error body used by POST /api/devices, and no
    tokens are issued (Finding H-7).
    """
    master_token = "a" * 64
    master_token_hash = hash_master_token(master_token)
    account = await account_factory(
        account_id="RT-DEVLIMIT-001", master_token_hash=master_token_hash
    )
    assert account.plan_id == "free"  # free plan max_devices == 2

    await device_service.register_device(account.id, "limit-device-1", "Laptop")
    await device_service.register_device(account.id, "limit-device-2", "Phone")

    payload = {
        "account_id": "RT-DEVLIMIT-001",
        "master_token": master_token,
        "device_guid": "limit-device-3-new",
    }
    resp = await async_client.post("/api/auth/login", json=payload)
    assert resp.status_code == 403, resp.text
    data = resp.json()
    assert data == {
        "detail": "Device limit reached",
        "plan": "free",
        "current_devices": 2,
        "max_devices": 2,
    }
    assert "access_token" not in resp.text
    assert "refresh_token" not in resp.text


@pytest.mark.asyncio
async def test_login_device_owned_by_different_account_returns_generic_401(
    async_client: AsyncClient, account_factory, device_service: DeviceService
):
    """
    Login with a device_guid already registered to a different account returns a generic
    401 authentication failure — never a message revealing the device belongs to someone
    else (Finding H-7 information-leak prevention).
    """
    master_token_a = "a" * 64
    master_token_b = "b" * 64
    account_a = await account_factory(
        account_id="RT-DEVOWN-A", master_token_hash=hash_master_token(master_token_a)
    )
    account_b = await account_factory(
        account_id="RT-DEVOWN-B", master_token_hash=hash_master_token(master_token_b)
    )

    # Device already belongs to account_a
    await device_service.register_device(
        account_a.id, "shared-device-guid", "Account A's Laptop"
    )

    # account_b attempts to log in presenting the same device_guid
    payload = {
        "account_id": "RT-DEVOWN-B",
        "master_token": master_token_b,
        "device_guid": "shared-device-guid",
    }
    resp = await async_client.post("/api/auth/login", json=payload)
    assert resp.status_code == 401, resp.text
    data = resp.json()
    assert data == {
        "detail": "Authentication failed: invalid credentials or inactive account"
    }
    # Must not leak that the conflict is device-ownership related, nor mention account_a.
    assert "device" not in resp.text.lower()
    assert "RT-DEVOWN-A" not in resp.text


@pytest.mark.asyncio
async def test_login_deactivated_device_returns_403_with_reactivation_message(
    async_client: AsyncClient, account_factory
):
    """
    Login with a device_guid the account previously deactivated via
    DELETE /api/devices/{device_guid} returns 403 with a specific, actionable
    reactivation-instruction message, and no tokens are issued (Finding H-7).
    """
    master_token = "a" * 64
    master_token_hash = hash_master_token(master_token)
    await account_factory(
        account_id="RT-DEVINACTIVE-001", master_token_hash=master_token_hash
    )

    login_payload = {
        "account_id": "RT-DEVINACTIVE-001",
        "master_token": master_token,
        "device_guid": "deactivate-me-device",
    }
    first_login = await async_client.post("/api/auth/login", json=login_payload)
    assert first_login.status_code == 200, first_login.text
    access_token = first_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    deactivate_resp = await async_client.delete(
        "/api/devices/deactivate-me-device", headers=headers
    )
    assert deactivate_resp.status_code == 200, deactivate_resp.text

    second_login = await async_client.post("/api/auth/login", json=login_payload)
    assert second_login.status_code == 403, second_login.text
    detail = second_login.json()["detail"]
    assert "deactivated" in detail.lower()
    assert "/api/devices/deactivate-me-device/reactivate" in detail
    assert "access_token" not in second_login.text
    assert "refresh_token" not in second_login.text


# ── Refresh Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_success(async_client: AsyncClient, account_factory):
    """Valid refresh token rotation issues new access and refresh tokens."""
    master_token = "d" * 64
    master_token_hash = hash_master_token(master_token)
    await account_factory(
        account_id="RT-REFRESH-001", master_token_hash=master_token_hash
    )

    # Login to get initial tokens
    login_resp = await async_client.post(
        "/api/auth/login",
        json={
            "account_id": "RT-REFRESH-001",
            "master_token": master_token,
            "device_guid": "dev-01",
        },
    )
    old_refresh = login_resp.json()["refresh_token"]

    # Rotate refresh token
    refresh_resp = await async_client.post(
        "/api/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert refresh_resp.status_code == 200, refresh_resp.text
    data = refresh_resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["refresh_token"] != old_refresh
    assert data["expires_in"] == 900


@pytest.mark.asyncio
async def test_refresh_replay_attack(async_client: AsyncClient, account_factory):
    """Reusing an already rotated refresh token triggers replay detection and revokes all sessions."""
    master_token = "e" * 64
    master_token_hash = hash_master_token(master_token)
    await account_factory(
        account_id="RT-REPLAY-001", master_token_hash=master_token_hash
    )

    # Login to get token
    login_resp = await async_client.post(
        "/api/auth/login",
        json={
            "account_id": "RT-REPLAY-001",
            "master_token": master_token,
            "device_guid": "dev-01",
        },
    )
    old_refresh = login_resp.json()["refresh_token"]

    # Perform first valid rotation
    rotate_resp = await async_client.post(
        "/api/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert rotate_resp.status_code == 200
    new_refresh = rotate_resp.json()["refresh_token"]

    # Attempt replay attack with old_refresh
    replay_resp = await async_client.post(
        "/api/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert replay_resp.status_code == 401

    # Confirm all sessions (including new_refresh) were revoked by the replay detection engine
    second_try = await async_client.post(
        "/api/auth/refresh", json={"refresh_token": new_refresh}
    )
    assert second_try.status_code == 401


@pytest.mark.asyncio
async def test_refresh_expired_token(
    async_client: AsyncClient, account_factory, db_session: AsyncSession
):
    """Presenting an expired refresh token returns HTTP 401 without rotation."""
    master_token = "f" * 64
    master_token_hash = hash_master_token(master_token)
    await account_factory(
        account_id="RT-EXP-REF-01", master_token_hash=master_token_hash
    )

    login_resp = await async_client.post(
        "/api/auth/login",
        json={
            "account_id": "RT-EXP-REF-01",
            "master_token": master_token,
            "device_guid": "dev-01",
        },
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Manually expire the token in the database
    repo = RefreshTokenRepository(db_session)
    entity = await repo.get_by_hash(hash_refresh_token(refresh_token))
    assert entity is not None
    await repo.update(entity, expires_at=datetime.now(timezone.utc) - timedelta(days=1))

    resp = await async_client.post(
        "/api/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_unknown_token(async_client: AsyncClient):
    """Presenting a random unknown refresh token returns HTTP 401."""
    random_token = secrets.token_hex(32)
    resp = await async_client.post(
        "/api/auth/refresh", json={"refresh_token": random_token}
    )
    assert resp.status_code == 401


# ── Logout Tests ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_logout_success(async_client: AsyncClient, account_factory):
    """Valid logout revokes the presented refresh token."""
    master_token = "1" * 64
    master_token_hash = hash_master_token(master_token)
    await account_factory(
        account_id="RT-LOGOUT-001", master_token_hash=master_token_hash
    )

    login_resp = await async_client.post(
        "/api/auth/login",
        json={
            "account_id": "RT-LOGOUT-001",
            "master_token": master_token,
            "device_guid": "dev-01",
        },
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Logout
    logout_resp = await async_client.post(
        "/api/auth/logout", json={"refresh_token": refresh_token}
    )
    assert logout_resp.status_code == 200
    assert logout_resp.json() == {"success": True}

    # Verify token can no longer be refreshed
    refresh_resp = await async_client.post(
        "/api/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_already_revoked_token(async_client: AsyncClient, account_factory):
    """Logout with an already revoked token is idempotent and returns success."""
    master_token = "2" * 64
    master_token_hash = hash_master_token(master_token)
    await account_factory(
        account_id="RT-LOGOUT-002", master_token_hash=master_token_hash
    )

    login_resp = await async_client.post(
        "/api/auth/login",
        json={
            "account_id": "RT-LOGOUT-002",
            "master_token": master_token,
            "device_guid": "dev-01",
        },
    )
    refresh_token = login_resp.json()["refresh_token"]

    # First logout
    await async_client.post("/api/auth/logout", json={"refresh_token": refresh_token})

    # Second logout (already revoked)
    second_logout = await async_client.post(
        "/api/auth/logout", json={"refresh_token": refresh_token}
    )
    assert second_logout.status_code == 200
    assert second_logout.json() == {"success": True}


@pytest.mark.asyncio
async def test_logout_unknown_token(async_client: AsyncClient):
    """Logout with an unknown token is idempotent and returns success."""
    random_token = secrets.token_hex(32)
    resp = await async_client.post(
        "/api/auth/logout", json={"refresh_token": random_token}
    )
    assert resp.status_code == 200
    assert resp.json() == {"success": True}


# ── Logout All Tests ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_logout_all_revokes_every_session(
    async_client: AsyncClient, account_factory
):
    """Logout All revokes sessions across all devices for the target account."""
    master_token = "3" * 64
    master_token_hash = hash_master_token(master_token)
    await account_factory(
        account_id="RT-LOGOUTALL-01", master_token_hash=master_token_hash
    )

    # Login on device 1
    resp1 = await async_client.post(
        "/api/auth/login",
        json={
            "account_id": "RT-LOGOUTALL-01",
            "master_token": master_token,
            "device_guid": "dev-01",
        },
    )
    token_dev1 = resp1.json()["refresh_token"]

    # Login on device 2
    resp2 = await async_client.post(
        "/api/auth/login",
        json={
            "account_id": "RT-LOGOUTALL-01",
            "master_token": master_token,
            "device_guid": "dev-02",
        },
    )
    token_dev2 = resp2.json()["refresh_token"]

    # Logout all using device 1 token
    logout_all_resp = await async_client.post(
        "/api/auth/logout-all", json={"refresh_token": token_dev1}
    )
    assert logout_all_resp.status_code == 200
    assert logout_all_resp.json() == {"success": True}

    # Verify both device 1 and device 2 tokens are revoked
    assert (
        await async_client.post("/api/auth/refresh", json={"refresh_token": token_dev1})
    ).status_code == 401
    assert (
        await async_client.post("/api/auth/refresh", json={"refresh_token": token_dev2})
    ).status_code == 401


@pytest.mark.asyncio
async def test_logout_all_other_accounts_unaffected(
    async_client: AsyncClient, account_factory
):
    """Logout All for Account A leaves Account B's sessions active and refreshable."""
    token_a = "4" * 64
    token_b = "5" * 64
    await account_factory(
        account_id="RT-ACCA-0001", master_token_hash=hash_master_token(token_a)
    )
    await account_factory(
        account_id="RT-ACCB-0001", master_token_hash=hash_master_token(token_b)
    )

    # Login both accounts
    resp_a = await async_client.post(
        "/api/auth/login",
        json={
            "account_id": "RT-ACCA-0001",
            "master_token": token_a,
            "device_guid": "dev-a",
        },
    )
    ref_a = resp_a.json()["refresh_token"]

    resp_b = await async_client.post(
        "/api/auth/login",
        json={
            "account_id": "RT-ACCB-0001",
            "master_token": token_b,
            "device_guid": "dev-b",
        },
    )
    ref_b = resp_b.json()["refresh_token"]

    # Logout all for Account A
    await async_client.post("/api/auth/logout-all", json={"refresh_token": ref_a})

    # Account A token fails
    assert (
        await async_client.post("/api/auth/refresh", json={"refresh_token": ref_a})
    ).status_code == 401

    # Account B token succeeds
    refresh_b = await async_client.post(
        "/api/auth/refresh", json={"refresh_token": ref_b}
    )
    assert refresh_b.status_code == 200
    assert "access_token" in refresh_b.json()


# ── Phase 1.3.6: Protected Endpoint GET /api/auth/me & Middleware Tests ──────


@pytest.mark.asyncio
async def test_get_me_success_with_valid_bearer_token(
    async_client: AsyncClient, account_factory
):
    """Valid access token returns non-sensitive profile information with 200 OK."""
    master_token = "a" * 64
    await account_factory(
        account_id="RT-ME-SUCCESS", master_token_hash=hash_master_token(master_token)
    )

    login_resp = await async_client.post(
        "/api/auth/login",
        json={
            "account_id": "RT-ME-SUCCESS",
            "master_token": master_token,
            "device_guid": "dev-me",
        },
    )
    access_token = login_resp.json()["access_token"]

    me_resp = await async_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["account_id"] == "RT-ME-SUCCESS"
    assert data["status"] == "ACTIVE"
    assert "subscription_expires_at" in data
    # Ensure sensitive data never leaks
    assert "id" not in data
    assert "master_token" not in data
    assert "master_token_hash" not in data
    assert "marzban_username" not in data


@pytest.mark.asyncio
async def test_get_me_missing_authorization_header(async_client: AsyncClient):
    """Missing Authorization header returns 401."""
    resp = await async_client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Missing Authorization header"}


@pytest.mark.asyncio
async def test_get_me_malformed_authorization_header(async_client: AsyncClient):
    """Malformed Authorization header (e.g. 3 parts) returns 401."""
    resp = await async_client.get(
        "/api/auth/me", headers={"Authorization": "Bearer token1 token2"}
    )
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid Authorization header format. Expected Bearer token"}


@pytest.mark.asyncio
async def test_get_me_wrong_bearer_format(async_client: AsyncClient):
    """Wrong authorization scheme (e.g. Basic instead of Bearer) returns 401."""
    resp = await async_client.get(
        "/api/auth/me", headers={"Authorization": "Basic sometoken"}
    )
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid Authorization header format. Expected Bearer token"}


@pytest.mark.asyncio
async def test_get_me_empty_token(async_client: AsyncClient):
    """Authorization header with Bearer prefix but empty token string returns 401."""
    resp = await async_client.get(
        "/api/auth/me", headers={"Authorization": "Bearer   "}
    )
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid Authorization header format. Expected Bearer token"}


@pytest.mark.asyncio
async def test_get_me_expired_jwt(async_client: AsyncClient, account_factory):
    """An expired Access JWT returns HTTP 401 Unauthorized (never 500)."""
    acc = await account_factory(account_id="RT-ME-EXPIRED")
    jwt_svc = get_jwt_service()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(acc.id),
        "account": acc.account_id,
        "device": "dev-01",
        "iss": "realitytunnel-auth",
        "aud": "realitytunnel-api",
        "iat": int(now.timestamp()) - 3600,
        "nbf": int(now.timestamp()) - 3600,
        "exp": int(now.timestamp()) - 1800,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, jwt_svc.private_key, algorithm="EdDSA")

    resp = await async_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Access token has expired"}


@pytest.mark.asyncio
async def test_get_me_tampered_jwt(async_client: AsyncClient, account_factory):
    """A tampered JWT returns HTTP 401 Unauthorized (never 500)."""
    master_token = "b" * 64
    await account_factory(
        account_id="RT-ME-TAMPER", master_token_hash=hash_master_token(master_token)
    )
    login_resp = await async_client.post(
        "/api/auth/login",
        json={
            "account_id": "RT-ME-TAMPER",
            "master_token": master_token,
            "device_guid": "dev-me",
        },
    )
    access_token = login_resp.json()["access_token"]
    # Tamper with the token string
    tampered = access_token[:-5] + "xxxxx"

    resp = await async_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {tampered}"}
    )
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid access token signature"}


@pytest.mark.asyncio
async def test_get_me_wrong_issuer(async_client: AsyncClient, account_factory):
    """JWT with wrong issuer claim returns 401."""
    acc = await account_factory(account_id="RT-ME-ISS")
    jwt_svc = get_jwt_service()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(acc.id),
        "account": acc.account_id,
        "device": "dev-01",
        "iss": "wrong-issuer",
        "aud": "realitytunnel-api",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(now.timestamp()) + 900,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, jwt_svc.private_key, algorithm="EdDSA")

    resp = await async_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_wrong_audience(async_client: AsyncClient, account_factory):
    """JWT with wrong audience claim returns 401."""
    acc = await account_factory(account_id="RT-ME-AUD")
    jwt_svc = get_jwt_service()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(acc.id),
        "account": acc.account_id,
        "device": "dev-01",
        "iss": "realitytunnel-auth",
        "aud": "wrong-audience",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(now.timestamp()) + 900,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, jwt_svc.private_key, algorithm="EdDSA")

    resp = await async_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_deleted_account(
    async_client: AsyncClient, account_factory, db_session: AsyncSession
):
    """Token is valid but account has been deleted from DB returns 401."""
    master_token = "c" * 64
    acc = await account_factory(
        account_id="RT-ME-DEL", master_token_hash=hash_master_token(master_token)
    )
    login_resp = await async_client.post(
        "/api/auth/login",
        json={
            "account_id": "RT-ME-DEL",
            "master_token": master_token,
            "device_guid": "dev-me",
        },
    )
    access_token = login_resp.json()["access_token"]

    # Delete account from DB
    await db_session.delete(acc)
    await db_session.commit()

    resp = await async_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Authentication failed or account invalid"}


@pytest.mark.asyncio
async def test_get_me_suspended_account(
    async_client: AsyncClient, account_factory, db_session: AsyncSession
):
    """Token is valid but account status changed to SUSPENDED returns 401."""
    master_token = "d" * 64
    acc = await account_factory(
        account_id="RT-ME-SUSP", master_token_hash=hash_master_token(master_token)
    )
    login_resp = await async_client.post(
        "/api/auth/login",
        json={
            "account_id": "RT-ME-SUSP",
            "master_token": master_token,
            "device_guid": "dev-me",
        },
    )
    access_token = login_resp.json()["access_token"]

    # Update account status to SUSPENDED
    acc.status = SubscriptionStatus.SUSPENDED
    await db_session.commit()

    resp = await async_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 401
    assert "Account inactive" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_me_expired_subscription(
    async_client: AsyncClient, account_factory, db_session: AsyncSession
):
    """Token is valid but subscription timestamp expired after token issuance returns 401."""
    master_token = "e" * 64
    acc = await account_factory(
        account_id="RT-ME-SUBEXP", master_token_hash=hash_master_token(master_token)
    )
    login_resp = await async_client.post(
        "/api/auth/login",
        json={
            "account_id": "RT-ME-SUBEXP",
            "master_token": master_token,
            "device_guid": "dev-me",
        },
    )
    access_token = login_resp.json()["access_token"]

    # Expire subscription timestamp in DB
    acc.subscription_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.commit()

    resp = await async_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 401
    assert "Account inactive" in resp.json()["detail"]


# ── Phase 1.3.8: Regression Tests for Audit FINDING-01 ───────────────────────


@pytest.mark.asyncio
async def test_refresh_rejects_suspended_account(
    async_client: AsyncClient, account_factory, db_session: AsyncSession
):
    """FINDING-01 regression: suspended account must not receive new access tokens via refresh."""
    master_token = "f" * 64
    acc = await account_factory(
        account_id="RT-SUSP-REFRESH", master_token_hash=hash_master_token(master_token)
    )
    login_resp = await async_client.post(
        "/api/auth/login",
        json={
            "account_id": "RT-SUSP-REFRESH",
            "master_token": master_token,
            "device_guid": "dev-01",
        },
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    # Suspend account after initial login
    acc.status = SubscriptionStatus.SUSPENDED
    await db_session.commit()

    # Refresh must now be rejected — suspended account cannot obtain new access tokens
    resp = await async_client.post(
        "/api/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejects_expired_subscription(
    async_client: AsyncClient, account_factory, db_session: AsyncSession
):
    """FINDING-01 regression: expired subscription must not receive new access tokens via refresh."""
    master_token = "a1" * 32
    acc = await account_factory(
        account_id="RT-EXP-REFRESH", master_token_hash=hash_master_token(master_token)
    )
    login_resp = await async_client.post(
        "/api/auth/login",
        json={
            "account_id": "RT-EXP-REFRESH",
            "master_token": master_token,
            "device_guid": "dev-01",
        },
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    # Expire subscription after initial login
    acc.subscription_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.commit()

    # Refresh must now be rejected — expired subscription cannot obtain new access tokens
    resp = await async_client.post(
        "/api/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert resp.status_code == 401
