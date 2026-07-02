"""
test_accounts.py — Tests for AccountRepository and Account persistence.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.exceptions import DuplicateEntityError
from app.models import SubscriptionStatus
from app.repositories import AccountRepository


@pytest.mark.asyncio
async def test_create_and_retrieve_account(db_session: AsyncSession, account_factory):
    repo = AccountRepository(db_session)
    acc = await account_factory(
        account_id="TEST-ACC-01",
        master_token_hash="hash_test_acc_01",
        marzban_username="marz_test_acc_01",
        status=SubscriptionStatus.ACTIVE,
    )
    assert acc.id is not None
    assert acc.account_id == "TEST-ACC-01"
    assert acc.status == SubscriptionStatus.ACTIVE

    # Retrieve by ID
    by_id = await repo.get_by_id(acc.id)
    assert by_id is not None and by_id.id == acc.id

    # Retrieve by account_id
    by_acc_id = await repo.get_by_account_id("TEST-ACC-01")
    assert by_acc_id is not None and by_acc_id.id == acc.id

    # Retrieve by marzban_username
    by_user = await repo.get_by_marzban_username("marz_test_acc_01")
    assert by_user is not None and by_user.id == acc.id

    # Retrieve by master_token_hash
    by_hash = await repo.get_by_master_token_hash("hash_test_acc_01")
    assert by_hash is not None and by_hash.id == acc.id


@pytest.mark.asyncio
async def test_duplicate_account_id_raises_error(account_factory):
    await account_factory(account_id="DUP-ACC-ID", master_token_hash="hash_dup_1")
    with pytest.raises(DuplicateEntityError):
        await account_factory(account_id="DUP-ACC-ID", master_token_hash="hash_dup_2")


@pytest.mark.asyncio
async def test_duplicate_master_token_hash_raises_error(account_factory):
    await account_factory(account_id="ACC-ID-1", master_token_hash="SAME-HASH-123")
    with pytest.raises(DuplicateEntityError):
        await account_factory(account_id="ACC-ID-2", master_token_hash="SAME-HASH-123")


@pytest.mark.asyncio
async def test_delete_account(db_session: AsyncSession, account_factory):
    repo = AccountRepository(db_session)
    acc = await account_factory(account_id="DEL-ACC-01")
    assert await repo.exists(id=acc.id)

    deleted = await repo.delete(acc.id)
    assert deleted is True
    assert not await repo.exists(id=acc.id)

    # Deleting again returns False
    deleted_again = await repo.delete(acc.id)
    assert deleted_again is False
