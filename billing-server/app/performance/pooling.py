"""
pooling.py — Database connection pool monitoring, tuning, and statistics reporting.
"""
import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import settings
from app.observability.metrics import metrics_registry
from app.performance.exceptions import PoolingError

logger = logging.getLogger(__name__)


def get_engine_pool_kwargs(environment: str | None = None) -> dict[str, Any]:
    """
    Returns optimal SQLAlchemy engine pool configuration keyword arguments
    tailored to the deployment environment.
    """
    if "sqlite" in settings.database_url.get_secret_value():
        from sqlalchemy.pool import StaticPool
        return {"poolclass": StaticPool}

    env = (environment or settings.environment).lower()

    if env == "testing":
        # Small pool for unit test isolation
        return {
            "pool_pre_ping": True,
            "pool_size": 2,
            "max_overflow": 4,
            "pool_timeout": 10.0,
            "pool_recycle": 600,
        }
    elif env == "production":
        # Production pool configured for high concurrency
        return {
            "pool_pre_ping": settings.db_pool_pre_ping,
            "pool_size": max(10, settings.db_pool_size),
            "max_overflow": max(20, settings.db_max_overflow),
            "pool_timeout": settings.db_pool_timeout,
            "pool_recycle": settings.db_pool_recycle,
        }
    else:
        # Development / Staging defaults
        return {
            "pool_pre_ping": settings.db_pool_pre_ping,
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_timeout": settings.db_pool_timeout,
            "pool_recycle": settings.db_pool_recycle,
        }


def get_pool_status(engine: AsyncEngine | None = None) -> dict[str, Any]:
    """
    Inspects the active SQLAlchemy connection pool and returns utilization statistics.
    Also updates the `db_pool_usage` gauge in Prometheus metrics.
    """
    if engine is None:
        try:
            from app.database import engine as default_engine
            engine = default_engine
        except Exception as exc:
            raise PoolingError("Failed to import default database engine for pool inspection.") from exc

    try:
        pool = engine.pool
        size = getattr(pool, "size", 0)
        if callable(size):
            size = size()
        checked_in = getattr(pool, "checkedin", 0)
        if callable(checked_in):
            checked_in = checked_in()
        checked_out = getattr(pool, "checkedout", 0)
        if callable(checked_out):
            checked_out = checked_out()
        overflow = getattr(pool, "overflow", 0)
        if callable(overflow):
            overflow = overflow()

        total_capacity = size + (getattr(pool, "_max_overflow", 0) or 0)
        active_connections = checked_out
        utilization_percent = round((active_connections / total_capacity) * 100.0, 2) if total_capacity > 0 else 0.0

        # Update gauge
        metrics_registry.set_gauge("db_pool_usage", float(active_connections))

        return {
            "pool_size": size,
            "checked_in": checked_in,
            "checked_out": checked_out,
            "overflow": overflow,
            "total_capacity": total_capacity,
            "utilization_percent": utilization_percent,
            "status": "healthy" if utilization_percent < 80.0 else "degraded",
        }
    except Exception as exc:
        logger.warning(f"Error inspecting connection pool: {exc}")
        return {
            "pool_size": settings.db_pool_size,
            "checked_in": 0,
            "checked_out": 0,
            "overflow": 0,
            "total_capacity": settings.db_pool_size + settings.db_max_overflow,
            "utilization_percent": 0.0,
            "status": "unknown",
            "error": str(exc),
        }
