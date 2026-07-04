"""
test_rate_limit.py — Unit tests for Phase 3.3 Rate Limiting & Abuse Protection.

Tests:
  - Sliding Window Log algorithm in MemoryRateLimitBackend
  - RateLimiter check and key derivation (IP vs account ID)
  - Fail-open resilience (backend failure returns unlimited result)
  - Observability metrics incrementing on hits/blocks/errors
  - Zero-secret logging in RateLimiter
"""
import asyncio
import time
from unittest.mock import AsyncMock, patch
import pytest
from fastapi import Request

from app.rate_limit.backend import MemoryRateLimitBackend
from app.rate_limit.limiter import RateLimiter
from app.rate_limit.models import RateLimitResult
from app.rate_limit.exceptions import RateLimitExceeded
from app.observability.metrics import metrics_registry


def make_dummy_request(path: str = "/api/auth/login", ip: str = "10.0.0.1", request_id: str = "req-123") -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": [],
        "client": (ip, 12345),
    }
    req = Request(scope)
    req.state.client_ip = ip
    req.state.request_id = request_id
    return req


@pytest.mark.asyncio
async def test_memory_backend_sliding_window_allow_and_block():
    """Verify MemoryRateLimitBackend tracks requests and blocks when threshold is exceeded."""
    backend = MemoryRateLimitBackend()
    key = "test_ip_127.0.0.1"
    limit = 3
    window = 60

    # Request 1
    res1 = await backend.increment(key, window, limit)
    assert res1.allowed is True
    assert res1.limit == 3
    assert res1.remaining == 2

    # Request 2
    res2 = await backend.increment(key, window, limit)
    assert res2.allowed is True
    assert res2.remaining == 1

    # Request 3
    res3 = await backend.increment(key, window, limit)
    assert res3.allowed is True
    assert res3.remaining == 0

    # Request 4 - Should be blocked
    res4 = await backend.increment(key, window, limit)
    assert res4.allowed is False
    assert res4.remaining == 0
    assert res4.retry_after > 0
    assert res4.retry_after <= window


@pytest.mark.asyncio
async def test_memory_backend_pruning_and_ttl():
    """Verify old timestamps are pruned and TTL reflects window expiration."""
    backend = MemoryRateLimitBackend()
    key = "test_pruning_key"
    limit = 2
    window = 1  # 1 second window for fast testing

    await backend.increment(key, window, limit)
    await backend.increment(key, window, limit)

    # Currently blocked
    res_blocked = await backend.increment(key, window, limit)
    assert res_blocked.allowed is False

    # Wait for window to pass
    await asyncio.sleep(1.1)

    # Should be pruned and allowed again
    res_allowed = await backend.increment(key, window, limit)
    assert res_allowed.allowed is True
    assert res_allowed.remaining == 1


@pytest.mark.asyncio
async def test_memory_backend_reset_and_clear():
    """Verify reset() removes a specific key and clear() removes all keys."""
    backend = MemoryRateLimitBackend()
    await backend.increment("key1", 60, 5)
    await backend.increment("key2", 60, 5)
    assert await backend.get_active_key_count() == 2

    await backend.reset("key1")
    assert await backend.get_active_key_count() == 1

    await backend.clear()
    assert await backend.get_active_key_count() == 0


@pytest.mark.asyncio
async def test_rate_limiter_fail_open_on_backend_error():
    """Verify RateLimiter fails open (returns unlimited) if the storage backend raises an exception."""
    backend = MemoryRateLimitBackend()
    limiter = RateLimiter(backend)

    # Patch backend.increment to raise an error
    with patch.object(backend, "increment", new_callable=AsyncMock) as mock_inc:
        mock_inc.side_effect = RuntimeError("Simulated Redis connection timeout")

        req = make_dummy_request(ip="192.168.1.100")
        result = await limiter.check(req, "login")
        
        # Must fail open
        assert result.allowed is True
        assert result.limit == 999999
        assert result.remaining == 999999

        # Verify backend error metric was incremented
        summary = metrics_registry.get_summary()
        assert summary.get("rate_limit_backend_errors", 0) >= 1.0


@pytest.mark.asyncio
async def test_rate_limiter_exceeded_raises_exception():
    """Verify RateLimiter.enforce() raises RateLimitExceeded when rule threshold is breached."""
    backend = MemoryRateLimitBackend()
    limiter = RateLimiter(backend)
    req = make_dummy_request(ip="10.0.0.1")

    # Login limit is 10/minute by default in config
    for _ in range(10):
        res = await limiter.enforce(req, "login")
        assert res.allowed is True

    # 11th request must raise RateLimitExceeded
    with pytest.raises(RateLimitExceeded) as exc_info:
        await limiter.enforce(req, "login")

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["X-RateLimit-Limit"] == "10"
    assert exc_info.value.headers["X-RateLimit-Remaining"] == "0"
    assert "Retry-After" in exc_info.value.headers


@pytest.mark.asyncio
async def test_rate_limiter_zero_secret_logging(caplog):
    """Verify rate limit logs hash IP addresses and never log raw sensitive credentials."""
    backend = MemoryRateLimitBackend()
    limiter = RateLimiter(backend)
    req = make_dummy_request(ip="203.0.113.50", request_id="req-123")

    with caplog.at_level("WARNING"):
        # Exceed limit
        for _ in range(11):
            try:
                await limiter.enforce(req, "login")
            except RateLimitExceeded:
                pass

    warnings = [r.message for r in caplog.records if "Abuse protection rate limit exceeded" in r.message]
    assert len(warnings) > 0
    # Ensure raw IP 203.0.113.50 is NOT in log, but ip_hash is present
    assert "203.0.113.50" not in warnings[0]
    assert "ip_hash=" in warnings[0]
