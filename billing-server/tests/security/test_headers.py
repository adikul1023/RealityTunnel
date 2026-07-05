"""
test_headers.py — Unit and integration tests for security headers middleware (Phase 3.5).
"""
import pytest
from httpx import AsyncClient

from app.observability.metrics import metrics_registry


@pytest.mark.asyncio
async def test_security_headers_present_and_metrics_increment(async_client: AsyncClient):
    """Verify that HTTP responses include all configured production security headers."""
    initial_cnt = metrics_registry.get_summary().get("security_headers_applied_total", 0)

    res = await async_client.get("/")
    assert res.status_code == 200

    headers = res.headers
    assert "Strict-Transport-Security" in headers
    assert "Content-Security-Policy" in headers
    assert "X-Frame-Options" in headers
    assert "X-Content-Type-Options" in headers
    assert "Referrer-Policy" in headers
    assert "Permissions-Policy" in headers
    assert "Cross-Origin-Opener-Policy" in headers
    assert "Cross-Origin-Resource-Policy" in headers
    assert "Cross-Origin-Embedder-Policy" in headers

    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-Content-Type-Options"] == "nosniff"

    new_cnt = metrics_registry.get_summary().get("security_headers_applied_total", 0)
    assert new_cnt == initial_cnt + 1
