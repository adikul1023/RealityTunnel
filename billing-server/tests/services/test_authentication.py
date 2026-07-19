"""
test_authentication.py — Comprehensive Unit Tests for AuthenticationService (Phase 1.3.2)
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import RepositoryError
from app.models import AccountStatus
from app.repositories import AccountRepository
from app.security import hash_master_token
from app.services import (
    AuthenticationReason,
    AuthenticationResult,
    AuthenticationService,
    AuthenticationServiceError,
    AccountNotActiveError,
)
from app.services.authentication import DUMMY_MASTER_TOKEN_HASH


@pytest.mark.asyncio
async def test_authenticate_success(db_session: AsyncSession, account_factory):
    """Verify authentication succeeds with active account, valid token, and valid/no expiry."""
    repo = AccountRepository(db_session)
    service = AuthenticationService(repo)

    raw_token = "secret_master_token_valid_01"
    token_hash = hash_master_token(raw_token)
    future_expiry = datetime.now(timezone.utc) + timedelta(days=30)

    acc = await account_factory(
        account_id="RT-AUTH-SUCC-0001",
        master_token_hash=token_hash,
        status=AccountStatus.ACTIVE,
        subscription_expires_at=future_expiry,
    )

    result = await service.authenticate("RT-AUTH-SUCC-0001", raw_token)
    assert isinstance(result, AuthenticationResult)
    assert result.success is True
    assert result.reason == AuthenticationReason.SUCCESS
    assert result.account is not None
    assert result.account.id == acc.id


@pytest.mark.asyncio
async def test_authenticate_unknown_account(db_session: AsyncSession):
    """Verify unknown account ID returns ACCOUNT_NOT_FOUND and success=False."""
    repo = AccountRepository(db_session)
    service = AuthenticationService(repo)

    result = await service.authenticate("RT-NON-EXIST-9999", "any_token_val")
    assert result.success is False
    assert result.reason == AuthenticationReason.ACCOUNT_NOT_FOUND
    assert result.account is None


@pytest.mark.asyncio
async def test_authenticate_wrong_master_token(db_session: AsyncSession, account_factory):
    """Verify incorrect Master Token returns INVALID_MASTER_TOKEN and success=False."""
    repo = AccountRepository(db_session)
    service = AuthenticationService(repo)

    raw_token = "correct_master_token"
    token_hash = hash_master_token(raw_token)

    await account_factory(
        account_id="RT-AUTH-WRONG-001",
        master_token_hash=token_hash,
        status=AccountStatus.ACTIVE,
    )

    result = await service.authenticate("RT-AUTH-WRONG-001", "wrong_master_token_attempt")
    assert result.success is False
    assert result.reason == AuthenticationReason.INVALID_MASTER_TOKEN
    assert result.account is None


@pytest.mark.asyncio
async def test_authenticate_suspended_account(db_session: AsyncSession, account_factory):
    """Verify suspended account returns ACCOUNT_SUSPENDED and includes account object."""
    repo = AccountRepository(db_session)
    service = AuthenticationService(repo)

    raw_token = "token_for_suspended"
    token_hash = hash_master_token(raw_token)

    acc = await account_factory(
        account_id="RT-AUTH-SUSP-001",
        master_token_hash=token_hash,
        status=AccountStatus.SUSPENDED,
    )

    result = await service.authenticate("RT-AUTH-SUSP-001", raw_token)
    assert result.success is False
    assert result.reason == AuthenticationReason.ACCOUNT_SUSPENDED
    assert result.account is not None
    assert result.account.id == acc.id


@pytest.mark.asyncio
async def test_authenticate_pending_account(db_session: AsyncSession, account_factory):
    """Verify pending subscription returns ACCOUNT_PENDING and includes account object."""
    repo = AccountRepository(db_session)
    service = AuthenticationService(repo)

    raw_token = "token_for_pending"
    token_hash = hash_master_token(raw_token)

    acc = await account_factory(
        account_id="RT-AUTH-PEND-001",
        master_token_hash=token_hash,
        status=AccountStatus.PENDING,
    )

    result = await service.authenticate("RT-AUTH-PEND-001", raw_token)
    assert result.success is False
    assert result.reason == AuthenticationReason.ACCOUNT_PENDING
    assert result.account is not None
    assert result.account.id == acc.id


@pytest.mark.asyncio
async def test_authenticate_expired_status(db_session: AsyncSession, account_factory):
    """Verify EXPIRED subscription status returns SUBSCRIPTION_EXPIRED."""
    repo = AccountRepository(db_session)
    service = AuthenticationService(repo)

    raw_token = "token_for_expired_status"
    token_hash = hash_master_token(raw_token)

    acc = await account_factory(
        account_id="RT-AUTH-EXPS-001",
        master_token_hash=token_hash,
        status=AccountStatus.EXPIRED,
    )

    result = await service.authenticate("RT-AUTH-EXPS-001", raw_token)
    assert result.success is False
    assert result.reason == AuthenticationReason.SUBSCRIPTION_EXPIRED
    assert result.account is not None
    assert result.account.id == acc.id


@pytest.mark.asyncio
async def test_authenticate_expired_timestamp(db_session: AsyncSession, account_factory):
    """Verify ACTIVE status with past subscription_expires_at returns SUBSCRIPTION_EXPIRED."""
    repo = AccountRepository(db_session)
    service = AuthenticationService(repo)

    raw_token = "token_for_expired_time"
    token_hash = hash_master_token(raw_token)
    past_expiry = datetime.now(timezone.utc) - timedelta(minutes=5)

    acc = await account_factory(
        account_id="RT-AUTH-EXPT-001",
        master_token_hash=token_hash,
        status=AccountStatus.ACTIVE,
        subscription_expires_at=past_expiry,
    )

    result = await service.authenticate("RT-AUTH-EXPT-001", raw_token)
    assert result.success is False
    assert result.reason == AuthenticationReason.SUBSCRIPTION_EXPIRED
    assert result.account is not None
    assert result.account.id == acc.id


@pytest.mark.asyncio
async def test_authenticate_repository_failure(db_session: AsyncSession):
    """Verify repository exceptions are translated into AuthenticationServiceError without leaking ORM errors.
    Per FINDING-03 remediation: detail field no longer carries raw library error strings.
    """
    repo = AccountRepository(db_session)
    service = AuthenticationService(repo)

    with patch.object(repo, "get_by_account_id", side_effect=RepositoryError("Database unavailable")):
        with pytest.raises(AuthenticationServiceError) as exc_info:
            await service.authenticate("RT-ANY-ID-001", "some_token")
        assert "Database error during authentication lookup" in str(exc_info.value)
        # detail field is intentionally not propagated (FINDING-03 remediation)
        assert exc_info.value.detail is None

    with patch.object(repo, "get_by_account_id", side_effect=RuntimeError("Unexpected connection drop")):
        with pytest.raises(AuthenticationServiceError) as exc_info:
            await service.authenticate("RT-ANY-ID-002", "some_token")
        assert "Unexpected database error during authentication lookup" in str(exc_info.value)
        # detail field is intentionally not propagated (FINDING-03 remediation)
        assert exc_info.value.detail is None


@pytest.mark.asyncio
async def test_authenticate_timing_defense_invoked(db_session: AsyncSession):
    """
    Verify timing attack defense: verify_master_token is invoked against DUMMY_MASTER_TOKEN_HASH
    when an account does not exist in the database.
    """
    repo = AccountRepository(db_session)
    service = AuthenticationService(repo)

    with patch("app.services.authentication.verify_master_token", return_value=False) as mock_verify:
        result = await service.authenticate("RT-NON-EXISTENT-TIMER", "attempted_raw_token")
        assert result.success is False
        assert result.reason == AuthenticationReason.ACCOUNT_NOT_FOUND
        mock_verify.assert_called_once_with("attempted_raw_token", DUMMY_MASTER_TOKEN_HASH)


@pytest.mark.asyncio
async def test_get_active_account_by_uuid_validation(db_session: AsyncSession, account_factory):
    """Verify get_active_account_by_uuid rejects suspended, pending, and expired accounts."""
    repo = AccountRepository(db_session)
    service = AuthenticationService(repo)

    active_acc = await account_factory(account_id="RT-ACT-001", status=AccountStatus.ACTIVE)
    res_active = await service.get_active_account_by_uuid(active_acc.id)
    assert res_active.id == active_acc.id

    susp_acc = await account_factory(account_id="RT-SUSP-001", status=AccountStatus.SUSPENDED)
    with pytest.raises(AccountNotActiveError) as exc_info:
        await service.get_active_account_by_uuid(susp_acc.id)
    assert "suspended" in str(exc_info.value).lower()

    pend_acc = await account_factory(account_id="RT-PEND-001", status=AccountStatus.PENDING)
    with pytest.raises(AccountNotActiveError) as exc_info:
        await service.get_active_account_by_uuid(pend_acc.id)
    assert "pending" in str(exc_info.value).lower()

    exp_acc = await account_factory(account_id="RT-EXP-001", status=AccountStatus.EXPIRED)
    with pytest.raises(AccountNotActiveError) as exc_info:
        await service.get_active_account_by_uuid(exp_acc.id)
    assert "expired" in str(exc_info.value).lower()

    past_expiry = datetime.now(timezone.utc) - timedelta(minutes=5)
    expt_acc = await account_factory(
        account_id="RT-EXPT-001",
        status=AccountStatus.ACTIVE,
        subscription_expires_at=past_expiry,
    )
    with pytest.raises(AccountNotActiveError) as exc_info:
        await service.get_active_account_by_uuid(expt_acc.id)
    assert "timestamp expired" in str(exc_info.value).lower()
