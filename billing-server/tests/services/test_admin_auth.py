"""
test_admin_auth.py — Unit & Integration tests for AdminAuthenticationService, AdminPasswordService, and AdminJWTService.
"""
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import EntityNotFoundError
from app.repositories import AdminUserRepository
from app.security import AdminPasswordService, AdminJWTService, JWTService
from app.services import (
    AdminAuthenticationService,
    AdminAuthReason,
    AdminAuthResult,
    AdminNotActiveError,
    MFANotImplementedYet,
)
from app.services.exceptions import InvalidAdminTokenError, InvalidTokenError


@pytest.mark.asyncio
async def test_admin_authenticate_success(db_session: AsyncSession, admin_user_factory):
    """Verify admin authentication succeeds with valid credentials and issues Admin JWT."""
    repo = AdminUserRepository(db_session)
    pwd_service = AdminPasswordService()
    jwt_service = AdminJWTService()
    service = AdminAuthenticationService(repo, pwd_service, jwt_service)

    password = "SuperSecretPassword99!"
    admin = await admin_user_factory(username="admin_succ", password=password, is_super_admin=True)

    result = await service.authenticate("admin_succ", password)
    assert isinstance(result, AdminAuthResult)
    assert result.success is True
    assert result.reason == AdminAuthReason.SUCCESS
    assert result.admin_user is not None
    assert result.admin_user.id == admin.id
    assert result.access_token is not None

    # Verify last_login_at updated
    updated_admin = await repo.get_by_id(admin.id)
    assert updated_admin.last_login_at is not None


@pytest.mark.asyncio
async def test_admin_authenticate_unknown_username(db_session: AsyncSession):
    """Verify authentication against non-existent username returns USER_NOT_FOUND and runs timing defense."""
    repo = AdminUserRepository(db_session)
    pwd_service = AdminPasswordService()
    jwt_service = AdminJWTService()
    service = AdminAuthenticationService(repo, pwd_service, jwt_service)

    result = await service.authenticate("nonexistent_admin", "any_password")
    assert result.success is False
    assert result.reason == AdminAuthReason.USER_NOT_FOUND
    assert result.access_token is None


@pytest.mark.asyncio
async def test_admin_authenticate_invalid_password(db_session: AsyncSession, admin_user_factory):
    """Verify authentication with incorrect password returns INVALID_PASSWORD."""
    repo = AdminUserRepository(db_session)
    pwd_service = AdminPasswordService()
    jwt_service = AdminJWTService()
    service = AdminAuthenticationService(repo, pwd_service, jwt_service)

    await admin_user_factory(username="admin_wrong_pwd", password="CorrectPassword123!")

    result = await service.authenticate("admin_wrong_pwd", "WrongPassword456!")
    assert result.success is False
    assert result.reason == AdminAuthReason.INVALID_PASSWORD
    assert result.access_token is None


@pytest.mark.asyncio
async def test_admin_authenticate_inactive_account(db_session: AsyncSession, admin_user_factory):
    """Verify authentication with deactivated admin returns USER_INACTIVE."""
    repo = AdminUserRepository(db_session)
    pwd_service = AdminPasswordService()
    jwt_service = AdminJWTService()
    service = AdminAuthenticationService(repo, pwd_service, jwt_service)

    password = "CorrectPassword123!"
    await admin_user_factory(username="admin_inactive", password=password, is_active=False)

    result = await service.authenticate("admin_inactive", password)
    assert result.success is False
    assert result.reason == AdminAuthReason.USER_INACTIVE
    assert result.access_token is None


@pytest.mark.asyncio
async def test_admin_authenticate_mfa_enabled(db_session: AsyncSession, admin_user_factory):
    """Verify authentication with MFA enabled raises MFANotImplementedYet to block rollout bypass."""
    repo = AdminUserRepository(db_session)
    pwd_service = AdminPasswordService()
    jwt_service = AdminJWTService()
    service = AdminAuthenticationService(repo, pwd_service, jwt_service)

    password = "CorrectPassword123!"
    await admin_user_factory(username="admin_mfa", password=password, mfa_enabled=True)

    with pytest.raises(MFANotImplementedYet) as exc_info:
        await service.authenticate("admin_mfa", password)
    assert "MFA for administrative accounts is not yet implemented" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_active_admin_by_id(db_session: AsyncSession, admin_user_factory):
    """Verify get_active_admin_by_id retrieves active users and rejects inactive/missing ones."""
    repo = AdminUserRepository(db_session)
    pwd_service = AdminPasswordService()
    jwt_service = AdminJWTService()
    service = AdminAuthenticationService(repo, pwd_service, jwt_service)

    active_admin = await admin_user_factory(username="admin_active_id", is_active=True)
    inactive_admin = await admin_user_factory(username="admin_inactive_id", is_active=False)

    fetched = await service.get_active_admin_by_id(active_admin.id)
    assert fetched.id == active_admin.id

    with pytest.raises(AdminNotActiveError):
        await service.get_active_admin_by_id(inactive_admin.id)

    with pytest.raises(EntityNotFoundError):
        await service.get_active_admin_by_id(uuid.uuid4())


def test_admin_password_service_argon2id():
    """Verify AdminPasswordService produces valid Argon2id hashes and performs timing defense."""
    pwd_service = AdminPasswordService()
    raw_pwd = "MySecretAdminPassword2026"
    hashed = pwd_service.hash_password(raw_pwd)

    assert hashed.startswith("$argon2id$")
    assert pwd_service.verify_password(raw_pwd, hashed) is True
    assert pwd_service.verify_password("wrong_password", hashed) is False

    # Execute timing defense shouldn't raise exceptions
    pwd_service.execute_timing_defense("dummy_password")


def test_jwt_service_domain_isolation():
    """Verify AdminJWTService and customer JWTService cannot verify each other's tokens."""
    admin_jwt_service = AdminJWTService()
    customer_jwt_service = JWTService()

    admin_id = uuid.uuid4()
    admin_token = admin_jwt_service.issue_admin_token(admin_id, "admin_user", True)

    # Verify admin token with admin service succeeds
    claims = admin_jwt_service.verify_admin_token(admin_token)
    assert claims.sub == str(admin_id)
    assert claims.role == "super_admin"

    # Verify customer JWTService rejects admin token (different keys, issuer, audience)
    with pytest.raises(Exception):
        customer_jwt_service.verify_access_token(admin_token)

    # Issue customer access token
    customer_token = customer_jwt_service.issue_access_token(uuid.uuid4(), "RT-0001-0001", "guid-123")

    # Verify admin JWTService rejects customer token
    with pytest.raises(InvalidAdminTokenError):
        admin_jwt_service.verify_admin_token(customer_token)
