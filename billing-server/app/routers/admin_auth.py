"""
admin_auth.py — Administrative Authentication Router.

Provides endpoints for administrative authentication and profile verification.
Strictly decoupled from customer authentication routes and dependencies.
"""
from __future__ import annotations

import hashlib
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.dependencies import get_admin_auth_service, get_current_admin
from app.models.admin_user import AdminUser
from app.rate_limit import require_rate_limit, RateLimiter, get_rate_limiter, KeyType
from app.routers.admin_models import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminProfileResponse,
)
from app.services.admin_auth import AdminAuthenticationService
from app.security_hardening.audit import audit_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Admin Authentication"])


@router.post(
    "/login",
    summary="Authenticate administrative user and issue Admin JWT",
    response_model=AdminLoginResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_rate_limit("admin_login"))],
    responses={
        400: {"description": "Validation error"},
        401: {"description": "Authentication failed or account inactive"},
        429: {"description": "Rate limit exceeded"},
        501: {"description": "MFA required but not implemented"},
        500: {"description": "Unexpected service or database error"},
    },
)
async def login(
    request: AdminLoginRequest,
    http_request: Request,
    admin_auth_service: AdminAuthenticationService = Depends(get_admin_auth_service),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> AdminLoginResponse:
    """
    Authenticate an administrative username and password pair.
    On success, issues a short-lived Ed25519 signed Admin Access JWT.
    """
    await limiter.enforce(http_request, "admin_login_account", KeyType.ACCOUNT, key_override=request.username)

    # Hash client IP for audit logging (never store raw IPs)
    client_ip = getattr(http_request.state, "client_ip", "unknown")
    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:16]
    
    result = await admin_auth_service.authenticate(request.username, request.password.get_secret_value())
    if not result.success or result.admin_user is None or result.access_token is None:
        logger.info("Admin login failed")
        # Audit log: failed login attempt
        await audit_service.record_event(
            event_type="admin_login",
            actor_id=request.username,
            target_id="system",
            details={"action": "login_attempt", "status": "failed", "reason": "invalid_credentials"},
            ip_hash=ip_hash,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: invalid credentials or inactive account",
        )

    logger.info("Admin login succeeded")
    role = "super_admin" if result.admin_user.is_super_admin else "admin"
    
    # Audit log: successful login
    await audit_service.record_event(
        event_type="admin_login",
        actor_id=str(result.admin_user.id),
        target_id="system",
        details={"action": "login_success", "username": result.admin_user.username, "role": role},
        ip_hash=ip_hash,
    )
    
    return AdminLoginResponse(
        access_token=result.access_token,
        username=result.admin_user.username,
        role=role,
    )


@router.get(
    "/me",
    summary="Retrieve current administrative profile",
    response_model=AdminProfileResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Authentication failed or token invalid"},
    },
)
async def me(
    current_admin: AdminUser = Depends(get_current_admin),
) -> AdminProfileResponse:
    """
    Retrieve the profile of the currently authenticated administrative user.
    Requires a valid Admin Ed25519 Bearer token. Rejects customer tokens.
    """
    return AdminProfileResponse(
        id=str(current_admin.id),
        username=current_admin.username,
        is_active=current_admin.is_active,
        is_super_admin=current_admin.is_super_admin,
        mfa_enabled=current_admin.mfa_enabled,
    )
