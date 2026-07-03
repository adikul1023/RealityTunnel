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
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories import AccountRepository, RefreshTokenRepository
from app.security import JWTService
from app.services import AuthenticationService, RefreshTokenService
from app.services.exceptions import (
    RefreshTokenExpiredError,
    RefreshTokenNotFoundError,
    RefreshTokenReplayError,
    RefreshTokenRevokedError,
)
from app.routers.auth_models import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    RefreshResponse,
    SuccessResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Singleton JWT service instance (stateless Ed25519 signer/verifier)
_jwt_service: JWTService | None = None


def get_jwt_service() -> JWTService:
    """Dependency provider yielding the stateless JWTService."""
    global _jwt_service
    if _jwt_service is None:
        _jwt_service = JWTService()
    return _jwt_service


async def get_account_repo(session: AsyncSession = Depends(get_db)) -> AccountRepository:
    """Dependency provider yielding AccountRepository tied to the request session."""
    return AccountRepository(session)


async def get_refresh_repo(session: AsyncSession = Depends(get_db)) -> RefreshTokenRepository:
    """Dependency provider yielding RefreshTokenRepository tied to the request session."""
    return RefreshTokenRepository(session)


async def get_auth_service(
    account_repo: AccountRepository = Depends(get_account_repo),
) -> AuthenticationService:
    """Dependency provider yielding AuthenticationService."""
    return AuthenticationService(account_repo)


async def get_rtr_service(
    refresh_repo: RefreshTokenRepository = Depends(get_refresh_repo),
) -> RefreshTokenService:
    """Dependency provider yielding RefreshTokenService."""
    return RefreshTokenService(refresh_repo)


@router.post(
    "/login",
    summary="Authenticate credentials and issue session tokens",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Validation error"},
        401: {"description": "Authentication failed or account inactive"},
        500: {"description": "Unexpected service or database error"},
    },
)
async def login(
    request: LoginRequest,
    auth_service: AuthenticationService = Depends(get_auth_service),
    jwt_service: JWTService = Depends(get_jwt_service),
    rtr_service: RefreshTokenService = Depends(get_rtr_service),
) -> LoginResponse:
    """
    Authenticate Account ID and Master Token credential pair.
    On success, issues a short-lived Ed25519 Access JWT and a long-lived rotated Refresh Token.
    """
    result = await auth_service.authenticate(request.account_id, request.master_token)
    if not result.success or result.account is None:
        logger.info("Login failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: invalid credentials or inactive account",
        )

    access_token = jwt_service.issue_access_token(
        account_uuid=result.account.id,
        account_id=result.account.account_id,
        device_guid=request.device_guid,
    )
    refresh_result = await rtr_service.issue_refresh_token(
        account_id=result.account.id,
        device_guid=request.device_guid,
    )

    logger.info("Login succeeded")
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_result.token,
    )


@router.post(
    "/refresh",
    summary="Rotate refresh token and issue new access token",
    response_model=RefreshResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Validation error"},
        401: {"description": "Invalid, expired, or replayed refresh token"},
        500: {"description": "Unexpected service or database error"},
    },
)
async def refresh(
    request: RefreshRequest,
    rtr_service: RefreshTokenService = Depends(get_rtr_service),
    jwt_service: JWTService = Depends(get_jwt_service),
    account_repo: AccountRepository = Depends(get_account_repo),
) -> RefreshResponse:
    """
    Perform Refresh Token Rotation (RTR).
    Validates old refresh token, revokes it, issues a new refresh token bound to the same device,
    and returns a fresh short-lived Access JWT.
    """
    try:
        rotated = await rtr_service.rotate_refresh_token(request.refresh_token)
    except Exception:
        logger.info("Refresh failed")
        raise

    account = await account_repo.get_by_id_or_raise(rotated.account_id)
    access_token = jwt_service.issue_access_token(
        account_uuid=account.id,
        account_id=account.account_id,
        device_guid=rotated.device_guid,
    )

    logger.info("Refresh succeeded")
    return RefreshResponse(
        access_token=access_token,
        refresh_token=rotated.new_token,
    )


@router.post(
    "/logout",
    summary="Revoke a single refresh token session",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
)
async def logout(
    request: LogoutRequest,
    rtr_service: RefreshTokenService = Depends(get_rtr_service),
) -> SuccessResponse:
    """
    Revoke only the presented refresh token session.
    Idempotent: returns success even if token was already revoked or unknown.
    """
    await rtr_service.revoke_refresh_token(request.refresh_token)
    logger.info("Logout")
    return SuccessResponse(success=True)


@router.post(
    "/logout-all",
    summary="Revoke all refresh token sessions for an account",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
)
async def logout_all(
    request: LogoutRequest,
    rtr_service: RefreshTokenService = Depends(get_rtr_service),
) -> SuccessResponse:
    """
    Determine account identity from presented refresh token and revoke every active session
    across all registered devices for that account.
    Idempotent: returns success even if token was already revoked or unknown.
    """
    try:
        info = await rtr_service.verify_refresh_token(request.refresh_token)
        await rtr_service.revoke_all_for_account(info.account_id)
    except (
        RefreshTokenNotFoundError,
        RefreshTokenExpiredError,
        RefreshTokenRevokedError,
        RefreshTokenReplayError,
    ):
        pass

    logger.info("Logout all")
    return SuccessResponse(success=True)
