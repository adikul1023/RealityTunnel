"""
app/rate_limit/storage.py — Central storage backend provider for rate limiting (Phase 3.3).
Provides singleton access to the active RateLimitBackend, selected via
settings.rate_limit_backend (Finding H-3: memory | redis).
"""

from __future__ import annotations

import logging
from functools import lru_cache

from app.config import settings
from app.rate_limit.backend import (
    MemoryRateLimitBackend,
    RateLimitBackend,
    RedisRateLimitBackend,
)

logger = logging.getLogger(__name__)


@lru_cache
def get_rate_limit_backend() -> RateLimitBackend:
    """
    Return the configured RateLimitBackend singleton instance.

    settings.rate_limit_backend == "redis": uses RedisRateLimitBackend, backed by
    settings.redis_url. Required in production (enforced by app.core.startup_validator).

    settings.rate_limit_backend == "memory" (default): uses MemoryRateLimitBackend
    (Sliding Window Log). Suitable for local development and single-process testing only —
    state is process-local and does not survive restarts or scale across replicas.
    """
    backend_choice = (
        (getattr(settings, "rate_limit_backend", "memory") or "memory").strip().lower()
    )
    if backend_choice == "redis":
        logger.info("Rate limit backend: redis (%s)", settings.redis_url)
        return RedisRateLimitBackend(redis_url=settings.redis_url)

    logger.info("Rate limit backend: memory")
    return MemoryRateLimitBackend()
