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
        name="Work Laptop",
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

    await dev_repo.create(account_id=acc.id, device_guid="guid-dup-100", name="Device 1")
    with pytest.raises(DuplicateEntityError):
        await dev_repo.create(account_id=acc.id, device_guid="guid-dup-100", name="Device 2")


@pytest.mark.asyncio
async def test_list_devices_ordered_by_last_seen_at(db_session: AsyncSession, account_factory):
    dev_repo = DeviceRepository(db_session)
    acc = await account_factory(account_id="DEV-ACC-03")

    now = datetime.now(timezone.utc)
    dev_old = await dev_repo.create(
        account_id=acc.id,
        device_guid="guid-old",
        name="Old Phone",
        last_seen_at=now - timedelta(hours=5),
    )
    dev_recent = await dev_repo.create(
        account_id=acc.id,
        device_guid="guid-recent",
        name="New Phone",
        last_seen_at=now - timedelta(minutes=10),
    )
    dev_oldest = await dev_repo.create(
        account_id=acc.id,
        device_guid="guid-oldest",
        name="Ancient Tablet",
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

    dev = await dev_repo.create(account_id=acc.id, device_guid="guid-cascade", name="To Cascade")
    assert await dev_repo.exists(id=dev.id)

    dev_id = dev.id
    # Delete the parent account
    await acc_repo.delete(acc.id)
    db_session.expire_all()

    # Verify device is deleted by DB cascade
    assert not await dev_repo.exists(id=dev_id)
    assert await dev_repo.get_by_id(dev_id) is None
