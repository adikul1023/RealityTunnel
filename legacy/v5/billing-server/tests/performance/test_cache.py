"""
test_cache.py — Tests for Phase 3.6 secure caching abstraction.
"""
import asyncio
import pytest

from app.performance.cache import MemoryCache, validate_cache_key, get_cache
from app.performance.exceptions import CacheError
from app.config import settings


@pytest.mark.asyncio
async def test_memory_cache_basic_ops():
    cache = MemoryCache()
    await cache.clear()

    key = "plan:pro_yearly"
    val = {"name": "Pro Yearly", "price": 99.0}

    assert await cache.get(key) is None
    await cache.set(key, val, ttl=60)
    assert await cache.get(key) == val

    stats = await cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["active_keys"] == 1

    await cache.delete(key)
    assert await cache.get(key) is None


@pytest.mark.asyncio
async def test_memory_cache_ttl_expiration():
    cache = MemoryCache()
    await cache.clear()

    key = "flag:feature_alpha"
    await cache.set(key, True, ttl=1)
    assert await cache.get(key) is True

    # Simulate expiration by setting TTL manually in store to past timestamp
    cache._store[key] = (True, 0.001)
    await asyncio.sleep(0.01)
    assert await cache.get(key) is None


@pytest.mark.asyncio
async def test_cache_security_policy_rejection():
    cache = MemoryCache()

    # Rejection of forbidden keyword even if prefix is valid
    with pytest.raises(CacheError, match="Prohibited keyword"):
        await cache.set("plan:pro_token_secret", "secret_value")

    # Rejection of invalid prefix
    with pytest.raises(CacheError, match="does not start with an allowed prefix"):
        await cache.set("user_profile:1234", "data")

    # Rejection of credentials keyword
    with pytest.raises(CacheError, match="Prohibited keyword"):
        validate_cache_key("config:db_password")


@pytest.mark.asyncio
async def test_get_cache_singleton():
    c1 = get_cache()
    c2 = get_cache()
    assert c1 is c2
