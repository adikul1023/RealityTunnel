"""
test_pooling.py — Tests for Phase 3.6 database connection pooling management and statistics.
"""
import pytest
from app.performance.pooling import get_engine_pool_kwargs, get_pool_status
from app.config import settings


def test_engine_pool_kwargs_environment_defaults(monkeypatch):
    monkeypatch.setattr(settings.database_url, "get_secret_value", lambda: "postgresql+asyncpg://user:pass@localhost/db")
    test_kwargs = get_engine_pool_kwargs("testing")
    assert test_kwargs["pool_size"] == 2
    assert test_kwargs["max_overflow"] == 4
    assert test_kwargs["pool_pre_ping"] is True

    prod_kwargs = get_engine_pool_kwargs("production")
    assert prod_kwargs["pool_size"] >= 10
    assert prod_kwargs["max_overflow"] >= 20
    assert prod_kwargs["pool_pre_ping"] == settings.db_pool_pre_ping


def test_pool_status_inspection():
    status = get_pool_status()
    assert "pool_size" in status
    assert "checked_in" in status
    assert "checked_out" in status
    assert "utilization_percent" in status
    assert status["status"] in ("healthy", "degraded", "unknown")
