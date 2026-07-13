"""
test_devices.py — Tests for DeviceRepository and Device persistence.
"""
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.exceptions import DuplicateEntityError
from app.repositories import AccountRepository, DeviceRepository


@pytest.mark.asyncio
async def test_register_device(db_session: AsyncSession, account_factory):
    dev_repo = DeviceRepository(db_session)
    acc = await account_factory(account_id="DEV-ACC-01")

    dev = await dev_repo.create(
        account_id=acc.id,
        device_guid="guid-pc-001",
        friendly_name="Work Laptop",
    )
    assert dev.id is not None
    assert dev.device_guid == "guid-pc-001"
    assert dev.account_id == acc.id

    # Lookup by GUID
    fetched = await dev_repo.get_by_guid("guid-pc-001")
    assert fetched is not None and fetched.id == dev.id


@pytest.mark.asyncio
async def test_duplicate_device_guid_rejected_for_same_account(db_session: AsyncSession, account_factory):
    dev_repo = DeviceRepository(db_session)
    acc = await account_factory(account_id="DEV-ACC-02")

    await dev_repo.create(account_id=acc.id, device_guid="guid-dup-100", friendly_name="Device 1")
    with pytest.raises(DuplicateEntityError):
        await dev_repo.create(account_id=acc.id, device_guid="guid-dup-100", friendly_name="Device 2")


@pytest.mark.asyncio
async def test_list_devices_ordered_by_last_seen_at(db_session: AsyncSession, account_factory):
    dev_repo = DeviceRepository(db_session)
    acc = await account_factory(account_id="DEV-ACC-03")

    now = datetime.now(timezone.utc)
    dev_old = await dev_repo.create(
        account_id=acc.id,
        device_guid="guid-old",
        friendly_name="Old Phone",
        last_seen_at=now - timedelta(hours=5),
    )
    dev_recent = await dev_repo.create(
        account_id=acc.id,
        device_guid="guid-recent",
        friendly_name="New Phone",
        last_seen_at=now - timedelta(minutes=10),
    )
    dev_oldest = await dev_repo.create(
        account_id=acc.id,
        device_guid="guid-oldest",
        friendly_name="Ancient Tablet",
        last_seen_at=now - timedelta(days=2),
    )

    devices = await dev_repo.get_devices_for_account(acc.id)
    assert len(devices) == 3
    assert devices[0].id == dev_recent.id
    assert devices[1].id == dev_old.id
    assert devices[2].id == dev_oldest.id


@pytest.mark.asyncio
async def test_cascade_delete_device_on_account_removal(db_session: AsyncSession, account_factory):
    acc_repo = AccountRepository(db_session)
    dev_repo = DeviceRepository(db_session)
    acc = await account_factory(account_id="DEV-ACC-04")

    dev = await dev_repo.create(account_id=acc.id, device_guid="guid-cascade", friendly_name="To Cascade")
    assert await dev_repo.exists(id=dev.id)

    dev_id = dev.id
    # Delete the parent account
    await acc_repo.delete(acc.id)
    db_session.expire_all()

    assert not await dev_repo.exists(id=dev_id)
    assert await dev_repo.get_by_id(dev_id) is None


@pytest.mark.asyncio
async def test_get_device_status(db_session: AsyncSession, account_factory):
    from app.services.device import DeviceService
    acc1 = await account_factory(account_id="DEV-ACC-10")
    acc2 = await account_factory(account_id="DEV-ACC-11")
    dev_repo = DeviceRepository(db_session)
    acc_repo = AccountRepository(db_session)
    service = DeviceService(dev_repo, acc_repo)

    # Active device for acc1
    await dev_repo.create(account_id=acc1.id, device_guid="guid-active", friendly_name="Active Dev", is_active=True)
    # Inactive device for acc1
    await dev_repo.create(account_id=acc1.id, device_guid="guid-inactive", friendly_name="Inactive Dev", is_active=False)
    # Active device for acc2
    await dev_repo.create(account_id=acc2.id, device_guid="guid-acc2", friendly_name="Acc2 Dev", is_active=True)

    # 1. Active device scoped to acc1
    active, reason = await service.get_device_status(acc1.id, "guid-active")
    assert active is True
    assert reason is None

    # 2. Inactive device scoped to acc1
    active, reason = await service.get_device_status(acc1.id, "guid-inactive")
    assert active is False
    assert reason == "DEVICE_REMOVED"

    # 3. Acc1 attempting to check device belonging to acc2 (Change #1 check)
    active, reason = await service.get_device_status(acc1.id, "guid-acc2")
    assert active is False
    assert reason == "DEVICE_REMOVED"

    # 4. Non-existent device
    active, reason = await service.get_device_status(acc1.id, "guid-missing")
    assert active is False
    assert reason == "DEVICE_REMOVED"

