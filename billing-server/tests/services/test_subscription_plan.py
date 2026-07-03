"""
test_subscription_plan.py — Unit and service integration tests for Phase 1.4.3.
Covers subscription plan resolution, quotas, limit enforcement, downgrade behavior, and exceptions.
"""
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, Device
from app.models.subscription_plan import FREE, PRO, FAMILY, SubscriptionPlan
from app.repositories import AccountRepository, DeviceRepository
from app.services import DeviceService, SubscriptionPlanService
from app.services.exceptions import DeviceLimitExceededError, UnknownPlanError


@pytest.fixture
def plan_service() -> SubscriptionPlanService:
    return SubscriptionPlanService()


# ── 1. Plan Lookup & Defaults ────────────────────────────────────────────────
def test_plan_lookup_valid(plan_service: SubscriptionPlanService):
    """Verify standard plans resolve accurately by lowercase or uppercase string."""
    assert plan_service.get_plan("free") == FREE
    assert plan_service.get_plan("PRO") == PRO
    assert plan_service.get_plan(" family ") == FAMILY


def test_plan_lookup_unknown(plan_service: SubscriptionPlanService):
    """Verify resolving an unknown or empty plan raises UnknownPlanError."""
    with pytest.raises(UnknownPlanError) as exc_info:
        plan_service.get_plan("enterprise_unlimited")
    assert "Unknown subscription plan ID" in str(exc_info.value)

    with pytest.raises(UnknownPlanError):
        plan_service.get_plan("")


@pytest.mark.asyncio
async def test_default_plan_assignment(db_session: AsyncSession):
    """Verify new Account instances default to 'free' plan_id."""
    account = Account(
        account_id="TEST-DEFAULT-PLAN",
        master_token_hash="hash" * 16,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    assert account.plan_id == "free"


# ── 2. Quotas & Limits (FREE, PRO, FAMILY) ───────────────────────────────────
@pytest.mark.asyncio
async def test_plan_limits_and_quotas(plan_service: SubscriptionPlanService):
    """Verify exact limit configurations for FREE, PRO, and FAMILY plans."""
    free_acc = Account(plan_id="free")
    pro_acc = Account(plan_id="pro")
    fam_acc = Account(plan_id="family")

    assert plan_service.get_max_devices(free_acc) == 2
    assert plan_service.get_max_concurrent_ips(free_acc) == 2
    assert plan_service.get_plan("free").data_quota_bytes == 10 * 1024**3

    assert plan_service.get_max_devices(pro_acc) == 5
    assert plan_service.get_max_concurrent_ips(pro_acc) == 5
    assert plan_service.get_plan("pro").data_quota_bytes == 100 * 1024**3

    assert plan_service.get_max_devices(fam_acc) == 15
    assert plan_service.get_max_concurrent_ips(fam_acc) == 15
    assert plan_service.get_plan("family").data_quota_bytes == 500 * 1024**3


# ── 3. Device Limit Enforcement in DeviceService ─────────────────────────────
@pytest.mark.asyncio
async def test_free_plan_device_limit_enforcement(
    db_session: AsyncSession, account_factory, device_service: DeviceService
):
    """Verify FREE plan rejects registration of a 3rd new device."""
    acc = await account_factory("FREE-LIMIT-1")
    assert acc.plan_id == "free"

    # Register 2 allowed devices
    await device_service.register_device(acc.id, "guid-free-1", "Device 1")
    await device_service.register_device(acc.id, "guid-free-2", "Device 2")

    # Attempt 3rd registration -> must fail with DeviceLimitExceededError
    with pytest.raises(DeviceLimitExceededError) as exc_info:
        await device_service.register_device(acc.id, "guid-free-3", "Device 3")

    err = exc_info.value
    assert err.current_device_count == 2
    assert err.max_devices == 2
    assert err.plan_id == "free"
    assert err.detail == {
        "detail": "Device limit reached",
        "plan": "free",
        "current_devices": 2,
        "max_devices": 2,
    }


@pytest.mark.asyncio
async def test_inactive_devices_excluded_from_limit(
    db_session: AsyncSession, account_factory, device_service: DeviceService
):
    """Verify soft-deactivated devices do NOT count against the subscription plan limit."""
    acc = await account_factory("FREE-INACT-1")
    await device_service.register_device(acc.id, "guid-inact-1", "Device 1")
    await device_service.register_device(acc.id, "guid-inact-2", "Device 2")

    # Deactivate Device 1
    await device_service.deactivate_device(acc.id, "guid-inact-1")

    # Now we have 1 active device and 1 inactive device. We should be allowed to register a new one!
    dev3 = await device_service.register_device(acc.id, "guid-inact-3", "Device 3")
    assert dev3.device_guid == "guid-inact-3"
    assert dev3.is_active is True


@pytest.mark.asyncio
async def test_existing_device_login_bypasses_limit(
    db_session: AsyncSession, account_factory, device_service: DeviceService
):
    """Verify an existing registered device can check in even when the account is at max capacity."""
    acc = await account_factory("FREE-BYPASS-1")
    dev1 = await device_service.register_device(acc.id, "guid-bypass-1")
    await device_service.register_device(acc.id, "guid-bypass-2")

    # Re-registering dev1 (login / timestamp update) must succeed without raising limit errors
    updated_dev1 = await device_service.register_device(acc.id, "guid-bypass-1", "Updated Name")
    assert updated_dev1.friendly_name == "Updated Name"


@pytest.mark.asyncio
async def test_downgrade_behavior_retains_existing_devices(
    db_session: AsyncSession, account_factory, device_service: DeviceService
):
    """
    Verify downgrade policy:
    If an account is downgraded from PRO (5 devices) to FREE (2 devices) while holding 4 active devices:
    - Existing devices are retained and remain functional (check-ins succeed).
    - New registrations are blocked until active count drops below the new limit.
    """
    acc = await account_factory("PRO-DOWN-1")
    acc.plan_id = "pro"
    await db_session.commit()

    # Register 4 devices under PRO plan
    for i in range(1, 5):
        await device_service.register_device(acc.id, f"guid-pro-{i}")

    # Downgrade account to FREE plan
    acc.plan_id = "free"
    await db_session.commit()

    # Existing active device checks in -> Must succeed without error or deletion!
    dev1 = await device_service.register_device(acc.id, "guid-pro-1")
    assert dev1.is_active is True

    # Attempting to register a 5th NEW device -> Must fail with DeviceLimitExceededError
    with pytest.raises(DeviceLimitExceededError) as exc_info:
        await device_service.register_device(acc.id, "guid-pro-new")

    assert exc_info.value.current_device_count == 4
    assert exc_info.value.max_devices == 2
