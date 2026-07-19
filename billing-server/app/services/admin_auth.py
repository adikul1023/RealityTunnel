"""
admin_auth.py — Pure domain service for Administrative Authentication.

Strictly decoupled from HTTP request handlers, FastAPI routes, and customer authentication tables.
"""
from __future__ import annotations

import enum
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.exceptions import RepositoryError, EntityNotFoundError
from app.models.admin_user import AdminUser
from app.repositories.admin_user_repository import AdminUserRepository
from app.security.admin_password import AdminPasswordService
from app.security.admin_jwt import AdminJWTService
from app.services.exceptions import (
    AdminSecurityError,
    AdminNotActiveError,
    MFANotImplementedYet,
)

logger = logging.getLogger(__name__)


class AdminAuthReason(str, enum.Enum):
    """
    Structured outcomes for administrative authentication attempts.
    """
    SUCCESS = "SUCCESS"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    INVALID_PASSWORD = "INVALID_PASSWORD"
    USER_INACTIVE = "USER_INACTIVE"


@dataclass(frozen=True)
class AdminAuthResult:
    """
    Typed result returned by AdminAuthenticationService.authenticate().
    Encapsulates success status, reason, backing admin user, and issued access token.
    """
    success: bool
    reason: AdminAuthReason
    admin_user: AdminUser | None = None
    access_token: str | None = None


class AdminAuthenticationService:
    """
    Core administrative authentication domain service.
    Orchestrates repository lookups, Argon2id verification, MFA stub checking, and JWT issuance.
    """

    def __init__(
        self,
        admin_repo: AdminUserRepository,
        password_service: AdminPasswordService,
        jwt_service: AdminJWTService,
    ) -> None:
        self.admin_repo = admin_repo
        self.password_service = password_service
        self.jwt_service = jwt_service

    async def authenticate(self, username: str, password: str) -> AdminAuthResult:
        """
        Authenticate an administrative username and password pair.
        
        Sequence:
        1. Lookup AdminUser by username.
        2. If not found -> execute timing attack defense -> return USER_NOT_FOUND.
        3. Verify password via Argon2id -> if invalid -> return INVALID_PASSWORD.
        4. Check active status -> if inactive -> return USER_INACTIVE.
        5. Check MFA -> if mfa_enabled -> raise MFANotImplementedYet.
        6. Update last_login_at timestamp and issue Admin JWT.
        """
        try:
            admin = await self.admin_repo.get_by_username(username)
        except RepositoryError as exc:
            logger.error("Admin authentication failed due to repository error")
            raise AdminSecurityError("Database error during administrative lookup") from exc
        except Exception as exc:
            logger.error("Admin authentication failed due to unexpected error")
            raise AdminSecurityError("Unexpected database error during administrative lookup") from exc

        if admin is None:
            # Execute dummy verification to prevent timing-based username enumeration
            self.password_service.execute_timing_defense(password)
            logger.info("Admin authentication failed: invalid credentials")
            return AdminAuthResult(success=False, reason=AdminAuthReason.USER_NOT_FOUND)

        if not self.password_service.verify_password(password, admin.password_hash):
            logger.info("Admin authentication failed: invalid credentials")
            return AdminAuthResult(success=False, reason=AdminAuthReason.INVALID_PASSWORD)

        if not admin.is_active:
            logger.info("Admin authentication failed: deactivated account")
            return AdminAuthResult(success=False, reason=AdminAuthReason.USER_INACTIVE, admin_user=admin)

        if getattr(admin, "mfa_enabled", None) is not False:
            logger.info("Admin authentication blocked: MFA required or data malformed/omitted")
            raise MFANotImplementedYet("MFA for administrative accounts is not yet implemented.")

        # Update last login timestamp
        try:
            await self.admin_repo.update(admin, last_login_at=datetime.now(timezone.utc))
        except Exception as exc:
            import traceback
            traceback.print_exc()
            logger.error("Failed to update last_login_at for admin account: %s", exc, exc_info=True)
            # We log but do not abort successful authentication if timestamp update fails

        token = self.jwt_service.issue_admin_token(
            admin_id=admin.id,
            username=admin.username,
            is_super_admin=admin.is_super_admin,
        )

        logger.info("Admin authentication succeeded")
        return AdminAuthResult(
            success=True,
            reason=AdminAuthReason.SUCCESS,
            admin_user=admin,
            access_token=token,
        )

    async def get_active_admin_by_id(self, admin_id: uuid.UUID) -> AdminUser:
        """
        Retrieve an active administrative user by UUID or raise appropriate security/not found exceptions.
        Used primarily by dependency injection for protected admin routes.
        """
        try:
            admin = await self.admin_repo.get_by_id_or_raise(admin_id)
        except EntityNotFoundError:
            raise
        except Exception as exc:
            raise AdminSecurityError("Database error retrieving administrative account") from exc

        if not admin.is_active:
            raise AdminNotActiveError("Administrative account is deactivated")

        return admin
