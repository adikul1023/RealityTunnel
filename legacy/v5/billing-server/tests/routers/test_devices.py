"""
test_devices.py — Integration Tests for Device Management REST API (Phase 1.4.2).

Verifies all authenticated device endpoints, ownership isolation (anti-IDOR 404 mapping),
idempotent deletion, status transitions, and JWT security requirements.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_device_service, get_jwt_service
from app.main import app
from app.models import AccountStatus
from app.repositories import AccountRepository, DeviceRepository
from app.security import hash_master_token
from app.services import DeviceService


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Yield an httpx AsyncClient configured with overridden database dependencies."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def device_service(db_session: AsyncSession) -> DeviceService:
    dev_repo = DeviceRepository(db_session)
    acc_repo = AccountRepository(db_session)
    return DeviceService(dev_repo, acc_repo)


import secrets


async def get_auth_headers(async_client: AsyncClient, account_factory, account_id: str = "RT-DEV-001") -> tuple[dict[str, str], any]:
    """Helper to create account, login, and return authorization header + account object."""
    master_token = secrets.token_hex(32)
    acc = await account_factory(account_id=account_id, master_token_hash=hash_master_token(master_token), plan_id="standard")
    login_resp = await async_client.post(
        "/api/auth/login",
        json={"account_id": account_id, "master_token": master_token, "device_guid": f"dev-{account_id}", "client_type": "desktop"},
    )
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, acc


# ── 1. List Devices ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_list_devices(async_client: AsyncClient, account_factory, device_service: DeviceService):
    """1. GET /api/devices returns all devices owned by current account."""
    headers, acc = await get_auth_headers(async_client, account_factory, "RT-LIST-001")
    # Login auto-registered "dev-RT-LIST-001". Register 1 more device:
    await device_service.register_device(acc.id, "guid-list-1", "Desktop")

    resp = await async_client.get("/api/devices", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "devices" in data
    assert len(data["devices"]) == 2

    guids = {d["device_guid"] for d in data["devices"]}
    assert guids == {"dev-RT-LIST-001", "guid-list-1"}

    # Verify public fields only (never expose database UUID or foreign keys)
    for dev in data["devices"]:
        assert "id" not in dev
        assert "account_id" not in dev
        assert "friendly_name" in dev
        assert "first_seen_at" in dev
        assert "last_seen_at" in dev
        assert dev["is_active"] is True


# ── 2. Get Own Device ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_get_own_device(async_client: AsyncClient, account_factory, device_service: DeviceService):
    """2. GET /api/devices/{guid} returns details for own device."""
    headers, acc = await get_auth_headers(async_client, account_factory, "RT-GET-001")
    await device_service.register_device(acc.id, "guid-get-1", "My Phone")

    resp = await async_client.get("/api/devices/guid-get-1", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["device_guid"] == "guid-get-1"
    assert data["friendly_name"] == "My Phone"
    assert data["is_active"] is True
    assert "id" not in data


# ── 3. Request Another Account's Device (404 Anti-Enumeration) ───────────────
@pytest.mark.asyncio
async def test_get_other_account_device_404(async_client: AsyncClient, account_factory, device_service: DeviceService):
    """3. GET /api/devices/{guid} for another account's device returns 404 (not 403)."""
    headers1, acc1 = await get_auth_headers(async_client, account_factory, "RT-GET-OTHER-1")
    headers2, acc2 = await get_auth_headers(async_client, account_factory, "RT-GET-OTHER-2")

    await device_service.register_device(acc1.id, "guid-secret-acc1", "Acc1 Device")

    # Account 2 attempts to get Account 1's device
    resp = await async_client.get("/api/devices/guid-secret-acc1", headers=headers2)
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Device not found"
    assert resp.json()["code"] == "DEVICE_NOT_FOUND"


# ── 4. Rename Device ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_rename_device(async_client: AsyncClient, account_factory, device_service: DeviceService):
    """4. PATCH /api/devices/{guid} updates friendly name."""
    headers, acc = await get_auth_headers(async_client, account_factory, "RT-RENAME-001")
    await device_service.register_device(acc.id, "guid-rename-1", "Old Name")

    resp = await async_client.patch(
        "/api/devices/guid-rename-1",
        json={"friendly_name": "New Name"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["friendly_name"] == "New Name"

    # Verify persistence
    get_resp = await async_client.get("/api/devices/guid-rename-1", headers=headers)
    assert get_resp.json()["friendly_name"] == "New Name"


# ── 5. Deactivate Device ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_deactivate_device(async_client: AsyncClient, account_factory, device_service: DeviceService):
    """5. DELETE /api/devices/{guid} soft-deactivates device."""
    headers, acc = await get_auth_headers(async_client, account_factory, "RT-DEACT-001")
    await device_service.register_device(acc.id, "guid-deact-1", "To Be Deactivated")

    resp = await async_client.delete("/api/devices/guid-deact-1", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True

    # Verify soft-delete state
    get_resp = await async_client.get("/api/devices/guid-deact-1", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["is_active"] is False


# ── 6. Reactivate Device ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_reactivate_device(async_client: AsyncClient, account_factory, device_service: DeviceService):
    """6. POST /api/devices/{guid}/reactivate reactivates an inactive device."""
    headers, acc = await get_auth_headers(async_client, account_factory, "RT-REACT-001")
    await device_service.register_device(acc.id, "guid-react-1")
    await async_client.delete("/api/devices/guid-react-1", headers=headers)

    resp = await async_client.post("/api/devices/guid-react-1/reactivate", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_active"] is True


# ── 7. Rename Inactive Device ────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_rename_inactive_device_400(async_client: AsyncClient, account_factory, device_service: DeviceService):
    """7. PATCH /api/devices/{guid} on an inactive device returns 400 Bad Request."""
    headers, acc = await get_auth_headers(async_client, account_factory, "RT-REN-INACT")
    await device_service.register_device(acc.id, "guid-ren-inact")
    await async_client.delete("/api/devices/guid-ren-inact", headers=headers)

    resp = await async_client.patch(
        "/api/devices/guid-ren-inact",
        json={"friendly_name": "Should Fail"},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"] == "Device is deactivated"
    assert resp.json()["code"] == "DEVICE_DEACTIVATED"


# ── 8. Missing JWT ───────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_missing_jwt(async_client: AsyncClient):
    """8. GET /api/devices without Authorization header returns 401."""
    resp = await async_client.get("/api/devices")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Missing Authorization header"}


# ── 9. Invalid JWT ───────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_invalid_jwt(async_client: AsyncClient):
    """9. GET /api/devices with malformed or invalid JWT returns 401."""
    resp = await async_client.get("/api/devices", headers={"Authorization": "Bearer not-a-valid-token"})
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid access token"}


# ── 10. Expired JWT ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_expired_jwt(async_client: AsyncClient, account_factory):
    """10. GET /api/devices with expired JWT returns 401."""
    _, acc = await get_auth_headers(async_client, account_factory, "RT-EXP-JWT")
    jwt_service = get_jwt_service()

    # Craft an expired token directly using jwt_service keys with all required claims
    now = int(datetime.now(timezone.utc).timestamp())
    expired_payload = {
        "sub": str(acc.id),
        "account": str(acc.account_id),
        "device": "dev-exp",
        "iss": "realitytunnel-auth",
        "aud": "realitytunnel-client",
        "iat": now - 7200,
        "nbf": now - 7200,
        "exp": now - 3600,
        "jti": "jti-expired-test",
    }
    import jwt
    expired_token = jwt.encode(expired_payload, jwt_service.private_key, algorithm="EdDSA")

    resp = await async_client.get("/api/devices", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Access token has expired"}


# ── 11. Tampered JWT ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_tampered_jwt(async_client: AsyncClient, account_factory):
    """11. GET /api/devices with tampered JWT signature returns 401."""
    headers, _ = await get_auth_headers(async_client, account_factory, "RT-TAMP-JWT")
    token = headers["Authorization"].split(" ")[1]
    tampered_token = token[:-4] + "aaaa"

    resp = await async_client.get("/api/devices", headers={"Authorization": f"Bearer {tampered_token}"})
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid access token signature"}


# ── 12. Deleted Account ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_deleted_account(async_client: AsyncClient, account_factory, db_session: AsyncSession):
    """12. Valid JWT for subsequently deleted account returns 401."""
    headers, acc = await get_auth_headers(async_client, account_factory, "RT-DEL-ACC")
    await db_session.delete(acc)
    await db_session.commit()

    resp = await async_client.get("/api/devices", headers=headers)
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Authentication failed or account invalid"}


# ── 13. Suspended Account ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_suspended_account(async_client: AsyncClient, account_factory, db_session: AsyncSession):
    """13. Valid JWT for subsequently suspended account returns 401."""
    headers, acc = await get_auth_headers(async_client, account_factory, "RT-SUSP-ACC")
    acc.status = AccountStatus.SUSPENDED
    await db_session.commit()

    resp = await async_client.get("/api/devices", headers=headers)
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Account inactive: Account suspended"}


# ── 14. Pending Account ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_pending_account(async_client: AsyncClient, account_factory, db_session: AsyncSession):
    """14. Account in PENDING status cannot access endpoints (returns 401)."""
    master_token = "a" * 64
    acc = await account_factory(
        account_id="RT-PEND-ACC",
        master_token_hash=hash_master_token(master_token),
        status=AccountStatus.PENDING,
    )
    jwt_service = get_jwt_service()
    token = jwt_service.issue_access_token(acc.id, acc.account_id, "dev-pend")

    resp = await async_client.get("/api/devices", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Account inactive: Account pending"}


# ── 15. Expired Subscription ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_expired_subscription(async_client: AsyncClient, account_factory, db_session: AsyncSession):
    """15. Valid JWT where subscription expires after issuance returns 401."""
    headers, acc = await get_auth_headers(async_client, account_factory, "RT-SUBEXP-ACC")
    acc.subscription_expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    await db_session.commit()

    resp = await async_client.get("/api/devices", headers=headers)
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Account inactive: Subscription timestamp expired"}


# ── 16. Verify DELETE Remains Idempotent (3x Calls) ──────────────────────────
@pytest.mark.asyncio
async def test_delete_idempotent(async_client: AsyncClient, account_factory, device_service: DeviceService):
    """16. Deleting an already inactive device returns 200 OK success without error across multiple calls."""
    headers, acc = await get_auth_headers(async_client, account_factory, "RT-IDEMP-DEL")
    await device_service.register_device(acc.id, "guid-idemp-del")

    # Call DELETE three times — all must return 200 OK
    for i in range(3):
        resp = await async_client.delete("/api/devices/guid-idemp-del", headers=headers)
        assert resp.status_code == 200, f"Attempt {i+1} failed with {resp.status_code}: {resp.text}"
        assert resp.json()["success"] is True


# ── 17. Verify No IDOR or Enumeration Across All Methods ─────────────────────
@pytest.mark.asyncio
async def test_no_idor_enumeration(async_client: AsyncClient, account_factory, device_service: DeviceService):
    """17. Verify GET, PATCH, DELETE, and POST /reactivate on another account's device return 404 Not Found."""
    _, acc1 = await get_auth_headers(async_client, account_factory, "RT-IDOR-1")
    headers2, _ = await get_auth_headers(async_client, account_factory, "RT-IDOR-2")

    await device_service.register_device(acc1.id, "guid-idor-target", "Acc1 Target")

    # Attempt GET
    get_resp = await async_client.get("/api/devices/guid-idor-target", headers=headers2)
    assert get_resp.status_code == 404, get_resp.text
    assert get_resp.json()["detail"] == "Device not found"
    assert get_resp.json()["code"] == "DEVICE_NOT_FOUND"

    # Attempt PATCH
    patch_resp = await async_client.patch(
        "/api/devices/guid-idor-target",
        json={"friendly_name": "Hacked Name"},
        headers=headers2,
    )
    assert patch_resp.status_code == 404, patch_resp.text
    assert patch_resp.json()["detail"] == "Device not found"
    assert patch_resp.json()["code"] == "DEVICE_NOT_FOUND"

    # Attempt DELETE
    del_resp = await async_client.delete("/api/devices/guid-idor-target", headers=headers2)
    assert del_resp.status_code == 404, del_resp.text
    assert del_resp.json()["detail"] == "Device not found"
    assert del_resp.json()["code"] == "DEVICE_NOT_FOUND"

    # Attempt REACTIVATE
    react_resp = await async_client.post("/api/devices/guid-idor-target/reactivate", headers=headers2)
    assert react_resp.status_code == 404, react_resp.text
    assert react_resp.json()["detail"] == "Device not found"
    assert react_resp.json()["code"] == "DEVICE_NOT_FOUND"


# ── 18. Reactivate Idempotency (2x Calls) ────────────────────────────────────
@pytest.mark.asyncio
async def test_reactivate_idempotent_2x(async_client: AsyncClient, account_factory, device_service: DeviceService):
    """18. Calling POST /reactivate twice returns success twice without exception."""
    headers, acc = await get_auth_headers(async_client, account_factory, "RT-REACT-IDEMP")
    await device_service.register_device(acc.id, "guid-react-idemp")
    await async_client.delete("/api/devices/guid-react-idemp", headers=headers)

    # First reactivation
    resp1 = await async_client.post("/api/devices/guid-react-idemp/reactivate", headers=headers)
    assert resp1.status_code == 200, resp1.text
    assert resp1.json()["is_active"] is True

    # Second reactivation (idempotency check)
    resp2 = await async_client.post("/api/devices/guid-react-idemp/reactivate", headers=headers)
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["is_active"] is True


# ── 19. Friendly Name Trimming ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_friendly_name_trimming(async_client: AsyncClient, account_factory, device_service: DeviceService):
    """19. Sending a friendly name with trailing/leading whitespace is cleanly trimmed and stored."""
    headers, acc = await get_auth_headers(async_client, account_factory, "RT-TRIM-NAME")
    await device_service.register_device(acc.id, "guid-trim-name", "Initial")

    resp = await async_client.patch(
        "/api/devices/guid-trim-name",
        json={"friendly_name": "My Laptop    "},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["friendly_name"] == "My Laptop"

    # Verify persistence in database
    get_resp = await async_client.get("/api/devices/guid-trim-name", headers=headers)
    assert get_resp.json()["friendly_name"] == "My Laptop"
