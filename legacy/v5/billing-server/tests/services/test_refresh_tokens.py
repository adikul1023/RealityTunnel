"""
test_refresh_tokens.py — Comprehensive Unit Tests for RefreshTokenService (Phase 1.3.4)
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DatabaseOperationError
from app.models import RefreshToken
from app.repositories import RefreshTokenRepository, DeviceRepository
from app.security import hash_refresh_token
from app.services import (
    RefreshTokenService,
    RefreshTokenResult,
    RefreshRotationResult,
    RefreshTokenInfo,
    RefreshTokenNotFoundError,
    RefreshTokenExpiredError,
    RefreshTokenRevokedError,
    RefreshTokenReplayError,
)


@pytest.fixture
def rtr_service(db_session: AsyncSession) -> RefreshTokenService:
    repo = RefreshTokenRepository(db_session)
    device_repo = DeviceRepository(db_session)
    return RefreshTokenService(repo, device_repo)


@pytest.mark.asyncio
async def test_issue_and_verify_refresh_token_success(
    rtr_service: RefreshTokenService, account_factory
):
    """Verify issuing a new refresh token and subsequently verifying it."""
    account = await account_factory()
    device_guid = "test-device-guid-001"

    issued = await rtr_service.issue_refresh_token(account.id, device_guid)
    assert isinstance(issued, RefreshTokenResult)
    assert len(issued.token) == 64  # 32 bytes hex encoded
    assert issued.device_guid == device_guid
    assert issued.account_id == account.id
    assert issued.expires_at > datetime.now(timezone.utc)

    # Verify the token
    verified = await rtr_service.verify_refresh_token(issued.token)
    assert isinstance(verified, RefreshTokenInfo)
    assert verified.account_id == account.id
    assert verified.device_guid == device_guid
    assert verified.is_revoked is False


@pytest.mark.asyncio
async def test_rotate_refresh_token_success(
    rtr_service: RefreshTokenService, account_factory
):
    """Verify normal refresh token rotation invalidates the old token and issues a new one."""
    account = await account_factory()
    device_guid = "test-device-guid-rotate"

    issued = await rtr_service.issue_refresh_token(account.id, device_guid)
    rotated = await rtr_service.rotate_refresh_token(issued.token)

    assert isinstance(rotated, RefreshRotationResult)
    assert rotated.new_token != issued.token
    assert len(rotated.new_token) == 64
    assert rotated.device_guid == device_guid
    assert rotated.account_id == account.id

    # The new token should be verifiable
    new_info = await rtr_service.verify_refresh_token(rotated.new_token)
    assert new_info.is_revoked is False
    assert new_info.device_guid == device_guid


@pytest.mark.asyncio
async def test_revoke_refresh_token_single(
    rtr_service: RefreshTokenService, account_factory
):
    """Verify revoking a single refresh token by plaintext string."""
    account = await account_factory()
    issued = await rtr_service.issue_refresh_token(account.id, "device-1")

    revoked = await rtr_service.revoke_refresh_token(issued.token)
    assert revoked is True

    # Attempting to revoke again returns False
    assert await rtr_service.revoke_refresh_token(issued.token) is False


@pytest.mark.asyncio
async def test_revoke_all_for_account(
    rtr_service: RefreshTokenService, account_factory
):
    """Verify bulk session revocation for an account."""
    account = await account_factory()
    token1 = await rtr_service.issue_refresh_token(account.id, "device-1")
    token2 = await rtr_service.issue_refresh_token(account.id, "device-2")

    count = await rtr_service.revoke_all_for_account(account.id)
    assert count == 2

    # Both tokens should now trigger replay/revoked exceptions upon verification attempt
    with pytest.raises(RefreshTokenReplayError):
        await rtr_service.verify_refresh_token(token1.token)
    with pytest.raises(RefreshTokenReplayError):
        await rtr_service.verify_refresh_token(token2.token)


@pytest.mark.asyncio
async def test_verify_expired_token(
    rtr_service: RefreshTokenService, account_factory, db_session: AsyncSession
):
    """Verify an expired token raises RefreshTokenExpiredError without mass revocation."""
    account = await account_factory()
    issued = await rtr_service.issue_refresh_token(account.id, "device-exp")

    # Manually expire the token in the database
    token_hash = hash_refresh_token(issued.token)
    repo = RefreshTokenRepository(db_session)
    entity = await repo.get_by_hash(token_hash)
    assert entity is not None
    entity.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db_session.commit()

    with pytest.raises(RefreshTokenExpiredError):
        await rtr_service.verify_refresh_token(issued.token)


@pytest.mark.asyncio
async def test_unknown_token_does_not_revoke_sessions(
    rtr_service: RefreshTokenService, account_factory
):
    """
    CRITICAL ARCHITECTURAL TEST:
    An unknown/unrecognized token string must raise RefreshTokenNotFoundError
    and MUST NOT trigger a mass logout or revoke active sessions.
    """
    account = await account_factory()
    valid_token = await rtr_service.issue_refresh_token(account.id, "device-safe")

    # Present an entirely random unknown token string
    unknown_token = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    with pytest.raises(RefreshTokenNotFoundError):
        await rtr_service.verify_refresh_token(unknown_token)

    # Confirm the valid token remains completely untouched and active!
    info = await rtr_service.verify_refresh_token(valid_token.token)
    assert info.is_revoked is False
    assert info.account_id == account.id


@pytest.mark.asyncio
async def test_tampered_or_malformed_token(
    rtr_service: RefreshTokenService
):
    """Verify malformed or invalid token types raise RefreshTokenNotFoundError."""
    with pytest.raises(RefreshTokenNotFoundError):
        await rtr_service.verify_refresh_token("")  # empty
    with pytest.raises(RefreshTokenNotFoundError):
        await rtr_service.verify_refresh_token("not-a-valid-hex-token")


@pytest.mark.asyncio
async def test_replay_attack_detection_revokes_all_sessions(
    rtr_service: RefreshTokenService, account_factory
):
    """
    REPLAY ATTACK DEFENSE TEST:
    1. Issue token A (device-1) and token B (device-2) for an account.
    2. Rotate token A -> produces token A2. Old token A is now marked is_revoked = True.
    3. Attempt to reuse old token A (simulate attacker or stale client replay).
    4. Expect RefreshTokenReplayError AND verify that ALL tokens (A2 and B) are immediately revoked!
    """
    account = await account_factory()
    res_a = await rtr_service.issue_refresh_token(account.id, "device-1")
    res_b = await rtr_service.issue_refresh_token(account.id, "device-2")

    # Rotate token A -> A2
    rot_a = await rtr_service.rotate_refresh_token(res_a.token)
    token_a2 = rot_a.new_token

    # At this point, A2 and B are valid and active
    info_a2 = await rtr_service.verify_refresh_token(token_a2)
    assert info_a2.is_revoked is False
    info_b = await rtr_service.verify_refresh_token(res_b.token)
    assert info_b.is_revoked is False

    # Now simulate REPLAY ATTACK: attempting to verify or rotate the old, revoked token A
    with pytest.raises(RefreshTokenReplayError) as exc_info:
        await rtr_service.verify_refresh_token(res_a.token)
    assert "Replay attack detected" in str(exc_info.value)

    # Check that ALL active tokens for this account (A2 and B) have been revoked!
    with pytest.raises(RefreshTokenReplayError):
        await rtr_service.verify_refresh_token(token_a2)
    with pytest.raises(RefreshTokenReplayError):
        await rtr_service.verify_refresh_token(res_b.token)


@pytest.mark.asyncio
async def test_rotation_atomicity_on_repository_failure(
    rtr_service: RefreshTokenService, account_factory, db_session: AsyncSession
):
    """
    TRANSACTIONAL ATOMICITY TEST:
    Mock repository failure halfway through rotation (when creating the new token entity).
    Verify that the entire transaction rolls back, leaving the old token active and un-revoked.
    """
    account = await account_factory()
    account_id = account.id
    issued = await rtr_service.issue_refresh_token(account_id, "device-atomic")

    # Mock repo.create to fail when attempting to persist the new token during rotation
    original_create = rtr_service.repo.create

    async def mock_create_fail(entity=None, **kwargs):
        # If it's a RefreshToken entity being created during rotation, raise an exception
        if isinstance(entity, RefreshToken):
            raise DatabaseOperationError("Simulated database failure during rotation insert")
        return await original_create(entity=entity, **kwargs)

    with patch.object(rtr_service.repo, "create", side_effect=mock_create_fail):
        with pytest.raises(DatabaseOperationError) as exc_info:
            await rtr_service.rotate_refresh_token(issued.token)
        assert "Simulated database failure" in str(exc_info.value)

    # Verify that because the transaction rolled back, the old token remains completely active!
    info = await rtr_service.verify_refresh_token(issued.token)
    assert info.is_revoked is False
    assert info.account_id == account_id


@pytest.mark.asyncio
async def test_device_binding_preservation(
    rtr_service: RefreshTokenService, account_factory
):
    """
    DEVICE BINDING TEST:
    Verify that refresh token rotation strictly preserves the original device_guid
    and that tokens cannot be silently migrated across devices.
    """
    account = await account_factory()
    original_guid = "device-guid-bound-8888"
    issued = await rtr_service.issue_refresh_token(account.id, original_guid)

    rotated = await rtr_service.rotate_refresh_token(issued.token)
    assert rotated.device_guid == original_guid

    # Verify in the database that the new session is bound to the original GUID
    info = await rtr_service.verify_refresh_token(rotated.new_token)
    assert info.device_guid == original_guid


@pytest.mark.asyncio
async def test_rotation_row_locking_invoked(
    rtr_service: RefreshTokenService, account_factory
):
    """
    CONCURRENCY RACE CONDITION DEFENSE TEST:
    Verify that rotate_refresh_token explicitly invokes get_by_hash with for_update=True
    to acquire a row-level exclusive lock (SELECT ... FOR UPDATE) before mutating token state.
    """
    account = await account_factory()
    issued = await rtr_service.issue_refresh_token(account.id, "device-lock-test")

    original_get_by_hash = rtr_service.repo.get_by_hash
    with patch.object(
        rtr_service.repo, "get_by_hash", wraps=original_get_by_hash
    ) as mock_get_by_hash:
        await rtr_service.rotate_refresh_token(issued.token)
        # Confirm for_update=True was passed to get_by_hash during rotation
        mock_get_by_hash.assert_called_once()
        _, kwargs = mock_get_by_hash.call_args
        assert kwargs.get("for_update") is True
