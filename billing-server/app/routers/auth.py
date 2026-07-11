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
from fastapi.responses import JSONResponse

from app.dependencies import (
    get_auth_service,
    get_current_account,
    get_device_service,
    get_jwt_service,
    get_refresh_service,
    get_signal_service,
    get_totp_service,
)
from app.models.account import Account
from app.models.connection_signal import ConnectionEventType
from typing import Union

import hashlib
import secrets
import string
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.models import ExchangeToken
from app.models.base import SubscriptionStatus
from app.security import hash_master_token
from app.rate_limit import require_rate_limit, RateLimiter, get_rate_limiter, KeyType
from app.routers.auth_models import (
    AccountMeResponse,
    DeviceLimitErrorResponse,
    ExchangeRequest,
    ExchangeResponse,
    InactiveDeviceErrorResponse,
    LoginChallengeResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    RefreshResponse,
    RegisterAccountRequest,
    RegisterAccountResponse,
    SuccessResponse,
)
from app.security import JWTService
from app.services import (
    AuthenticationService,
    ConnectionSignalService,
    DeviceService,
    RefreshTokenService,
)
from app.services.exceptions import (
    DeviceLimitExceededError,
    DeviceOwnershipError,
    DeviceServiceError,
    InactiveDeviceError,
    RefreshTokenExpiredError,
    RefreshTokenNotFoundError,
    RefreshTokenReplayError,
    RefreshTokenRevokedError,
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
        source_ip = (
            getattr(http_request.state, "client_ip", "unknown") if http_request else None
        )
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
    "/register",
    summary="Create a new customer account and return one-time credentials",
    response_model=RegisterAccountResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Validation error"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Unexpected database error"},
    },
)
async def register_account(
    request: RegisterAccountRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterAccountResponse:
    """
    Create a new account with generated Account ID and secret Master Token.
    Returns credentials exactly once for user download/acknowledgement.
    """
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(5):
        block1 = "".join(secrets.choice(alphabet) for _ in range(4))
        block2 = "".join(secrets.choice(alphabet) for _ in range(4))
        candidate_id = f"ST-{block1}-{block2}"
        existing = await db.execute(select(Account).where(Account.account_id == candidate_id))
        if existing.scalar_one_or_none() is None:
            account_id = candidate_id
            break
    else:
        account_id = f"ST-{uuid.uuid4().hex[:8].upper()}"

    master_token = secrets.token_hex(32)
    master_token_hash = hash_master_token(master_token)
    if settings.environment.lower() != "production":
        logger.debug("DEV AUDIT [Register]: generated_hash=%s", master_token_hash)

    account = Account(
        account_id=account_id,
        master_token_hash=master_token_hash,
        plan_id=request.plan_id,
        status=SubscriptionStatus.ACTIVE,
    )
    db.add(account)
    await db.commit()
    logger.info("Account registration succeeded")

    return RegisterAccountResponse(
        account_id=account_id,
        master_token=master_token,
    )


@router.post(
    "/login",
    summary="Authenticate credentials and issue session tokens",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_rate_limit("login"))],
    responses={
        400: {"description": "Validation error"},
        401: {"description": "Authentication failed or account inactive"},
        403: {
            "model": Union[DeviceLimitErrorResponse, InactiveDeviceErrorResponse],
            "description": "Device limit reached for subscription plan, or this device has been deactivated",
        },
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
    device_service: DeviceService = Depends(get_device_service),
    signal_service: ConnectionSignalService = Depends(get_signal_service),
    limiter: RateLimiter = Depends(get_rate_limiter),
    db: AsyncSession = Depends(get_db),
    totp_service=Depends(get_totp_service),
) -> Union[LoginResponse, JSONResponse]:
    """
    Authenticate Account ID and Master Token credential pair.
    On success, issues a short-lived Ed25519 Access JWT and a long-lived rotated Refresh Token.

    Finding H-7: the presented device_guid is registered (or touched, if already registered
    to this account) via DeviceService.register_device before any tokens are issued. This
    makes the subscription plan's device-limit enforcement load-bearing at login, not only
    on the separate POST /api/devices endpoint.
    """
    await limiter.enforce(http_request, "login_account", KeyType.ACCOUNT, key_override=request.account_id)

    result = await auth_service.authenticate(request.account_id, request.master_token.get_secret_value())
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

    # ── Two-Factor Authentication check ─────────────────────────────────────
    # This check runs AFTER credential verification so we don't leak whether 2FA is
    # enabled on an account that doesn't even have valid credentials.
    account = result.account
    if account.totp_enabled:
        if not request.two_fa_code:
            # Credentials are valid but TOTP code has not been provided yet.
            # Signal the frontend to show the TOTP input field and await a second request.
            logger.info("Login challenge: Two-factor authentication required")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Two-factor authentication required",
                    "requires_2fa": True,
                },
            )

        # A TOTP code was provided — verify it.
        totp_verified = False
        code_str = request.two_fa_code.strip()

        # Try live TOTP first (6-digit numeric code).
        if account.totp_secret_encrypted:
            try:
                secret = totp_service.decrypt_secret(account.totp_secret_encrypted)
                if totp_service.verify_totp(secret, code_str):
                    totp_verified = True
            except Exception as exc:
                logger.error("Failed to decrypt TOTP secret during login for account (id redacted): %s", type(exc).__name__)

        # If live TOTP failed, try backup code (consumes it if valid).
        if not totp_verified and account.totp_backup_codes_json:
            backup_valid, updated_hashes_json = totp_service.verify_and_consume_backup_code(
                account.totp_backup_codes_json, code_str
            )
            if backup_valid:
                totp_verified = True
                # Consume the backup code — persist the updated (shorter) list.
                account.totp_backup_codes_json = updated_hashes_json
                db.add(account)
                await db.commit()
                logger.info("Login: backup code consumed")

        if not totp_verified:
            logger.info("Login failed: invalid two-factor authentication code")
            await safe_record_signal(
                signal_service,
                account_id=account.id,
                event_type=ConnectionEventType.LOGIN,
                success=False,
                device_guid=request.device_guid,
                http_request=http_request,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed: invalid two-factor authentication code",
            )

    try:
        await device_service.register_device(
            account_id=result.account.id,
            device_guid=request.device_guid,
            friendly_name=None,
        )
    except DeviceLimitExceededError:
        logger.info("Login failed: device limit reached")
        await safe_record_signal(
            signal_service,
            account_id=result.account.id,
            event_type=ConnectionEventType.LOGIN,
            success=False,
            device_guid=request.device_guid,
            http_request=http_request,
        )
        # Re-raised as-is: the globally registered DeviceLimitExceededError handler
        # (app/main.py) already produces the exact structured 403 body
        # ({"detail": ..., "plan": ..., "current_devices": ..., "max_devices": ...}) used by
        # POST /api/devices today. Reuse it rather than duplicating that response shape here.
        raise
    except DeviceOwnershipError:
        # SECURITY: never reveal that this device_guid is registered to a different
        # account — that would leak information about another account's device inventory.
        # Respond identically to an invalid-credentials failure.
        logger.info("Login failed")
        await safe_record_signal(
            signal_service,
            account_id=result.account.id,
            event_type=ConnectionEventType.LOGIN,
            success=False,
            device_guid=request.device_guid,
            http_request=http_request,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: invalid credentials or inactive account",
        )
    except InactiveDeviceError:
        logger.info("Login failed: device deactivated")
        await safe_record_signal(
            signal_service,
            account_id=result.account.id,
            event_type=ConnectionEventType.LOGIN,
            success=False,
            device_guid=request.device_guid,
            http_request=http_request,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This device has been deactivated. Reactivate it via "
                f"/api/devices/{request.device_guid}/reactivate or register a new device."
            ),
        )
    except DeviceServiceError:
        logger.error("Login failed due to device registration error")
        await safe_record_signal(
            signal_service,
            account_id=result.account.id,
            event_type=ConnectionEventType.LOGIN,
            success=False,
            device_guid=request.device_guid,
            http_request=http_request,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected service or database error",
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


@router.post(
    "/exchange",
    summary="Atomically redeem a single-use exchange token for session tokens",
    response_model=ExchangeResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Validation error"},
        410: {"description": "Exchange token expired or already redeemed"},
        500: {"description": "Unexpected database error"},
    },
)
async def exchange_token(
    request: ExchangeRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    jwt_service: JWTService = Depends(get_jwt_service),
    refresh_service: RefreshTokenService = Depends(get_refresh_service),
    device_service: DeviceService = Depends(get_device_service),
    signal_service: ConnectionSignalService = Depends(get_signal_service),
) -> ExchangeResponse:
    """
    Atomically redeem a single-use web exchange token for an authenticated session token pair.
    The exchange token is invalidated immediately upon redemption.
    NEVER returns the Master Token.
    """
    token_hash = hashlib.sha256(request.exchange_token.encode("utf-8")).hexdigest()

    result = await db.execute(
        select(ExchangeToken).where(ExchangeToken.token_hash == token_hash).with_for_update()
    )
    token_entry = result.scalar_one_or_none()

    if not token_entry or token_entry.is_redeemed or token_entry.expires_at <= datetime.now(timezone.utc):
        logger.warning("Attempted redemption of invalid, expired, or already redeemed exchange token")
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Exchange token is invalid, expired, or has already been redeemed",
        )

    # Atomically invalidate single-use exchange token
    token_entry.is_redeemed = True
    await db.commit()

    account_id = token_entry.account_id
    is_initial = token_entry.is_initial_provisioning

    # Register device and issue tokens
    try:
        await device_service.register_device(
            account_id=account_id,
            device_guid=request.device_guid,
            friendly_name=None,
            client_ip=getattr(http_request.state, "client_ip", "unknown"),
        )
    except Exception as exc:
        logger.error("Device registration during exchange failed: %s", exc)

    access_token = jwt_service.create_access_token(account_id=account_id, role="user")
    refresh_token = await refresh_service.issue_refresh_token(
        account_id=account_id,
        device_guid=request.device_guid,
    )

    await safe_record_signal(
        signal_service,
        account_id=account_id,
        event_type=ConnectionEventType.LOGIN,
        success=True,
        device_guid=request.device_guid,
        http_request=http_request,
    )

    return ExchangeResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_in=jwt_service.access_token_expire_minutes * 60,
        is_initial_provisioning=is_initial,
    )

