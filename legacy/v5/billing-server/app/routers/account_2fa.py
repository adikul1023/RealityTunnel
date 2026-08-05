"""
account_2fa.py — Two-Factor Authentication API Endpoints Router.

Provides real TOTP enrollment and management endpoints:
  - GET  /api/account/2fa/status
  - POST /api/account/2fa/setup
  - POST /api/account/2fa/enable
  - POST /api/account/2fa/disable
  - POST /api/account/2fa/regenerate-backups
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_account, get_totp_service
from app.models.account import Account
from app.rate_limit import require_rate_limit
from app.services.totp_dtos import (
    TotpRegenerateResponse,
    TotpSetupResponse,
    TotpStatusResponse,
    TotpVerificationRequest,
)
from app.services.totp_service import TOTPService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/account/2fa", tags=["Two-Factor Authentication"])


@router.get(
    "/status",
    summary="Get 2FA status for current account",
    response_model=TotpStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_2fa_status(
    account: Account = Depends(get_current_account),
) -> TotpStatusResponse:
    """Return whether Two-Factor Authentication is active for the current account."""
    return TotpStatusResponse(enabled=bool(account.totp_enabled))


@router.post(
    "/setup",
    summary="Generate TOTP setup secret, QR code image, and backup codes",
    response_model=TotpSetupResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_rate_limit("2fa_setup"))],
)
async def setup_2fa(
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
    totp_service: TOTPService = Depends(get_totp_service),
) -> TotpSetupResponse:
    """
    Generate a new TOTP secret and backup codes for enrollment.
    Idempotent: calling setup overwrites any pending unconfirmed setup.
    """
    secret, qr_data_uri, _, backup_codes = totp_service.generate_setup(account.account_id)
    encrypted_secret = totp_service.encrypt_secret(secret)
    hashed_backup_codes = totp_service.hash_backup_codes(backup_codes)

    account.totp_secret_encrypted = encrypted_secret
    account.totp_backup_codes_json = hashed_backup_codes
    db.add(account)
    await db.commit()

    return TotpSetupResponse(
        qr_data_uri=qr_data_uri,
        secret=secret,
        backup_codes=backup_codes,
    )


@router.post(
    "/enable",
    summary="Verify TOTP code and enable Two-Factor Authentication",
    response_model=TotpStatusResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_rate_limit("2fa_enable"))],
)
async def enable_2fa(
    request: TotpVerificationRequest,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
    totp_service: TOTPService = Depends(get_totp_service),
) -> TotpStatusResponse:
    """Verify 6-digit TOTP code against pending secret to activate 2FA."""
    if not account.totp_secret_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending 2FA setup found. Call /setup first.",
        )

    try:
        secret = totp_service.decrypt_secret(account.totp_secret_encrypted)
    except Exception as exc:
        logger.error("Failed to decrypt TOTP secret for account %s: %s", account.id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt setup secret.",
        )

    if not totp_service.verify_totp(secret, request.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code. Please ensure your authenticator app clock is synced.",
        )

    account.totp_enabled = True
    db.add(account)
    await db.commit()
    logger.info("Account %s successfully enabled 2FA", account.id)

    return TotpStatusResponse(enabled=True)


@router.post(
    "/disable",
    summary="Disable Two-Factor Authentication with TOTP code or backup code",
    response_model=TotpStatusResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_rate_limit("2fa_disable"))],
)
async def disable_2fa(
    request: TotpVerificationRequest,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
    totp_service: TOTPService = Depends(get_totp_service),
) -> TotpStatusResponse:
    """Disable 2FA after verifying either a live TOTP code or a valid backup code."""
    if not account.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is not currently enabled.",
        )

    verified = False
    if account.totp_secret_encrypted:
        try:
            secret = totp_service.decrypt_secret(account.totp_secret_encrypted)
            if totp_service.verify_totp(secret, request.code):
                verified = True
        except Exception:
            pass

    if not verified:
        backup_valid, _ = totp_service.verify_and_consume_backup_code(
            account.totp_backup_codes_json, request.code
        )
        if backup_valid:
            verified = True

    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Two-Factor code or backup code.",
        )

    account.totp_enabled = False
    account.totp_secret_encrypted = None
    account.totp_backup_codes_json = None
    db.add(account)
    await db.commit()
    logger.info("Account %s successfully disabled 2FA", account.id)

    return TotpStatusResponse(enabled=False)


@router.post(
    "/regenerate-backups",
    summary="Regenerate one-time backup codes",
    response_model=TotpRegenerateResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_rate_limit("2fa_regen"))],
)
async def regenerate_backup_codes(
    request: TotpVerificationRequest,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
    totp_service: TOTPService = Depends(get_totp_service),
) -> TotpRegenerateResponse:
    """Generate 10 new backup codes after verifying a live TOTP code."""
    if not account.totp_enabled or not account.totp_secret_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication must be enabled to regenerate backup codes.",
        )

    try:
        secret = totp_service.decrypt_secret(account.totp_secret_encrypted)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt setup secret.",
        )

    if not totp_service.verify_totp(secret, request.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code.",
        )

    _, _, _, new_codes = totp_service.generate_setup(account.account_id)
    account.totp_backup_codes_json = totp_service.hash_backup_codes(new_codes)
    db.add(account)
    await db.commit()

    return TotpRegenerateResponse(backup_codes=new_codes)
