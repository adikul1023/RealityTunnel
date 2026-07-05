"""
Async SQLAlchemy 2.x database engine and session factory.
"""
import logging
from typing import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

import time
from app.config import settings
from app.observability.metrics import metrics_registry
from app.performance.pooling import get_engine_pool_kwargs
from app.performance.profiler import profiler

logger = logging.getLogger(__name__)

# ── Engine ──────────────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,          # SQL logging in debug mode
    **get_engine_pool_kwargs(),
)


@event.listens_for(engine.sync_engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, execmany):
    if context:
        context._query_start_time = time.perf_counter()


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, execmany):
    metrics_registry.inc_counter("db_queries_total")
    if context and hasattr(context, "_query_start_time"):
        duration = time.perf_counter() - context._query_start_time
        profiler.record_latency("query", duration)


@event.listens_for(engine.sync_engine, "rollback")
def receive_rollback(conn):
    metrics_registry.inc_counter("db_transaction_failures_total")


# ── Session factory ─────────────────────────────────────────────────────────

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


# ── Declarative base (for models in later phases) ───────────────────────────

class Base(DeclarativeBase):
    pass


# ── Dependency ───────────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    async with AsyncSessionLocal() as session:
        yield session


# ── Health helper ────────────────────────────────────────────────────────────

async def verify_db() -> bool:
    """
    Execute a trivial query to confirm the database is reachable.
    Returns True on success, raises on failure.
    """
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return True
