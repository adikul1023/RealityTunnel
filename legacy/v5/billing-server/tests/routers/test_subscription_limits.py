"""
test_subscription_limits.py — Integration tests for HTTP 403 mapping and device limit enforcement.
Verifies router exception translation, structured JSON response payloads, and zero internal ID leakage.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import DeviceService


@pytest.mark.asyncio
async def test_register_device_limit_reached_returns_403(
    async_client: AsyncClient,
    auth_headers_factory,
    device_service: DeviceService,
):
    """
    Verify registering a device beyond the subscription plan limit via POST /api/devices:
    1. Returns HTTP 403 Forbidden.
    2. Returns the exact structured JSON response with detail, plan, current_devices, and max_devices.
    3. Leaks no database UUIDs or internal IDs.
    """
    headers, account = await auth_headers_factory("LIMIT-ROUTER-1", plan_id="free")
    assert account.plan_id == "free"

    # Login auto-registered 1 device.

    # Attempt to register a 2nd device via HTTP REST API
    response = await async_client.post(
        "/api/devices",
        json={"device_guid": "device-guid-2", "friendly_name": "Tablet"},
        headers=headers,
    )

    assert response.status_code == 403
    data = response.json()

    assert data == {
        "detail": "Device limit reached",
        "plan": "free",
        "current_devices": 1,
        "max_devices": 1,
        "code": "DEVICE_LIMIT_EXCEEDED",
        "message": "Device limit reached for plan 'free': 1/1 devices registered.",
    }
    # Ensure no internal database UUID or account ID is leaked in the error payload
    response_text = response.text
    assert str(account.id) not in response_text
    assert account.account_id not in response_text


@pytest.mark.asyncio
async def test_register_device_success_within_limit(
    async_client: AsyncClient,
    auth_headers_factory,
):
    """Verify device registration succeeds via POST /api/devices when under the plan limit."""
    headers, account = await auth_headers_factory("LIMIT-ALLOWED-1")
    # Logging in registers 1 device. Limit is 2. So registering 1 more must succeed.
    response = await async_client.post(
        "/api/devices",
        json={"device_guid": "device-guid-allowed", "friendly_name": "My Desktop"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["device_guid"] == "device-guid-allowed"
    assert data["friendly_name"] == "My Desktop"
    assert data["is_active"] is True
