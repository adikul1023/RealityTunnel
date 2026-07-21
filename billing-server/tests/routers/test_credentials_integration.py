"""
test_credentials_integration.py — Router Integration Tests for Phase 2.4 VPN Credential API.
Tests authenticated access, dependency wiring, error mappings (401, 404, 400, 409, 500),
rotation, revocation, and restoration endpoints.
"""
from __future__ import annotations

import secrets
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_marzban_provider
from app.main import app
from app.models import ProvisioningProfile, ProvisioningState
from app.security import hash_master_token
from app.services.provisioning.provider import ProvisionedUserDTO, ProvisioningProvider


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Yield an httpx AsyncClient configured with overridden database dependencies."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_provider() -> AsyncMock:
    provider = AsyncMock(spec=ProvisioningProvider)
    provider.get_user.return_value = ProvisionedUserDTO(
        remote_user_id="remote_user_test",
        status="active",
        links=[
            "vless://client-uuid-999@vpn.realitytunnel.com:443?type=tcp&security=reality&pbk=mock_pbk_value&sni=sni.tunnel.com&sid=mock_sid_value#remote_user_test"
        ],
    )
    provider.reset_user_credentials.return_value = ProvisionedUserDTO(
        remote_user_id="remote_user_test",
        status="active",
        links=[
            "vless://rotated-uuid-888@vpn.realitytunnel.com:443?type=tcp&security=reality&pbk=rotated_pbk&sni=sni.tunnel.com&sid=rotated_sid#remote_user_test"
        ],
    )
    return provider


async def get_auth_headers(async_client: AsyncClient, account_factory, account_id: str = "RT-CRED-001") -> tuple[dict[str, str], any]:
    """Helper to create account, login, and return authorization header + account object."""
    master_token = secrets.token_hex(32)
    acc = await account_factory(account_id=account_id, master_token_hash=hash_master_token(master_token))
    login_resp = await async_client.post(
        "/api/auth/login",
        json={"account_id": account_id, "master_token": master_token, "device_guid": f"dev-{account_id}", "client_type": "desktop"},
    )
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, acc


async def create_db_profile(db_session: AsyncSession, account_id: uuid.UUID) -> ProvisioningProfile:
    profile = ProvisioningProfile(
        id=uuid.uuid4(),
        account_id=account_id,
        remote_user_id="remote_user_test",
        provisioning_state=ProvisioningState.ACTIVE,
    )
    db_session.add(profile)
    await db_session.commit()
    return profile


# ── Integration Tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_credentials_unauthorized(async_client: AsyncClient):
    """GET /api/credentials without token returns 401."""
    resp = await async_client.get("/api/credentials")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_credentials_not_found(async_client: AsyncClient, account_factory):
    """GET /api/credentials with valid token but no profile returns 404."""
    headers, acc = await get_auth_headers(async_client, account_factory, "RT-CRED-NF")
    resp = await async_client.get("/api/credentials", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_credentials_success(
    async_client: AsyncClient,
    account_factory,
    db_session: AsyncSession,
    mock_provider: AsyncMock,
):
    """GET /api/credentials returns complete canonical properties and singbox config."""
    app.dependency_overrides[get_marzban_provider] = lambda: mock_provider
    try:
        headers, acc = await get_auth_headers(async_client, account_factory, "RT-CRED-OK")
        await create_db_profile(db_session, acc.id)

        resp = await async_client.get("/api/credentials", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["uuid"] == "client-uuid-999"
        assert data["server_hostname"] == "vpn.realitytunnel.com"
        assert "outbounds" in data["client_config"]
    finally:
        app.dependency_overrides.pop(get_marzban_provider, None)


@pytest.mark.asyncio
async def test_get_vless_and_singbox(
    async_client: AsyncClient,
    account_factory,
    db_session: AsyncSession,
    mock_provider: AsyncMock,
):
    """Verify specific endpoints for VLESS URI and sing-box JSON."""
    app.dependency_overrides[get_marzban_provider] = lambda: mock_provider
    try:
        headers, acc = await get_auth_headers(async_client, account_factory, "RT-CRED-LINKS")
        await create_db_profile(db_session, acc.id)

        resp_vless = await async_client.get("/api/credentials/vless", headers=headers)
        assert resp_vless.status_code == 200
        assert "vless://" in resp_vless.json()["vless_uri"]

        resp_sb = await async_client.get("/api/credentials/sing-box", headers=headers)
        assert resp_sb.status_code == 200
        assert resp_sb.json()["config"]["log"]["level"] == "info"
    finally:
        app.dependency_overrides.pop(get_marzban_provider, None)


@pytest.mark.asyncio
async def test_regenerate_credentials_success(
    async_client: AsyncClient,
    account_factory,
    db_session: AsyncSession,
    mock_provider: AsyncMock,
):
    """POST /api/credentials/regenerate rotates UUID and returns updated profile."""
    app.dependency_overrides[get_marzban_provider] = lambda: mock_provider
    try:
        headers, acc = await get_auth_headers(async_client, account_factory, "RT-CRED-ROT")
        await create_db_profile(db_session, acc.id)

        resp = await async_client.post("/api/credentials/regenerate", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["uuid"] == "rotated-uuid-888"
        mock_provider.reset_user_credentials.assert_called_once_with("remote_user_test")
    finally:
        app.dependency_overrides.pop(get_marzban_provider, None)


@pytest.mark.asyncio
async def test_revoke_and_restore_credentials(
    async_client: AsyncClient,
    account_factory,
    db_session: AsyncSession,
    mock_provider: AsyncMock,
):
    """Verify full revocation and restoration lifecycle via API."""
    app.dependency_overrides[get_marzban_provider] = lambda: mock_provider
    try:
        headers, acc = await get_auth_headers(async_client, account_factory, "RT-CRED-REV")
        await create_db_profile(db_session, acc.id)

        # 1. Revoke credentials
        resp_rev = await async_client.post("/api/credentials/revoke", headers=headers)
        assert resp_rev.status_code == 200
        assert resp_rev.json()["status"] == "revoked"

        # 2. Try revoking again -> 400
        resp_rev_dup = await async_client.post("/api/credentials/revoke", headers=headers)
        assert resp_rev_dup.status_code == 400

        # 3. Restore credentials
        resp_res = await async_client.post("/api/credentials/restore", headers=headers)
        assert resp_res.status_code == 200
        assert resp_res.json()["status"] == "restored"

        # 4. Try restoring again -> 409
        resp_res_dup = await async_client.post("/api/credentials/restore", headers=headers)
        assert resp_res_dup.status_code == 409
    finally:
        app.dependency_overrides.pop(get_marzban_provider, None)
