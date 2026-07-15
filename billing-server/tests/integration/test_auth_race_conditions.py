import asyncio
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.models import RefreshToken
from app.services.refresh_tokens import RefreshTokenService
from app.services.exceptions import RefreshTokenReplayError, RefreshTokenServiceError, RefreshTokenRevokedError
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.device_repository import DeviceRepository
from app.config import settings

@pytest.mark.asyncio
async def test_concurrent_refresh_token_rotation_service_layer(db_session: AsyncSession, account_factory):
    """
    Test that concurrent requests to rotate the same valid refresh token
    result in exactly one success, and the others fail or trigger replay protection.
    We test this at the service layer by instantiating multiple independent DB sessions
    to correctly simulate parallel HTTP requests without sharing a single SQLAlchemy session.
    """
    # 1. Setup account and initial token using the standard test session
    account = await account_factory()
    repo = RefreshTokenRepository(db_session)
    device_repo = DeviceRepository(db_session)
    refresh_svc = RefreshTokenService(repo, device_repo)
    
    token_result = await refresh_svc.issue_refresh_token(
        account_id=account.id,
        device_guid="device-1"
    )
    # Ensure it's committed so other sessions can see it
    await db_session.commit()
    
    # 2. Fire N concurrent refresh requests using independent sessions
    N = 5
    engine = create_async_engine(settings.database_url.get_secret_value(), pool_size=10, max_overflow=20)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    
    async def rotate_with_new_session():
        async with async_session_maker() as session:
            svc = RefreshTokenService(RefreshTokenRepository(session), DeviceRepository(session))
            try:
                return await svc.rotate_refresh_token(token_result.token)
            except Exception as exc:
                return exc

    # Gather results concurrently
    results = await asyncio.gather(*(rotate_with_new_session() for _ in range(N)))
    
    # Clean up engine
    await engine.dispose()
    
    # 3. Analyze results
    successes = [r for r in results if not isinstance(r, Exception)]
    exceptions = [r for r in results if isinstance(r, Exception)]
    
    # Exactly one should succeed
    assert len(successes) == 1
    
    # The others should fail (due to row lock, the first commits, the others read the revoked token)
    assert len(exceptions) == N - 1
    
    # Subsequent reads of the same token after the first commits should trigger ReplayError
    replay_errors = [e for e in exceptions if isinstance(e, RefreshTokenReplayError)]
    
    # There could be an edge case where it's not a ReplayError if the row was locked and then they read the new state?
    # Wait, the old token is marked `is_revoked = True`. When the blocked transactions wake up, 
    # they read `is_revoked == True` and immediately throw RefreshTokenReplayError.
    assert len(replay_errors) == N - 1
    
    # 4. Verify DB state using the original db_session
    stmt = sa.select(RefreshToken).where(RefreshToken.account_id == account.id)
    result = await db_session.execute(stmt)
    all_tokens = result.scalars().all()
    
    # The replay protection mass-revokes all tokens for the account.
    # We should have the originally issued token (revoked by the first successful rotation),
    # the new token created by the first successful rotation (subsequently revoked by the replay attacks),
    # so we should have 2 tokens in total, BOTH revoked.
    assert len(all_tokens) == 2
    for token in all_tokens:
        assert token.is_revoked is True
