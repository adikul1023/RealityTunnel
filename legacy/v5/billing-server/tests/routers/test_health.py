import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_livez_ok(async_client: AsyncClient):
    """Test that /livez returns 200 OK instantly."""
    response = await async_client.get("/livez")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_ok(async_client: AsyncClient):
    """Test that /health returns 200 OK instantly."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_readyz_ok(async_client: AsyncClient):
    """Test that /readyz returns 200 OK and checks database."""
    response = await async_client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"


@pytest.mark.asyncio
async def test_admin_health_unauthorized(async_client: AsyncClient):
    """Test that /api/admin/system-health requires authentication."""
    response = await async_client.get("/api/admin/system-health")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_health_authorized(async_client: AsyncClient, admin_auth_headers_factory):
    """Test that /api/admin/system-health returns deep diagnostics for admins."""
    headers, _ = await admin_auth_headers_factory(is_super_admin=True)
    response = await async_client.get("/api/admin/system-health", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "degraded", "error")
