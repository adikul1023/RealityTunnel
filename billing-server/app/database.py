"""
Async SQLAlchemy 2.x database engine and session factory.
"""
import logging
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

# ── Engine ──────────────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,          # SQL logging in debug mode
    pool_pre_ping=True,           # validate connections before use
    pool_size=5,
    max_overflow=10,
)

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
