"""
tests/routers/test_admin_operations.py — Unit and integration tests for Phase 2A Operations REST API.

Coverage:
- GET /api/admin/infrastructure/status (component status DTOs with latency and messages)
- GET /api/admin/audit-events (keyset pagination with next_cursor and source filtering)
- GET /api/admin/version (components and baseline client versions)
- GET /api/admin/account/{account_id} (unified 7-facet account detail lookup)
- DELETE /api/admin/accounts/{account_id}/devices/{device_guid} (device removal and remaining count)
- RBAC enforcement (read-only admins forbidden from device deletion)
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from app.models import SubscriptionStatus
from app.security_hardening.audit import audit_service

pytestmark = pytest.mark.asyncio


# ── Infrastructure Status ─────────────────────────────────────────────────────


async def test_infrastructure_status_success(async_client, admin_auth_headers_factory):
    headers, _ = await admin_auth_headers_factory(is_super_admin=False)
    resp = await async_client.get("/api/admin/infrastructure/status", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    expected_components = [
        "billing_api",
        "database",
        "marzban",
        "xray",
        "scheduler",
        "redis",
        "caddy",
    ]
    for comp in expected_components:
        assert comp in body, f"Component {comp} missing in status response"
        assert "status" in body[comp]
        assert body[comp]["status"] in ("healthy", "degraded", "offline", "not_configured")
        assert "last_checked" in body[comp]
        assert "reason" in body[comp]


async def test_infrastructure_status_requires_auth(async_client):
    resp = await async_client.get("/api/admin/infrastructure/status")
    assert resp.status_code == 401


# ── Audit Events ──────────────────────────────────────────────────────────────


async def test_audit_events_pagination(async_client, admin_auth_headers_factory, db_session):
    # Log several events explicitly
    for i in range(5):
        await audit_service.record_event(
            event_type=f"TEST_AUDIT_{i}",
            actor_id="admin-1",
            target_id=f"test-{i}",
            details={"source": "operator"},
        )

    headers, _ = await admin_auth_headers_factory(is_super_admin=False)
    resp = await async_client.get("/api/admin/audit-events?limit=2", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert len(body["items"]) <= 2
    assert "next_cursor" in body
    assert body["next_cursor"] is not None

    # Fetch next page using cursor
    cursor = body["next_cursor"]
    resp_page2 = await async_client.get(f"/api/admin/audit-events?limit=2&cursor={cursor}", headers=headers)
    assert resp_page2.status_code == 200
    body2 = resp_page2.json()
    assert "items" in body2
    assert len(body2["items"]) <= 2


async def test_audit_events_filtering(async_client, admin_auth_headers_factory, db_session):
    await audit_service.record_event(
        event_type="LOGIN_SUCCESS",
        actor_id="admin-2",
        target_id="system",
        details={"source": "operator"},
    )
    headers, _ = await admin_auth_headers_factory(is_super_admin=False)
    resp = await async_client.get("/api/admin/audit-events?source=operator", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert all(e.get("source") == "operator" for e in body["items"])


# ── Version Endpoint ──────────────────────────────────────────────────────────


async def test_version_endpoint_success(async_client, admin_auth_headers_factory):
    headers, _ = await admin_auth_headers_factory(is_super_admin=False)
    resp = await async_client.get("/api/admin/version", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert "billing_api" in body
    assert "marzban" in body
    assert "xray" in body
    assert "sing_box_min" in body
    assert "database_schema" in body
    assert "git_commit" in body
    assert "build_time" in body
    assert "environment" in body


# ── Unified Account Lookup ────────────────────────────────────────────────────


async def test_unified_account_lookup_success(
    async_client, account_factory, admin_auth_headers_factory, device_service
):
    acc = await account_factory(account_id="TEST-OPS-UNI-01", status=SubscriptionStatus.ACTIVE)
    await device_service.register_device(acc.id, "device-ops-1")

    headers, _ = await admin_auth_headers_factory(is_super_admin=False)
    resp = await async_client.get(f"/api/admin/account/{acc.account_id}", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["account"]["account_id"] == "TEST-OPS-UNI-01"
    assert "subscription" in body
    assert "devices" in body
    assert len(body["devices"]) == 1
    assert body["devices"][0]["device_guid"] == "device-ops-1"
    assert "provisioning" in body
    assert "provisioning_state" in body
    assert "marzban" in body
    assert "vpn" in body
    assert "usage" in body


async def test_unified_account_lookup_not_found(async_client, admin_auth_headers_factory):
    headers, _ = await admin_auth_headers_factory(is_super_admin=False)
    resp = await async_client.get("/api/admin/account/DOES-NOT-EXIST", headers=headers)
    assert resp.status_code == 404


# ── Device Deletion Endpoint ──────────────────────────────────────────────────


async def test_delete_device_super_admin_success(
    async_client, account_factory, admin_auth_headers_factory, device_service
):
    acc = await account_factory(account_id="TEST-OPS-DEV-01", status=SubscriptionStatus.ACTIVE)
    await device_service.register_device(acc.id, "dev-remove-1")
    await device_service.register_device(acc.id, "dev-keep-2")

    headers, _ = await admin_auth_headers_factory(is_super_admin=True)
    resp = await async_client.delete(
        f"/api/admin/accounts/{acc.account_id}/devices/dev-remove-1",
        headers=headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["removed"] is True
    assert body["remaining_devices"] == 1
    assert "refresh_tokens_revoked" in body

    # Verify via listing
    resp_list = await async_client.get(f"/api/admin/accounts/{acc.account_id}/devices", headers=headers)
    devices = resp_list.json()["devices"]
    assert len(devices) == 1
    assert devices[0]["device_guid"] == "dev-keep-2"


async def test_delete_device_readonly_admin_forbidden(
    async_client, account_factory, admin_auth_headers_factory, device_service
):
    acc = await account_factory(account_id="TEST-OPS-DEV-02")
    await device_service.register_device(acc.id, "dev-forbidden-1")

    headers, _ = await admin_auth_headers_factory(is_super_admin=False)
    resp = await async_client.delete(
        f"/api/admin/accounts/{acc.account_id}/devices/dev-forbidden-1",
        headers=headers,
    )
    assert resp.status_code == 403


async def test_delete_device_unknown_device_returns_404(
    async_client, account_factory, admin_auth_headers_factory
):
    acc = await account_factory(account_id="TEST-OPS-DEV-03")
    headers, _ = await admin_auth_headers_factory(is_super_admin=True)
    resp = await async_client.delete(
        f"/api/admin/accounts/{acc.account_id}/devices/nonexistent-dev",
        headers=headers,
    )
    assert resp.status_code == 404
