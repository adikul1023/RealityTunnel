import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
import pytest_asyncio
from app.dependencies import get_current_admin_optional
from unittest.mock import AsyncMock, patch

@pytest_asyncio.fixture(scope="function")
async def async_client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

@pytest.mark.asyncio
async def test_health_anonymous_masks_db_error(async_client: AsyncClient):
    """M7: Anonymous callers see masked detail when DB fails."""
    # We patch verify_db to raise an exception
    with patch("app.routers.health.verify_db", new_callable=AsyncMock) as mock_verify:
        mock_verify.side_effect = RuntimeError("FATAL: terminating connection due to administrator command")
        
        resp = await async_client.get("/api/health") # Wait, is it /health or /api/health? 
        # Actually health is mapped to /health without /api prefix sometimes. 
        # Looking at app/routers/health.py, it's just router.get("/health").
        # Let's check main.py or just use /health
        
        # If it returns 404, we'll fix the path.
        if resp.status_code == 404:
            resp = await async_client.get("/health")

        assert resp.status_code == 503
        data = resp.json()
        
        # Must be masked
        assert data["detail"]["components"]["postgresql"]["status"] == "error"
        assert data["detail"]["components"]["postgresql"]["detail"] == "database unreachable"
        assert "FATAL" not in str(data)

@pytest.mark.asyncio
async def test_health_admin_shows_db_error(async_client: AsyncClient):
    """M7: Authenticated admin callers see the raw DB error."""
    # Override get_current_admin_optional to return a dummy admin object
    app.dependency_overrides[get_current_admin_optional] = lambda: {"id": "admin_123"}
    
    with patch("app.routers.health.verify_db", new_callable=AsyncMock) as mock_verify:
        mock_verify.side_effect = RuntimeError("FATAL: terminating connection due to administrator command")
        
        resp = await async_client.get("/health")
        if resp.status_code == 404:
            resp = await async_client.get("/api/health")

        assert resp.status_code == 503
        data = resp.json()
        
        # Must show raw error
        assert data["detail"]["components"]["postgresql"]["status"] == "error"
        assert "FATAL" in data["detail"]["components"]["postgresql"]["detail"]

    app.dependency_overrides.pop(get_current_admin_optional, None)
