"""
test_refresh_tokens.py — Tests for RefreshTokenRepository and session persistence.
"""
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories import AccountRepository, DeviceRepository, RefreshTokenRepository


@pytest.mark.asyncio
async def test_create_and_lookup_refresh_token(db_session: AsyncSession, account_factory):
    dev_repo = DeviceRepository(db_session)
    rt_repo = RefreshTokenRepository(db_session)
    acc = await account_factory(account_id="RT-ACC-01")
    dev = await dev_repo.create(account_id=acc.id, device_guid="guid-rt-01", friendly_name="RT Device")

    expires = datetime.now(timezone.utc) + timedelta(days=30)
    rt = await rt_repo.create(
        account_id=acc.id,
        device_guid=dev.device_guid,
        token_hash="sha256_hash_token_001",
        expires_at=expires,
    )
    assert rt.id is not None
    assert rt.token_hash == "sha256_hash_token_001"
    assert rt.is_revoked is False

    # Lookup by hash
    fetched = await rt_repo.get_by_hash("sha256_hash_token_001")
    assert fetched is not None and fetched.id == rt.id


@pytest.mark.asyncio
async def test_revoke_single_token(db_session: AsyncSession, account_factory):
    dev_repo = DeviceRepository(db_session)
    rt_repo = RefreshTokenRepository(db_session)
    acc = await account_factory(account_id="RT-ACC-02")
    dev = await dev_repo.create(account_id=acc.id, device_guid="guid-rt-02", friendly_name="RT Device 2")

    expires = datetime.now(timezone.utc) + timedelta(days=30)
    rt = await rt_repo.create(
        account_id=acc.id,
        device_guid=dev.device_guid,
        token_hash="sha256_hash_to_revoke",
        expires_at=expires,
    )
    assert not rt.is_revoked

    # Revoke token
    revoked = await rt_repo.revoke("sha256_hash_to_revoke")
    assert revoked is True

    # Verify state in database
    updated = await rt_repo.get_by_hash("sha256_hash_to_revoke")
    assert updated is not None and updated.is_revoked is True

    # Revoking already revoked token returns False
    revoked_again = await rt_repo.revoke("sha256_hash_to_revoke")
    assert revoked_again is False


@pytest.mark.asyncio
async def test_revoke_all_tokens_for_account(db_session: AsyncSession, account_factory):
    dev_repo = DeviceRepository(db_session)
    rt_repo = RefreshTokenRepository(db_session)
    acc = await account_factory(account_id="RT-ACC-03")
    dev = await dev_repo.create(account_id=acc.id, device_guid="guid-rt-03", friendly_name="RT Device 3")
    expires = datetime.now(timezone.utc) + timedelta(days=30)

    # 2 active tokens
    rt1 = await rt_repo.create(account_id=acc.id, device_guid=dev.device_guid, token_hash="hash_active_1", expires_at=expires)
    rt2 = await rt_repo.create(account_id=acc.id, device_guid=dev.device_guid, token_hash="hash_active_2", expires_at=expires)
    # 1 already revoked token
    rt3 = await rt_repo.create(account_id=acc.id, device_guid=dev.device_guid, token_hash="hash_already_revoked", expires_at=expires, is_revoked=True)

    count = await rt_repo.revoke_all_for_account(acc.id)
    assert count == 2  # Only the 2 active tokens should be newly revoked

    # Verify all 3 are now revoked
    for h in ("hash_active_1", "hash_active_2", "hash_already_revoked"):
        token = await rt_repo.get_by_hash(h)
        assert token is not None and token.is_revoked is True


@pytest.mark.asyncio
async def test_cascade_delete_token_on_account_removal(db_session: AsyncSession, account_factory):
    acc_repo = AccountRepository(db_session)
    dev_repo = DeviceRepository(db_session)
    rt_repo = RefreshTokenRepository(db_session)
    acc = await account_factory(account_id="RT-ACC-04")
    dev = await dev_repo.create(account_id=acc.id, device_guid="guid-rt-04", friendly_name="RT Device 4")

    rt = await rt_repo.create(
        account_id=acc.id,
        device_guid=dev.device_guid,
        token_hash="sha256_hash_cascade",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    assert await rt_repo.exists(id=rt.id)

    rt_id = rt.id
    # Delete parent account
    await acc_repo.delete(acc.id)
    db_session.expire_all()

    # Verify token is deleted by DB cascade
    assert not await rt_repo.exists(id=rt_id)
    assert await rt_repo.get_by_id(rt_id) is None
