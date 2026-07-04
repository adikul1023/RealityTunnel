"""
auth.py — Authentication & Refresh API Endpoints Router (Phase 1.3.5)

Thin orchestration layer connecting HTTP requests to domain authentication and token rotation services.
Strictly decoupled from business logic, credential hashing, and direct database queries.

Endpoints:
  - POST /api/auth/login
  - POST /api/auth/refresh
  - POST /api/auth/logout
  - POST /api/auth/logout-all

LOGGING INVARIANT:
Never logs Account IDs, Master Tokens, Refresh Tokens, JWTs, Hashes, or Device GUIDs.
Logs only generic outcome descriptions: "Login succeeded", "Login failed", "Refresh succeeded", "Refresh failed", "Logout", "Logout all".
"""
from __future__ import annotations

import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.dependencies import (
    get_auth_service,
    get_current_account,
    get_jwt_service,
    get_refresh_service,
    get_signal_service,
)
from app.models.account import Account
from app.models.connection_signal import ConnectionEventType
from app.rate_limit import require_rate_limit
from app.security import JWTService
from app.services import AuthenticationService, RefreshTokenService, ConnectionSignalService
from app.services.exceptions import (
    RefreshTokenExpiredError,
    RefreshTokenNotFoundError,
    RefreshTokenReplayError,
    RefreshTokenRevokedError,
)
from app.routers.auth_models import (
    AccountMeResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    RefreshResponse,
    SuccessResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Authentication"])


async def safe_record_signal(
    signal_service: ConnectionSignalService,
    account_id: uuid.UUID | None,
    event_type: ConnectionEventType,
    success: bool,
    device_guid: str | None = None,
    http_request: Request | None = None,
) -> None:
    """Safely record a security signal without letting exceptions disrupt authentication."""
    try:
        source_ip = http_request.client.host if http_request and http_request.client else None
        user_agent = http_request.headers.get("user-agent") if http_request else None
        await signal_service.record_signal(
            account_id=account_id,
            event_type=event_type,
            success=success,
            device_guid=device_guid,
            source_ip=source_ip,
            user_agent=user_agent,
        )
    except Exception as exc:
        logger.error("Failed to record connection signal: %s", exc)


@router.post(
    "/login",
    summary="Authenticate credentials and issue session tokens",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_rate_limit("login"))],
    responses={
        400: {"description": "Validation error"},
        401: {"description": "Authentication failed or account inactive"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Unexpected service or database error"},
    },
)
async def login(
    request: LoginRequest,
    http_request: Request,
    auth_service: AuthenticationService = Depends(get_auth_service),
    jwt_service: JWTService = Depends(get_jwt_service),
    refresh_service: RefreshTokenService = Depends(get_refresh_service),
    signal_service: ConnectionSignalService = Depends(get_signal_service),
) -> LoginResponse:
    """
    Authenticate Account ID and Master Token credential pair.
    On success, issues a short-lived Ed25519 Access JWT and a long-lived rotated Refresh Token.
    """
    result = await auth_service.authenticate(request.account_id, request.master_token)
    if not result.success or result.account is None:
        logger.info("Login failed")
        await safe_record_signal(
            signal_service,
            account_id=result.account.id if result.account else None,
            event_type=ConnectionEventType.LOGIN,
            success=False,
            device_guid=request.device_guid,
            http_request=http_request,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: invalid credentials or inactive account",
        )

    access_token = jwt_service.issue_access_token(
        account_uuid=result.account.id,
        account_id=result.account.account_id,
        device_guid=request.device_guid,
    )
    refresh_result = await refresh_service.issue_refresh_token(
        account_id=result.account.id,
        device_guid=request.device_guid,
    )

    logger.info("Login succeeded")
    await safe_record_signal(
        signal_service,
        account_id=result.account.id,
        event_type=ConnectionEventType.LOGIN,
        success=True,
        device_guid=request.device_guid,
        http_request=http_request,
    )
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_result.token,
    )


@router.post(
    "/refresh",
    summary="Rotate refresh token and issue new access token",
    response_model=RefreshResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_rate_limit("refresh"))],
    responses={
        400: {"description": "Validation error"},
        401: {"description": "Invalid, expired, or replayed refresh token"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Unexpected service or database error"},
    },
)
async def refresh(
    request: RefreshRequest,
    http_request: Request,
    refresh_service: RefreshTokenService = Depends(get_refresh_service),
    jwt_service: JWTService = Depends(get_jwt_service),
    auth_service: AuthenticationService = Depends(get_auth_service),
    signal_service: ConnectionSignalService = Depends(get_signal_service),
) -> RefreshResponse:
    """
    Perform Refresh Token Rotation (RTR).
    Validates old refresh token, revokes it, issues a new refresh token bound to the same device,
    and returns a fresh short-lived Access JWT.
    """
    try:
        rotated = await refresh_service.rotate_refresh_token(request.refresh_token)
    except Exception as exc:
        logger.info("Refresh failed")
        await safe_record_signal(
            signal_service,
            account_id=getattr(exc, "account_id", None),
            event_type=ConnectionEventType.REFRESH,
            success=False,
            device_guid=getattr(exc, "device_guid", None),
            http_request=http_request,
        )
        raise

    account = await auth_service.get_active_account_by_uuid(rotated.account_id)
    access_token = jwt_service.issue_access_token(
        account_uuid=account.id,
        account_id=account.account_id,
        device_guid=rotated.device_guid,
    )

    logger.info("Refresh succeeded")
    await safe_record_signal(
        signal_service,
        account_id=rotated.account_id,
        event_type=ConnectionEventType.REFRESH,
        success=True,
        device_guid=rotated.device_guid,
        http_request=http_request,
    )
    return RefreshResponse(
        access_token=access_token,
        refresh_token=rotated.new_token,
    )


@router.post(
    "/logout",
    summary="Revoke a single refresh token session",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_rate_limit("refresh"))],
)
async def logout(
    request: LogoutRequest,
    http_request: Request,
    refresh_service: RefreshTokenService = Depends(get_refresh_service),
    signal_service: ConnectionSignalService = Depends(get_signal_service),
) -> SuccessResponse:
    """
    Revoke only the presented refresh token session.
    Idempotent: returns success even if token was already revoked or unknown.
    """
    account_id = None
    device_guid = None
    try:
        info = await refresh_service.verify_refresh_token(request.refresh_token)
        account_id = info.account_id
        device_guid = info.device_guid
    except Exception:
        pass

    await refresh_service.revoke_refresh_token(request.refresh_token)
    logger.info("Logout")
    await safe_record_signal(
        signal_service,
        account_id=account_id,
        event_type=ConnectionEventType.LOGOUT,
        success=True,
        device_guid=device_guid,
        http_request=http_request,
    )
    return SuccessResponse(success=True)


@router.post(
    "/logout-all",
    summary="Revoke all refresh token sessions for an account",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_rate_limit("refresh"))],
)
async def logout_all(
    request: LogoutRequest,
    http_request: Request,
    refresh_service: RefreshTokenService = Depends(get_refresh_service),
    signal_service: ConnectionSignalService = Depends(get_signal_service),
) -> SuccessResponse:
    """
    Determine account identity from presented refresh token and revoke every active session
    across all registered devices for that account.
    Idempotent: returns success even if token was already revoked or unknown.
    """
    account_id = None
    device_guid = None
    try:
        info = await refresh_service.verify_refresh_token(request.refresh_token)
        account_id = info.account_id
        device_guid = info.device_guid
        await refresh_service.revoke_all_for_account(info.account_id)
    except (
        RefreshTokenNotFoundError,
        RefreshTokenExpiredError,
        RefreshTokenRevokedError,
        RefreshTokenReplayError,
    ):
        pass

    logger.info("Logout all")
    await safe_record_signal(
        signal_service,
        account_id=account_id,
        event_type=ConnectionEventType.LOGOUT_ALL,
        success=True,
        device_guid=device_guid,
        http_request=http_request,
    )
    return SuccessResponse(success=True)


@router.get(
    "/me",
    summary="Retrieve non-sensitive profile information for the authenticated account",
    response_model=AccountMeResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Missing, invalid, expired, or unauthorized bearer token"},
        500: {"description": "Unexpected service or database error"},
    },
)
async def get_me(
    current_account: Account = Depends(get_current_account),
) -> AccountMeResponse:
    """
    Retrieve current authenticated account details.
    Requires a valid Ed25519 Access JWT in the Authorization Bearer header.
    Rejects access if the backing account is deleted, suspended, pending, or expired.
    """
    return AccountMeResponse(
        account_id=current_account.account_id,
        status=current_account.status,
        subscription_expires_at=current_account.subscription_expires_at,
    )

