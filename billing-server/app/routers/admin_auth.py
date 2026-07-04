"""
admin_auth.py — Administrative Authentication Router.

Provides endpoints for administrative authentication and profile verification.
Strictly decoupled from customer authentication routes and dependencies.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_admin_auth_service, get_current_admin
from app.models.admin_user import AdminUser
from app.rate_limit import require_rate_limit
from app.routers.admin_models import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminProfileResponse,
)
from app.services.admin_auth import AdminAuthenticationService

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
    admin_auth_service: AdminAuthenticationService = Depends(get_admin_auth_service),
) -> AdminLoginResponse:
    """
    Authenticate an administrative username and password pair.
    On success, issues a short-lived Ed25519 signed Admin Access JWT.
    """
    result = await admin_auth_service.authenticate(request.username, request.password)
    if not result.success or result.admin_user is None or result.access_token is None:
        logger.info("Admin login failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: invalid credentials or inactive account",
        )

    logger.info("Admin login succeeded")
    role = "super_admin" if result.admin_user.is_super_admin else "admin"
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
