import pytest
import asyncio
from app.performance.cache import MemoryCache

@pytest.mark.asyncio
async def test_memory_cache_lru_eviction():
    # Capacity of 3
    cache = MemoryCache(maxsize=3)
    
    # Insert config:A, config:B, config:C
    await cache.set("config:A", 1)
    await cache.set("config:B", 2)
    await cache.set("config:C", 3)
    
    # Touch config:A to make it recently used
    assert await cache.get("config:A") == 1
    
    # Insert config:D, should evict config:B (least recently used)
    await cache.set("config:D", 4)
    
    # Verify config:B is gone
    assert await cache.get("config:B") is None
    
    # Verify config:A, config:C, config:D exist
    assert await cache.get("config:A") == 1
    assert await cache.get("config:C") == 3
    assert await cache.get("config:D") == 4
    
    # Touch config:C
    assert await cache.get("config:C") == 3
    
    # Insert config:E, should evict config:A (least recently used, since config:C was just touched, config:D was just inserted)
    await cache.set("config:E", 5)
    
    assert await cache.get("config:A") is None
    assert await cache.get("config:C") == 3
    assert await cache.get("config:D") == 4
    assert await cache.get("config:E") == 5
