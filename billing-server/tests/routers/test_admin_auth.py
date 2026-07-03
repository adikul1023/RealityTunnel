"""
test_admin_auth.py — HTTP Router & Cross-Domain Isolation Tests for Administrative Authentication.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_login_success(async_client: AsyncClient, admin_user_factory):
    """Verify successful login via POST /api/admin/login returns Admin JWT and role."""
    password = "AdminPassword2026!"
    await admin_user_factory(username="router_admin", password=password, is_super_admin=True)

    resp = await async_client.post(
        "/api/admin/login",
        json={"username": "router_admin", "password": password},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "Bearer"
    assert data["username"] == "router_admin"
    assert data["role"] == "super_admin"


@pytest.mark.asyncio
async def test_admin_login_invalid_password(async_client: AsyncClient, admin_user_factory):
    """Verify POST /api/admin/login with incorrect password returns 401 Unauthorized."""
    await admin_user_factory(username="router_admin_pwd", password="ValidPassword1!")

    resp = await async_client.post(
        "/api/admin/login",
        json={"username": "router_admin_pwd", "password": "WrongPassword99!"},
    )
    assert resp.status_code == 401, resp.text
    assert "Authentication failed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_login_unknown_user(async_client: AsyncClient):
    """Verify POST /api/admin/login with unknown username returns 401 Unauthorized."""
    resp = await async_client.post(
        "/api/admin/login",
        json={"username": "ghost_admin", "password": "AnyPassword1!"},
    )
    assert resp.status_code == 401, resp.text
    assert "Authentication failed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_login_inactive_user(async_client: AsyncClient, admin_user_factory):
    """Verify POST /api/admin/login for deactivated admin returns 401 Unauthorized."""
    password = "AdminPassword2026!"
    await admin_user_factory(username="inactive_admin", password=password, is_active=False)

    resp = await async_client.post(
        "/api/admin/login",
        json={"username": "inactive_admin", "password": password},
    )
    assert resp.status_code == 401, resp.text
    assert "Authentication failed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_login_mfa_enabled(async_client: AsyncClient, admin_user_factory):
    """Verify POST /api/admin/login for admin with MFA enabled returns 501 Not Implemented."""
    password = "AdminPassword2026!"
    await admin_user_factory(username="mfa_admin", password=password, mfa_enabled=True)

    resp = await async_client.post(
        "/api/admin/login",
        json={"username": "mfa_admin", "password": password},
    )
    assert resp.status_code == 501, resp.text
    assert "MFA for administrative accounts is not yet implemented" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_me_success(async_client: AsyncClient, admin_auth_headers_factory):
    """Verify GET /api/admin/me retrieves profile with valid admin bearer token."""
    headers, admin = await admin_auth_headers_factory(username="me_admin", is_super_admin=True)

    resp = await async_client.get("/api/admin/me", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == str(admin.id)
    assert data["username"] == "me_admin"
    assert data["is_super_admin"] is True
    assert data["is_active"] is True
    assert data["mfa_enabled"] is False


@pytest.mark.asyncio
async def test_admin_me_unauthorized_missing_token(async_client: AsyncClient):
    """Verify GET /api/admin/me without Authorization header returns 401."""
    resp = await async_client.get("/api/admin/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cross_domain_isolation_customer_token_rejected_on_admin_route(
    async_client: AsyncClient, auth_headers_factory
):
    """Verify a valid customer Access JWT is rejected when sent to a protected admin route."""
    customer_headers, _ = await auth_headers_factory(account_id="RT-CUST-0001")

    # Attempt to access protected admin route with customer token
    resp = await async_client.get("/api/admin/me", headers=customer_headers)
    assert resp.status_code == 401, resp.text
    assert "Authentication failed or token invalid" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_cross_domain_isolation_admin_token_rejected_on_customer_route(
    async_client: AsyncClient, admin_auth_headers_factory
):
    """Verify a valid Admin Access JWT is rejected when sent to a protected customer route."""
    admin_headers, _ = await admin_auth_headers_factory(username="iso_admin")

    # Attempt to access protected customer route (e.g. GET /api/devices) with admin token
    resp = await async_client.get("/api/devices", headers=admin_headers)
    assert resp.status_code == 401, resp.text
    assert "Authentication failed or token invalid" in resp.json()["detail"]
