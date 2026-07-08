"""
cache.py — Optional caching abstraction layer with strict zero-secret domain security policy.
Supports MemoryCache and stubbed RedisCache for future production scaling.
"""
import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any
from collections import OrderedDict

from app.config import settings
from app.observability.metrics import metrics_registry
from app.performance.exceptions import CacheError

logger = logging.getLogger(__name__)

# Strict Security Whitelisting & Blacklisting
ALLOWED_CACHE_PREFIXES: tuple[str, ...] = (
    "plan:",
    "config:",
    "flag:",
    "health:",
)

FORBIDDEN_KEYWORDS: tuple[str, ...] = (
    "cred",
    "token",
    "payment",
    "device",
    "auth",
    "password",
    "secret",
    "jwt",
    "account",
    "master",
    "vless",
    "key",
)


def validate_cache_key(key: str) -> None:
    """
    Enforces that only non-sensitive domain data is cached.
    Raises CacheError if a key contains forbidden terms or lacks a whitelisted prefix.
    """
    key_lower = key.lower()
    for word in FORBIDDEN_KEYWORDS:
        if word in key_lower:
            raise CacheError(f"Security violation: Prohibited keyword '{word}' detected in cache key '{key}'.")

    if not any(key_lower.startswith(prefix) for prefix in ALLOWED_CACHE_PREFIXES):
        raise CacheError(
            f"Security violation: Cache key '{key}' does not start with an allowed prefix: {ALLOWED_CACHE_PREFIXES}."
        )


class BaseCache(ABC):
    """Abstract caching backend interface."""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        pass

    @abstractmethod
    async def clear(self) -> None:
        pass

    @abstractmethod
    async def get_stats(self) -> dict[str, Any]:
        pass


class MemoryCache(BaseCache):
    """
    Thread-safe in-memory async cache with TTL expiration.
    Used for local development, testing, and single-node production deployment.
    """

    def __init__(self, maxsize: int = 10000) -> None:
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0
        self.maxsize = maxsize

    def _update_metrics(self) -> None:
        total = self._hits + self._misses
        ratio = (self._hits / total) if total > 0 else 0.0
        metrics_registry.set_gauge("cache_hit_ratio", round(ratio, 4))

    async def get(self, key: str) -> Any | None:
        if not settings.cache_enabled:
            return None
        validate_cache_key(key)
        async with self._lock:
            if key not in self._store:
                self._misses += 1
                metrics_registry.inc_counter("cache_misses_total")
                self._update_metrics()
                return None

            value, expire_at = self._store[key]
            if expire_at > 0 and time.time() > expire_at:
                del self._store[key]
                self._misses += 1
                metrics_registry.inc_counter("cache_misses_total")
                self._update_metrics()
                return None

            self._hits += 1
            metrics_registry.inc_counter("cache_hits_total")
            self._update_metrics()
            
            # LRU behavior: move to end (newest)
            self._store.move_to_end(key)
            return value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        if not settings.cache_enabled:
            return
        validate_cache_key(key)
        effective_ttl = ttl if ttl is not None else settings.cache_ttl_seconds
        expire_at = (time.time() + effective_ttl) if effective_ttl > 0 else 0.0
        async with self._lock:
            # Add or update the key
            self._store[key] = (value, expire_at)
            # Move to end to mark as newest
            self._store.move_to_end(key)
            
            # Evict oldest (least recently used) if we exceed maxsize
            if len(self._store) > self.maxsize:
                # popitem(last=False) removes the first (oldest) item
                self._store.popitem(last=False)

    async def delete(self, key: str) -> bool:
        validate_cache_key(key)
        async with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0
            metrics_registry.set_gauge("cache_hit_ratio", 0.0)

    async def get_stats(self) -> dict[str, Any]:
        async with self._lock:
            now = time.time()
            active_keys = sum(1 for _, exp in self._store.values() if exp == 0 or exp > now)
            total = self._hits + self._misses
            ratio = (self._hits / total) if total > 0 else 0.0
            return {
                "backend": "memory",
                "enabled": settings.cache_enabled,
                "active_keys": active_keys,
                "hits": self._hits,
                "misses": self._misses,
                "hit_ratio": round(ratio, 4),
            }


class RedisCache(BaseCache):
    """
    Redis cache abstraction for future multi-node distributed deployments.
    Enforces identical zero-secret validation rules before serializing payloads.
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url
        self._connected = False

    async def get(self, key: str) -> Any | None:
        validate_cache_key(key)
        raise NotImplementedError("RedisCache is stubbed for future horizontal scaling in Phase 3.6.")

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        validate_cache_key(key)
        raise NotImplementedError("RedisCache is stubbed for future horizontal scaling in Phase 3.6.")

    async def delete(self, key: str) -> bool:
        validate_cache_key(key)
        raise NotImplementedError("RedisCache is stubbed for future horizontal scaling in Phase 3.6.")

    async def clear(self) -> None:
        raise NotImplementedError("RedisCache is stubbed for future horizontal scaling in Phase 3.6.")

    async def get_stats(self) -> dict[str, Any]:
        return {
            "backend": "redis",
            "enabled": settings.cache_enabled,
            "connected": self._connected,
            "note": "Redis cache stubbed for future deployment",
        }


class NoOpCache(BaseCache):
    """No-op cache used when caching is disabled via configuration."""

    async def get(self, key: str) -> Any | None:
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        pass

    async def delete(self, key: str) -> bool:
        return False

    async def clear(self) -> None:
        pass

    async def get_stats(self) -> dict[str, Any]:
        return {
            "backend": "noop",
            "enabled": False,
            "active_keys": 0,
            "hits": 0,
            "misses": 0,
            "hit_ratio": 0.0,
        }


# Global cache instance
_cache_instance: BaseCache | None = None


def get_cache() -> BaseCache:
    """Returns the singleton cache abstraction instance."""
    global _cache_instance
    if _cache_instance is None:
        if not settings.cache_enabled:
            _cache_instance = NoOpCache()
        elif settings.cache_backend.lower() == "redis":
            _cache_instance = RedisCache()
        else:
            _cache_instance = MemoryCache()
    return _cache_instance


def reset_cache_backend() -> None:
    """Reset global cache singleton (for test isolation)."""
    global _cache_instance
    _cache_instance = None
