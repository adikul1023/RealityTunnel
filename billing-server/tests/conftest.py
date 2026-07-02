"""
conftest.py — Pytest fixtures for async repository and persistence layer testing.
Runs directly against PostgreSQL in Docker.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import AsyncGenerator, Callable, Any
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import Account, SubscriptionStatus
from app.repositories import AccountRepository


@pytest_asyncio.fixture(scope="function", autouse=True)
async def dispose_engine() -> AsyncGenerator[None, None]:
    """Ensure async database engine is cleanly disposed after each test to avoid event loop reuse errors."""
    yield
    from app.database import engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an isolated async database session."""
    from sqlalchemy import text
    async with AsyncSessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE accounts CASCADE"))
        await session.commit()
        yield session
        await session.close()


@pytest_asyncio.fixture(scope="function")
async def account_factory(db_session: AsyncSession) -> AsyncGenerator[Callable[..., Any], None]:
    """
    Factory fixture to generate test Account instances.
    Automatically deletes created accounts after the test finishes,
    which cascades deletions to child devices and refresh tokens.
    """
    created_ids: list[uuid.UUID] = []
    repo = AccountRepository(db_session)

    async def _create(
        account_id: str | None = None,
        master_token_hash: str | None = None,
        marzban_username: str | None = None,
        status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    ) -> Account:
        if account_id is None:
            account_id = f"TEST-{uuid.uuid4().hex[:8].upper()}"
        if master_token_hash is None:
            master_token_hash = f"hash_{uuid.uuid4().hex}"
        acc = await repo.create(
            account_id=account_id,
            master_token_hash=master_token_hash,
            marzban_username=marzban_username,
            status=status,
        )
        created_ids.append(acc.id)
        return acc

    yield _create

    # Cleanup: delete all created test accounts
    for acc_id in created_ids:
        try:
            await repo.delete(acc_id)
        except Exception:
            pass
