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
        await session.execute(text("TRUNCATE TABLE accounts, connection_signals, admin_users CASCADE"))
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
        subscription_expires_at=None,
        **kwargs,
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
            subscription_expires_at=subscription_expires_at,
            **kwargs,
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


@pytest_asyncio.fixture(scope="function")
async def device_service(db_session: AsyncSession):
    from app.repositories import AccountRepository, DeviceRepository
    from app.services import DeviceService
    dev_repo = DeviceRepository(db_session)
    acc_repo = AccountRepository(db_session)
    return DeviceService(dev_repo, acc_repo)


@pytest_asyncio.fixture(scope="function")
async def signal_service(db_session: AsyncSession):
    from app.repositories import ConnectionSignalRepository
    from app.services import ConnectionSignalService
    repo = ConnectionSignalRepository(db_session)
    return ConnectionSignalService(repo)


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[Any, None]:
    from httpx import ASGITransport, AsyncClient
    from app.database import get_db
    from app.main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def auth_headers_factory(async_client, account_factory):
    import secrets
    from app.security import hash_master_token

    async def _helper(account_id: str = "RT-DEV-001") -> tuple[dict[str, str], Any]:
        master_token = secrets.token_hex(32)
        acc = await account_factory(account_id=account_id, master_token_hash=hash_master_token(master_token))
        login_resp = await async_client.post(
            "/api/auth/login",
            json={"account_id": account_id, "master_token": master_token, "device_guid": f"dev-{account_id}"},
        )
        assert login_resp.status_code == 200, login_resp.text
        token = login_resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}, acc

    return _helper


@pytest_asyncio.fixture(scope="function")
async def admin_user_factory(db_session: AsyncSession) -> AsyncGenerator[Callable[..., Any], None]:
    """Factory fixture to generate test AdminUser instances."""
    created_ids: list[uuid.UUID] = []
    from app.models.admin_user import AdminUser
    from app.repositories import AdminUserRepository
    from app.security import AdminPasswordService
    repo = AdminUserRepository(db_session)
    pwd_service = AdminPasswordService()

    async def _create(
        username: str | None = None,
        password: str | None = None,
        is_active: bool = True,
        is_super_admin: bool = False,
        mfa_enabled: bool = False,
        **kwargs,
    ) -> AdminUser:
        if username is None:
            username = f"admin_{uuid.uuid4().hex[:8]}"
        if password is None:
            password = "SecretAdminPassword123!"
        password_hash = pwd_service.hash_password(password)
        admin = await repo.create(
            username=username,
            password_hash=password_hash,
            is_active=is_active,
            is_super_admin=is_super_admin,
            mfa_enabled=mfa_enabled,
            **kwargs,
        )
        created_ids.append(admin.id)
        return admin

    yield _create

    for adm_id in created_ids:
        try:
            await repo.delete(adm_id)
        except Exception:
            pass


@pytest_asyncio.fixture(scope="function")
async def admin_auth_headers_factory(async_client, admin_user_factory):
    """Generate authenticated HTTP Authorization Bearer headers for a test AdminUser."""
    async def _helper(username: str = "test_admin", is_super_admin: bool = False) -> tuple[dict[str, str], Any]:
        password = "SecretAdminPassword123!"
        admin = await admin_user_factory(username=username, password=password, is_super_admin=is_super_admin)
        login_resp = await async_client.post(
            "/api/admin/login",
            json={"username": username, "password": password},
        )
        assert login_resp.status_code == 200, login_resp.text
        token = login_resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}, admin

    return _helper
