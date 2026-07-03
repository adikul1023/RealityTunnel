"""
test_device_service.py — Unit tests for DeviceService (Phase 1.4.1).
Verifies device lifecycle, timestamps, ownership invariants, status toggles, and exception translation.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import RepositoryError
from app.repositories import AccountRepository, DeviceRepository
from app.services import (
    DeviceService,
    DeviceServiceError,
    DeviceOwnershipError,
    DeviceNotFoundError,
    InactiveDeviceError,
)


@pytest.fixture
def device_service(db_session: AsyncSession) -> DeviceService:
    dev_repo = DeviceRepository(db_session)
    acc_repo = AccountRepository(db_session)
    return DeviceService(dev_repo, acc_repo)


@pytest.mark.asyncio
async def test_register_device_new_creates_timestamps(
    device_service: DeviceService, account_factory
):
    """1. Verify register_device creates device with proper timestamps and friendly_name."""
    acc = await account_factory(account_id="DEV-SVC-01")
    dev = await device_service.register_device(
        account_id=acc.id, device_guid="guid-svc-001", friendly_name="My Desktop"
    )

    assert dev.id is not None
    assert dev.account_id == acc.id
    assert dev.device_guid == "guid-svc-001"
    assert dev.friendly_name == "My Desktop"
    assert dev.is_active is True
    assert dev.first_seen_at is not None
    assert dev.last_seen_at is not None
    assert dev.first_seen_at == dev.last_seen_at


@pytest.mark.asyncio
async def test_register_device_existing_same_account(
    device_service: DeviceService, account_factory
):
    """2. Registering same GUID under same account updates last_seen_at (and friendly_name if given)."""
    acc = await account_factory(account_id="DEV-SVC-02")
    dev1 = await device_service.register_device(
        account_id=acc.id, device_guid="guid-svc-002", friendly_name="Laptop Original"
    )
    first_seen = dev1.first_seen_at
    old_last_seen = dev1.last_seen_at

    # Register again with new friendly_name
    dev2 = await device_service.register_device(
        account_id=acc.id, device_guid="guid-svc-002", friendly_name="Laptop Renamed"
    )

    assert dev2.id == dev1.id
    assert dev2.first_seen_at == first_seen
    assert dev2.last_seen_at >= old_last_seen
    assert dev2.friendly_name == "Laptop Renamed"


@pytest.mark.asyncio
async def test_register_device_ownership_error(
    device_service: DeviceService, account_factory
):
    """3. Registering same GUID under different account raises DeviceOwnershipError."""
    acc1 = await account_factory(account_id="DEV-SVC-03A")
    acc2 = await account_factory(account_id="DEV-SVC-03B")

    await device_service.register_device(account_id=acc1.id, device_guid="guid-svc-shared")

    with pytest.raises(DeviceOwnershipError):
        await device_service.register_device(account_id=acc2.id, device_guid="guid-svc-shared")


@pytest.mark.asyncio
async def test_touch_device_updates_only_last_seen(
    device_service: DeviceService, account_factory
):
    """4. touch_device updates only last_seen_at. Does not change first_seen_at or friendly_name."""
    acc = await account_factory(account_id="DEV-SVC-04")
    dev = await device_service.register_device(
        account_id=acc.id, device_guid="guid-svc-004", friendly_name="Touch Phone"
    )
    first_seen = dev.first_seen_at
    name = dev.friendly_name

    touched = await device_service.touch_device("guid-svc-004")

    assert touched.id == dev.id
    assert touched.first_seen_at == first_seen
    assert touched.friendly_name == name
    assert touched.last_seen_at >= first_seen


@pytest.mark.asyncio
async def test_rename_device_verifies_ownership(
    device_service: DeviceService, account_factory
):
    """5. rename_device updates friendly_name and verifies ownership."""
    acc1 = await account_factory(account_id="DEV-SVC-05A")
    acc2 = await account_factory(account_id="DEV-SVC-05B")

    dev = await device_service.register_device(
        account_id=acc1.id, device_guid="guid-svc-005", friendly_name="Old Name"
    )

    renamed = await device_service.rename_device(acc1.id, "guid-svc-005", "New Name")
    assert renamed.friendly_name == "New Name"

    with pytest.raises(DeviceOwnershipError):
        await device_service.rename_device(acc2.id, "guid-svc-005", "Hacked Name")


@pytest.mark.asyncio
async def test_deactivate_and_reactivate_device(
    device_service: DeviceService, account_factory
):
    """6. Deactivate and reactivate toggle is_active."""
    acc = await account_factory(account_id="DEV-SVC-06")
    dev = await device_service.register_device(account_id=acc.id, device_guid="guid-svc-006")
    assert dev.is_active is True

    deactivated = await device_service.deactivate_device(acc.id, "guid-svc-006")
    assert deactivated.is_active is False

    reactivated = await device_service.reactivate_device(acc.id, "guid-svc-006")
    assert reactivated.is_active is True


@pytest.mark.asyncio
async def test_deactivate_already_inactive_raises_error(
    device_service: DeviceService, account_factory
):
    """7. Deactivating an already inactive device raises InactiveDeviceError."""
    acc = await account_factory(account_id="DEV-SVC-07")
    await device_service.register_device(account_id=acc.id, device_guid="guid-svc-007")
    await device_service.deactivate_device(acc.id, "guid-svc-007")

    with pytest.raises(InactiveDeviceError):
        await device_service.deactivate_device(acc.id, "guid-svc-007")


@pytest.mark.asyncio
async def test_touch_inactive_device_raises_error(
    device_service: DeviceService, account_factory
):
    """8. Touching an inactive device raises InactiveDeviceError."""
    acc = await account_factory(account_id="DEV-SVC-08")
    await device_service.register_device(account_id=acc.id, device_guid="guid-svc-008")
    await device_service.deactivate_device(acc.id, "guid-svc-008")

    with pytest.raises(InactiveDeviceError):
        await device_service.touch_device("guid-svc-008")


@pytest.mark.asyncio
async def test_manipulate_another_accounts_device(
    device_service: DeviceService, account_factory
):
    """9. Trying to manipulate another account's device raises DeviceOwnershipError."""
    acc1 = await account_factory(account_id="DEV-SVC-09A")
    acc2 = await account_factory(account_id="DEV-SVC-09B")
    await device_service.register_device(account_id=acc1.id, device_guid="guid-svc-009")

    with pytest.raises(DeviceOwnershipError):
        await device_service.get_device(acc2.id, "guid-svc-009")

    with pytest.raises(DeviceOwnershipError):
        await device_service.deactivate_device(acc2.id, "guid-svc-009")


@pytest.mark.asyncio
async def test_exception_translation(
    device_service: DeviceService, account_factory
):
    """10. Translating repository exceptions to domain exceptions properly."""
    acc = await account_factory(account_id="DEV-SVC-10")

    # Non-existent device lookup raises DeviceNotFoundError
    with pytest.raises(DeviceNotFoundError):
        await device_service.get_device(acc.id, "non-existent-guid")

    # Non-existent account registration raises DeviceServiceError
    fake_uuid = uuid.uuid4()
    with pytest.raises(DeviceServiceError, match="Account .* not found"):
        await device_service.register_device(fake_uuid, "guid-svc-fake")

    # Mock repository exception -> must translate to DeviceServiceError (never leak RepositoryError)
    with patch.object(
        device_service.device_repo, "get_by_guid", side_effect=RepositoryError("DB fail")
    ):
        with pytest.raises(DeviceServiceError) as exc_info:
            await device_service.get_device(acc.id, "guid-svc-010")
        assert not isinstance(exc_info.value, RepositoryError)
