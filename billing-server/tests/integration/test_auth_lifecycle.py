import pytest
from httpx import AsyncClient

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.account import SubscriptionStatus

@pytest.mark.asyncio
async def test_logout_revokes_token(db_session: AsyncSession, async_client: AsyncClient, account_factory, auth_headers_factory):
    """
    Test that calling /logout successfully revokes the refresh token.
    """
    # Actually auth_headers_factory uses random master tokens. So we just do it manually.
    import secrets
    from app.security import hash_master_token
    
    master_token = secrets.token_hex(32)
    account = await account_factory(account_id="RT-LOG-1", master_token_hash=hash_master_token(master_token))
    
    login_resp = await async_client.post(
        "/api/auth/login",
        json={"account_id": "RT-LOG-1", "master_token": master_token, "device_guid": "dev-1"},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]
    access_token = login_resp.json()["access_token"]
    
    # 1. Logout
    logout_resp = await async_client.post(
        "/api/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert logout_resp.status_code == 200
    
    # 2. Try to refresh with the revoked token (should fail)
    refresh_resp = await async_client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 401
    assert "Authentication failed or token invalid" in refresh_resp.text


@pytest.mark.asyncio
async def test_suspended_account_cannot_refresh(db_session: AsyncSession, async_client: AsyncClient, account_factory):
    import secrets
    from app.security import hash_master_token
    from app.repositories import AccountRepository
    
    master_token = secrets.token_hex(32)
    account = await account_factory(account_id="RT-SUSP-1", master_token_hash=hash_master_token(master_token))
    
    login_resp = await async_client.post(
        "/api/auth/login",
        json={"account_id": "RT-SUSP-1", "master_token": master_token, "device_guid": "dev-1"},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]
    
    # Suspend the account in the database
    account.status = SubscriptionStatus.SUSPENDED
    await db_session.commit()
    
    # Try to refresh
    refresh_resp = await async_client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    # The refresh should fail because the account is suspended
    assert refresh_resp.status_code in (401, 403)
