import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_cors_preflight_register_localhost(async_client: AsyncClient):
    """Test that OPTIONS /api/auth/register responds with 200 OK and CORS headers for localhost:3000."""
    response = await async_client.options(
        "/api/auth/register",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "POST" in response.headers.get("access-control-allow-methods", "")

@pytest.mark.asyncio
async def test_cors_preflight_login_stealthy_co_in(async_client: AsyncClient):
    """Test that OPTIONS /api/auth/login responds with 200 OK and CORS headers for stealthy.co.in."""
    response = await async_client.options(
        "/api/auth/login",
        headers={
            "Origin": "https://stealthy.co.in",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://stealthy.co.in"
