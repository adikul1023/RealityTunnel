"""
tests/integration/test_admin_e2e_flow.py — Complete E2E workflow for Phase 2A Operations layer.

Workflow verified:
1. Operator authenticates and retrieves JWT.
2. Operator checks global infrastructure health across all 7 facets.
3. Operator lists/searches accounts and identifies customer account.
4. Operator queries unified 7-facet account details (account, subscription, devices, provisioning, marzban, vpn, usage).
5. Operator removes a compromised/stale client device and checks remaining device count.
6. Operator inspects audit log and verifies the device removal event is properly recorded with source trace.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SubscriptionStatus

pytestmark = pytest.mark.asyncio


async def test_admin_operations_complete_e2e_workflow(
    async_client: AsyncClient,
    account_factory,
    admin_auth_headers_factory,
    device_service,
    db_session: AsyncSession,
):
    # Setup: Create account and register 2 client devices
    acc = await account_factory(account_id="TEST-E2E-OPS-01", status=SubscriptionStatus.ACTIVE)
    await device_service.register_device(acc.id, "dev-e2e-keep")
    await device_service.register_device(acc.id, "dev-e2e-remove")

    # 1. Operator authenticates (Super-Admin to allow device removal)
    headers, _ = await admin_auth_headers_factory(is_super_admin=True)

    # 2. Operator checks global infrastructure status
    status_resp = await async_client.get("/api/admin/infrastructure/status", headers=headers)
    assert status_resp.status_code == 200
    status_body = status_resp.json()
    assert status_body["billing_api"]["status"] == "healthy"
    assert "marzban" in status_body
    assert "database" in status_body
    assert "xray" in status_body
    assert "scheduler" in status_body
    assert "redis" in status_body
    assert "caddy" in status_body

    # 3. Operator lists/searches accounts
    list_resp = await async_client.get("/api/admin/accounts", headers=headers)
    assert list_resp.status_code == 200
    accounts = list_resp.json()["accounts"]
    assert any(a["account_id"] == "TEST-E2E-OPS-01" for a in accounts)

    # 4. Operator queries unified 7-facet account detail
    unified_resp = await async_client.get(f"/api/admin/account/{acc.account_id}", headers=headers)
    assert unified_resp.status_code == 200
    unified_body = unified_resp.json()
    assert unified_body["account"]["account_id"] == "TEST-E2E-OPS-01"
    assert len(unified_body["devices"]) == 2
    device_guids = {d["device_guid"] for d in unified_body["devices"]}
    assert device_guids == {"dev-e2e-keep", "dev-e2e-remove"}
    assert "provisioning" in unified_body
    assert "provisioning_state" in unified_body
    assert "marzban" in unified_body
    assert "vpn" in unified_body
    assert "usage" in unified_body

    # 5. Operator removes stale client device
    remove_resp = await async_client.delete(
        f"/api/admin/accounts/{acc.account_id}/devices/dev-e2e-remove",
        headers=headers,
    )
    assert remove_resp.status_code == 200
    remove_body = remove_resp.json()
    assert remove_body["removed"] is True
    assert remove_body["remaining_devices"] == 1
    assert "refresh_tokens_revoked" in remove_body

    # Verify unified view updates immediately
    unified_resp_after = await async_client.get(f"/api/admin/account/{acc.account_id}", headers=headers)
    devices_after = unified_resp_after.json()["devices"]
    assert len(devices_after) == 1
    assert devices_after[0]["device_guid"] == "dev-e2e-keep"

    # 6. Operator inspects audit log and verifies the device deletion event was recorded
    audit_resp = await async_client.get("/api/admin/audit-events?limit=20", headers=headers)
    assert audit_resp.status_code == 200
    audit_items = audit_resp.json()["items"]
    
    deletion_events = [
        e for e in audit_items
        if e["event_type"] == "device_deletion" and e["target_id"] == "TEST-E2E-OPS-01"
    ]
    assert len(deletion_events) >= 1
    deletion_event = deletion_events[0]
    assert deletion_event["source"] == "operator"
    assert deletion_event["details"]["device_guid"] == "dev-e2e-remove"
