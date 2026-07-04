"""
tests/routers/test_admin_accounts.py — Integration tests for Phase 1.4.6 Administrative REST API.

Coverage:
- Account listing and detail (any admin)
- Suspend, activate, extend-subscription (super-admin only)
- Device listing (any admin, read-only)
- Logout-all (super-admin only)
- Signal listing with pagination (any admin)
- HTTP 403 for read-only admin on write operations
- HTTP 404 for unknown accounts
- Cross-domain token rejection (customer JWT rejected on admin routes)
- DTO leakage audit (no sensitive fields in responses)
- OpenAPI security verification (AdminBearer only on admin routes)
"""
from __future__ import annotations

import secrets
import uuid

import pytest
import pytest_asyncio

from app.models import SubscriptionStatus
from app.security import hash_master_token

pytestmark = pytest.mark.asyncio


# ── Helpers ───────────────────────────────────────────────────────────────────

SENSITIVE_FIELDS = {
    "master_token_hash",
    "password_hash",
    "marzban_username",
    "refresh_token",
    "access_token",
    "master_token",
}


def _assert_no_sensitive_fields(obj: dict | list) -> None:
    """Recursively assert no sensitive credential fields appear in any DTO."""
    if isinstance(obj, list):
        for item in obj:
            _assert_no_sensitive_fields(item)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            assert key not in SENSITIVE_FIELDS, f"Sensitive field '{key}' leaked in DTO"
            _assert_no_sensitive_fields(value)


# ── Account listing ───────────────────────────────────────────────────────────


async def test_list_accounts_success(async_client, account_factory, admin_auth_headers_factory):
    await account_factory(account_id="TEST-LIST-001")
    await account_factory(account_id="TEST-LIST-002")

    headers, _ = await admin_auth_headers_factory(is_super_admin=False)
    resp = await async_client.get("/api/admin/accounts", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert "accounts" in body
    assert "total" in body
    assert body["total"] >= 2
    assert all("account_id" in a for a in body["accounts"])


async def test_list_accounts_pagination(async_client, account_factory, admin_auth_headers_factory):
    for i in range(5):
        await account_factory(account_id=f"TEST-PAGE-{i:03d}")

    headers, _ = await admin_auth_headers_factory(is_super_admin=False)
    resp = await async_client.get("/api/admin/accounts?limit=2&offset=0", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["accounts"]) == 2
    assert body["total"] == 2


async def test_list_accounts_requires_auth(async_client):
    resp = await async_client.get("/api/admin/accounts")
    assert resp.status_code == 401


# ── Account detail ────────────────────────────────────────────────────────────


async def test_get_account_success(async_client, account_factory, admin_auth_headers_factory):
    acc = await account_factory(account_id="TEST-DETAIL-001")
    headers, _ = await admin_auth_headers_factory(is_super_admin=False)

    resp = await async_client.get(f"/api/admin/accounts/{acc.account_id}", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["account_id"] == acc.account_id
    assert "status" in body
    assert "plan_id" in body
    assert "created_at" in body


async def test_get_account_unknown(async_client, admin_auth_headers_factory):
    headers, _ = await admin_auth_headers_factory(is_super_admin=False)
    resp = await async_client.get("/api/admin/accounts/DOES-NOT-EXIST", headers=headers)
    assert resp.status_code == 404


async def test_get_account_requires_auth(async_client):
    resp = await async_client.get("/api/admin/accounts/ANYTHING")
    assert resp.status_code == 401


# ── Suspend ───────────────────────────────────────────────────────────────────


async def test_suspend_account_super_admin(async_client, account_factory, admin_auth_headers_factory):
    acc = await account_factory(account_id="TEST-SUSP-001", status=SubscriptionStatus.ACTIVE)
    headers, _ = await admin_auth_headers_factory(is_super_admin=True)

    resp = await async_client.patch(f"/api/admin/accounts/{acc.account_id}/suspend", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["status"] == "SUSPENDED"


async def test_suspend_account_readonly_admin_forbidden(async_client, account_factory, admin_auth_headers_factory):
    acc = await account_factory(account_id="TEST-SUSP-002")
    headers, _ = await admin_auth_headers_factory(is_super_admin=False)

    resp = await async_client.patch(f"/api/admin/accounts/{acc.account_id}/suspend", headers=headers)

    assert resp.status_code == 403


async def test_suspend_account_unknown(async_client, admin_auth_headers_factory):
    headers, _ = await admin_auth_headers_factory(is_super_admin=True)
    resp = await async_client.patch("/api/admin/accounts/DOES-NOT-EXIST/suspend", headers=headers)
    assert resp.status_code == 404


async def test_suspend_idempotent(async_client, account_factory, admin_auth_headers_factory):
    acc = await account_factory(account_id="TEST-SUSP-IDEM", status=SubscriptionStatus.ACTIVE)
    headers, _ = await admin_auth_headers_factory(is_super_admin=True)

    for _ in range(3):
        resp = await async_client.patch(f"/api/admin/accounts/{acc.account_id}/suspend", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "SUSPENDED"


# ── Activate ──────────────────────────────────────────────────────────────────


async def test_activate_account_super_admin(async_client, account_factory, admin_auth_headers_factory):
    acc = await account_factory(account_id="TEST-ACT-001", status=SubscriptionStatus.SUSPENDED)
    headers, _ = await admin_auth_headers_factory(is_super_admin=True)

    resp = await async_client.patch(f"/api/admin/accounts/{acc.account_id}/activate", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["status"] == "ACTIVE"


async def test_activate_account_readonly_admin_forbidden(async_client, account_factory, admin_auth_headers_factory):
    acc = await account_factory(account_id="TEST-ACT-002")
    headers, _ = await admin_auth_headers_factory(is_super_admin=False)

    resp = await async_client.patch(f"/api/admin/accounts/{acc.account_id}/activate", headers=headers)

    assert resp.status_code == 403


# ── Extend subscription ───────────────────────────────────────────────────────


async def test_extend_subscription_super_admin(async_client, account_factory, admin_auth_headers_factory):
    acc = await account_factory(account_id="TEST-EXT-001", status=SubscriptionStatus.ACTIVE)
    headers, _ = await admin_auth_headers_factory(is_super_admin=True)

    resp = await async_client.patch(
        f"/api/admin/accounts/{acc.account_id}/extend-subscription",
        json={"days": 30},
        headers=headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["subscription_expires_at"] is not None


async def test_extend_subscription_readonly_admin_forbidden(async_client, account_factory, admin_auth_headers_factory):
    acc = await account_factory(account_id="TEST-EXT-002")
    headers, _ = await admin_auth_headers_factory(is_super_admin=False)

    resp = await async_client.patch(
        f"/api/admin/accounts/{acc.account_id}/extend-subscription",
        json={"days": 30},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_extend_subscription_expired_reactivates(async_client, account_factory, admin_auth_headers_factory):
    acc = await account_factory(account_id="TEST-EXT-003", status=SubscriptionStatus.EXPIRED)
    headers, _ = await admin_auth_headers_factory(is_super_admin=True)

    resp = await async_client.patch(
        f"/api/admin/accounts/{acc.account_id}/extend-subscription",
        json={"days": 7},
        headers=headers,
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "ACTIVE"


async def test_extend_subscription_invalid_days(async_client, account_factory, admin_auth_headers_factory):
    acc = await account_factory(account_id="TEST-EXT-004")
    headers, _ = await admin_auth_headers_factory(is_super_admin=True)

    resp = await async_client.patch(
        f"/api/admin/accounts/{acc.account_id}/extend-subscription",
        json={"days": 0},
        headers=headers,
    )
    # FastAPI's global validation_exception_handler in main.py converts 422 -> 400
    assert resp.status_code == 400


# ── Devices ───────────────────────────────────────────────────────────────────


async def test_list_devices_for_account(
    async_client, account_factory, admin_auth_headers_factory, device_service
):
    """Register a device via DeviceService, then verify admin can list it."""
    acc = await account_factory(account_id="TEST-DEVS-001")

    # Register a device directly via service (same db_session as everything else)
    await device_service.register_device(acc.id, "test-device-guid-admin-01")

    # Admin lists devices
    admin_headers, _ = await admin_auth_headers_factory(is_super_admin=False)
    resp = await async_client.get(
        f"/api/admin/accounts/{acc.account_id}/devices",
        headers=admin_headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "devices" in body
    assert len(body["devices"]) == 1
    assert body["devices"][0]["device_guid"] == "test-device-guid-admin-01"


async def test_list_devices_unknown_account(async_client, admin_auth_headers_factory):
    headers, _ = await admin_auth_headers_factory(is_super_admin=False)
    resp = await async_client.get("/api/admin/accounts/DOES-NOT-EXIST/devices", headers=headers)
    assert resp.status_code == 404


# ── Logout-all ────────────────────────────────────────────────────────────────


async def test_logout_all_super_admin(async_client, account_factory, admin_auth_headers_factory, auth_headers_factory):
    master_token = secrets.token_hex(32)
    acc = await account_factory(
        account_id="TEST-LOGOUT-001",
        master_token_hash=hash_master_token(master_token),
    )

    # Establish customer sessions
    for i in range(2):
        r = await async_client.post(
            "/api/auth/login",
            json={"account_id": acc.account_id, "master_token": master_token, "device_guid": f"dev-{i}"},
        )
        assert r.status_code == 200

    admin_headers, _ = await admin_auth_headers_factory(is_super_admin=True)
    resp = await async_client.post(
        f"/api/admin/accounts/{acc.account_id}/logout-all",
        headers=admin_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["revoked_count"] == 2


async def test_logout_all_readonly_admin_forbidden(async_client, account_factory, admin_auth_headers_factory):
    acc = await account_factory(account_id="TEST-LOGOUT-002")
    headers, _ = await admin_auth_headers_factory(is_super_admin=False)

    resp = await async_client.post(
        f"/api/admin/accounts/{acc.account_id}/logout-all",
        headers=headers,
    )
    assert resp.status_code == 403


async def test_logout_all_unknown_account(async_client, admin_auth_headers_factory):
    headers, _ = await admin_auth_headers_factory(is_super_admin=True)
    resp = await async_client.post("/api/admin/accounts/DOES-NOT-EXIST/logout-all", headers=headers)
    assert resp.status_code == 404


# ── Signals ───────────────────────────────────────────────────────────────────


async def test_list_signals_pagination(async_client, account_factory, admin_auth_headers_factory):
    from app.models.connection_signal import ConnectionEventType
    from app.repositories import ConnectionSignalRepository
    from app.database import AsyncSessionLocal

    acc = await account_factory(account_id="TEST-SIG-001")

    # Insert 5 signals directly
    async with AsyncSessionLocal() as session:
        repo = ConnectionSignalRepository(session)
        for _ in range(5):
            await repo.create(
                account_id=acc.id,
                event_type=ConnectionEventType.LOGIN,
                success=True,
            )

    admin_headers, _ = await admin_auth_headers_factory(is_super_admin=False)

    resp = await async_client.get(
        f"/api/admin/accounts/{acc.account_id}/signals?limit=3&offset=0",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "signals" in body
    assert len(body["signals"]) == 3
    assert body["total"] == 3

    resp2 = await async_client.get(
        f"/api/admin/accounts/{acc.account_id}/signals?limit=3&offset=3",
        headers=admin_headers,
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert len(body2["signals"]) == 2


async def test_list_signals_unknown_account(async_client, admin_auth_headers_factory):
    headers, _ = await admin_auth_headers_factory(is_super_admin=False)
    resp = await async_client.get("/api/admin/accounts/DOES-NOT-EXIST/signals", headers=headers)
    assert resp.status_code == 404


# ── Cross-domain token rejection ──────────────────────────────────────────────


async def test_customer_token_rejected_on_admin_accounts_route(
    async_client, auth_headers_factory
):
    """A customer access JWT must be rejected on admin account routes."""
    customer_headers, _ = await auth_headers_factory()
    resp = await async_client.get("/api/admin/accounts", headers=customer_headers)
    assert resp.status_code == 401


async def test_admin_token_rejected_on_customer_route(
    async_client, admin_auth_headers_factory
):
    """An admin access JWT must be rejected on customer device routes."""
    admin_headers, _ = await admin_auth_headers_factory(is_super_admin=False)
    resp = await async_client.get("/api/devices", headers=admin_headers)
    assert resp.status_code == 401


# ── DTO leakage audit ─────────────────────────────────────────────────────────


async def test_dto_leakage_no_sensitive_fields(
    async_client, account_factory, admin_auth_headers_factory
):
    """Verify that no sensitive fields ever appear in admin API responses."""
    acc = await account_factory(account_id="TEST-LEAK-001")
    headers, _ = await admin_auth_headers_factory(is_super_admin=True)

    # account list
    r = await async_client.get("/api/admin/accounts", headers=headers)
    _assert_no_sensitive_fields(r.json())

    # account detail
    r = await async_client.get(f"/api/admin/accounts/{acc.account_id}", headers=headers)
    _assert_no_sensitive_fields(r.json())

    # suspend
    r = await async_client.patch(f"/api/admin/accounts/{acc.account_id}/suspend", headers=headers)
    _assert_no_sensitive_fields(r.json())

    # activate
    r = await async_client.patch(f"/api/admin/accounts/{acc.account_id}/activate", headers=headers)
    _assert_no_sensitive_fields(r.json())

    # devices
    r = await async_client.get(f"/api/admin/accounts/{acc.account_id}/devices", headers=headers)
    _assert_no_sensitive_fields(r.json())

    # signals
    r = await async_client.get(f"/api/admin/accounts/{acc.account_id}/signals", headers=headers)
    _assert_no_sensitive_fields(r.json())


# ── OpenAPI security verification ─────────────────────────────────────────────


async def test_openapi_security_admin_accounts_routes(async_client):
    """
    All /api/admin/accounts/* endpoints must advertise AdminBearer security in OpenAPI,
    not CustomerBearer. The login endpoint (POST /api/admin/login) correctly has no security.
    """
    resp = await async_client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()

    for path, path_item in schema["paths"].items():
        if not path.startswith("/api/admin/accounts"):
            continue
        for method, operation in path_item.items():
            if method in ("get", "post", "patch", "put", "delete"):
                security = operation.get("security", [])
                assert security, f"No security declared on {method.upper()} {path}"
                scheme_names = [list(s.keys())[0] for s in security]
                assert "AdminBearer" in scheme_names, (
                    f"{method.upper()} {path} does not use AdminBearer: {scheme_names}"
                )
                assert "CustomerBearer" not in scheme_names, (
                    f"{method.upper()} {path} exposes CustomerBearer on admin route"
                )


async def test_no_repository_access_in_any_router():
    """
    Architectural invariant (Audit Part 7):
    All files in app/routers/ must never import or use repositories directly.
    Routers strictly orchestrate domain services.
    """
    import ast
    import pathlib

    routers_dir = pathlib.Path(__file__).parent.parent.parent / "app" / "routers"
    forbidden_patterns = [
        "AccountRepository", "DeviceRepository", "RefreshTokenRepository",
        "ConnectionSignalRepository", "AdminUserRepository", "BaseRepository"
    ]

    for router_file in routers_dir.glob("*.py"):
        if router_file.name.startswith("__"):
            continue
        source = router_file.read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                src = ast.unparse(node)
                for pattern in forbidden_patterns:
                    assert pattern not in src, (
                        f"Router {router_file.name} imports repository directly: '{pattern}' found"
                    )

            if isinstance(node, ast.Name):
                for pattern in forbidden_patterns:
                    assert node.id != pattern, (
                        f"Router {router_file.name} references repository class '{pattern}'"
                    )
