"""
test_subscription_plan.py — Unit and service integration tests for Phase 1.4.3.
Covers subscription plan resolution, quotas, limit enforcement, downgrade behavior, and exceptions.
"""
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, Device
from app.models.subscription_plan import FREE, BASIC, STANDARD, QUARTERLY, SubscriptionPlan
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
    assert plan_service.get_plan("BASIC") == BASIC
    assert plan_service.get_plan(" standard ") == STANDARD


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


# ── 2. Quotas & Limits (FREE, BASIC, STANDARD, QUARTERLY) ────────────────────
@pytest.mark.asyncio
async def test_plan_limits_and_quotas(plan_service: SubscriptionPlanService):
    """Verify exact limit configurations for FREE, BASIC, STANDARD, and QUARTERLY plans."""
    free_acc = Account(plan_id="free")
    basic_acc = Account(plan_id="basic")
    std_acc = Account(plan_id="standard")

    assert plan_service.get_max_devices(free_acc) == 1
    assert plan_service.get_max_concurrent_ips(free_acc) == 1
    assert plan_service.get_plan("free").data_quota_bytes == 10 * 1024**3

    assert plan_service.get_max_devices(basic_acc) == 1
    assert plan_service.get_max_concurrent_ips(basic_acc) == 1
    assert plan_service.get_plan("basic").data_quota_bytes == 40 * 1024**3

    assert plan_service.get_max_devices(std_acc) == 2
    assert plan_service.get_max_concurrent_ips(std_acc) == 2
    assert plan_service.get_plan("standard").data_quota_bytes == 50 * 1024**3


# ── 3. Device Limit Enforcement in DeviceService ─────────────────────────────
@pytest.mark.asyncio
async def test_free_plan_device_limit_enforcement(
    db_session: AsyncSession, account_factory, device_service: DeviceService
):
    """Verify FREE plan rejects registration of a 2nd new device."""
    acc = await account_factory("FREE-LIMIT-1", plan_id="free")
    assert acc.plan_id == "free"

    # Register 1 allowed device
    await device_service.register_device(acc.id, "guid-free-1", "Device 1")

    # Attempt 2nd registration -> must fail with DeviceLimitExceededError
    with pytest.raises(DeviceLimitExceededError) as exc_info:
        await device_service.register_device(acc.id, "guid-free-2", "Device 2")

    err = exc_info.value
    assert err.current_device_count == 1
    assert err.max_devices == 1
    assert err.plan_id == "free"
    assert err.detail == {
        "detail": "Device limit reached",
        "plan": "free",
        "current_devices": 1,
        "max_devices": 1,
        "code": "DEVICE_LIMIT_EXCEEDED",
        "message": "Device limit reached for plan 'free': 1/1 devices registered.",
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
    If an account is downgraded from STANDARD (2 devices) to FREE (1 device) while holding 2 active devices:
    - Existing devices are retained and remain functional (check-ins succeed).
    - New registrations are blocked until active count drops below the new limit.
    """
    acc = await account_factory("STD-DOWN-1")
    acc.plan_id = "standard"
    await db_session.commit()

    # Register 2 devices under STANDARD plan
    for i in range(1, 3):
        await device_service.register_device(acc.id, f"guid-std-{i}")

    # Downgrade account to FREE plan
    acc.plan_id = "free"
    await db_session.commit()

    # Existing active device checks in -> Must succeed without error or deletion!
    dev1 = await device_service.register_device(acc.id, "guid-std-1")
    assert dev1.is_active is True

    # Attempting to register a 3rd NEW device -> Must fail with DeviceLimitExceededError
    with pytest.raises(DeviceLimitExceededError) as exc_info:
        await device_service.register_device(acc.id, "guid-std-new")

    assert exc_info.value.current_device_count == 2
    assert exc_info.value.max_devices == 1


@pytest.mark.asyncio
async def test_reactivate_device_enforces_subscription_limit(
    db_session: AsyncSession, account_factory, device_service: DeviceService
):
    """
    Audit Regression Test (Part 2 / Part 9):
    Verify that reactivating a deactivated device checks the active device count against the plan limit.
    If at capacity, reactivate_device must raise DeviceLimitExceededError and prevent limit bypass.
    """
    acc = await account_factory("REACT-LIMIT-1", plan_id="free")  # FREE plan: max 1 device
    await device_service.register_device(acc.id, "guid-react-limit-1", "Device 1")

    # Deactivate Device 1 (active count is now 0)
    await device_service.deactivate_device(acc.id, "guid-react-limit-1")

    # Register Device 2 (active count is now 1, filling capacity)
    await device_service.register_device(acc.id, "guid-react-limit-2", "Device 2")

    # Attempt to reactivate Device 1 -> must fail with DeviceLimitExceededError
    with pytest.raises(DeviceLimitExceededError) as exc_info:
        await device_service.reactivate_device(acc.id, "guid-react-limit-1")

    err = exc_info.value
    assert err.current_device_count == 1
    assert err.max_devices == 1
    assert err.plan_id == "free"
