"""
test_rate_limit.py — Router integration tests for Phase 3.3 Rate Limiting & Abuse Protection.

Tests:
  - Enforces 10/min rate limit on customer /api/auth/login
  - Enforces 5/min rate limit on admin /api/admin/login
  - Verifies HTTP 429 response body and rate limit headers (X-RateLimit-*, Retry-After)
  - Verifies fail-open behavior at HTTP router level when storage backend fails
"""
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient

from app.rate_limit.storage import get_rate_limit_backend


@pytest.mark.asyncio
async def test_auth_login_rate_limit_enforcement(async_client: AsyncClient):
    """Verify customer login endpoint enforces 10/minute rate limit and returns 429 on 11th request."""
    url = "/api/auth/login"
    payload = {"account_id": "ACC-1234-5678", "master_token": "mt_secret_token", "device_guid": "dev-1"}

    # Make 10 requests within limit
    for i in range(10):
        resp = await async_client.post(url, json=payload)
        # 401 because credentials are bogus, but rate limit allowed it through
        assert resp.status_code in (401, 200), f"Request {i+1} failed with {resp.status_code}: {resp.text}"
        assert "X-RateLimit-Limit" in resp.headers
        assert resp.headers["X-RateLimit-Limit"] == "10"

    # 11th request must be blocked with HTTP 429
    resp_429 = await async_client.post(url, json=payload)
    assert resp_429.status_code == 429, resp_429.text
    assert resp_429.headers["X-RateLimit-Limit"] == "10"
    assert resp_429.headers["X-RateLimit-Remaining"] == "0"
    assert "Retry-After" in resp_429.headers

    data = resp_429.json()
    assert data["detail"] == "Rate limit exceeded"
    assert "retry_after" in data


@pytest.mark.asyncio
async def test_admin_login_rate_limit_enforcement(async_client: AsyncClient):
    """Verify admin login endpoint enforces 5/minute rate limit and returns 429 on 6th request."""
    url = "/api/admin/login"
    payload = {"username": "admin", "password": "wrongpassword"}

    # Make 5 requests within limit
    for _ in range(5):
        resp = await async_client.post(url, json=payload)
        assert resp.status_code in (401, 200)
        assert resp.headers["X-RateLimit-Limit"] == "5"

    # 6th request must be blocked with HTTP 429
    resp_429 = await async_client.post(url, json=payload)
    assert resp_429.status_code == 429
    assert resp_429.headers["X-RateLimit-Remaining"] == "0"
    assert resp_429.json()["detail"] == "Rate limit exceeded"


@pytest.mark.asyncio
async def test_router_fail_open_on_storage_backend_error(async_client: AsyncClient):
    """Verify that if the rate limit storage backend fails, traffic fails open without 500 error."""
    backend = get_rate_limit_backend()
    url = "/api/auth/login"
    payload = {"account_id": "ACC-9999-8888", "master_token": "mt_secret_token", "device_guid": "dev-2"}

    with patch.object(backend, "increment", new_callable=AsyncMock) as mock_inc:
        mock_inc.side_effect = RuntimeError("Redis cluster outage simulated")

        resp = await async_client.post(url, json=payload)
        # Should NOT be 500 or 429! Must fail open and reach the auth handler (returning 401 or 200)
        assert resp.status_code in (401, 200), f"Fail open failed, got {resp.status_code}: {resp.text}"
        # Unlimited fallback header should be attached
        assert resp.headers["X-RateLimit-Limit"] == "999999"
