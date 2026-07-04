"""
credentials.py — Phase 2.4 VPN Credential Lifecycle & Client Configuration Delivery API Router.
Provides authenticated endpoints for retrieving and managing VPN client configurations and credentials.
Enforces zero-secret logging and consumes CredentialService exclusively.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_account, get_credential_service
from app.models import Account
from app.routers.credential_models import (
    CredentialResponse,
    VlessResponse,
    SingboxResponse,
    CredentialStatusResponse,
)
from app.services.credential_service import CredentialService
from app.services.exceptions import (
    CredentialNotFoundError,
    CredentialAlreadyRevokedError,
    CredentialAlreadyActiveError,
    CredentialRotationFailedError,
    CredentialServiceError,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/credentials",
    tags=["VPN Credentials"],
    responses={
        401: {"description": "Authentication required or token invalid"},
        404: {"description": "VPN profile not found"},
        500: {"description": "Internal server error"},
    },
)


@router.get(
    "",
    response_model=CredentialResponse,
    status_code=status.HTTP_200_OK,
    summary="Get active VPN profile and configuration",
    description="Returns canonical VPN connection parameters and generated sing-box configuration.",
)
async def get_credentials(
    account: Account = Depends(get_current_account),
    service: CredentialService = Depends(get_credential_service),
) -> CredentialResponse:
    """Retrieve complete active VPN profile and configuration blob."""
    try:
        logger.info("Retrieving VPN credentials for account_id=%s", account.id)
        data = await service.get_credentials(account.id)
        return CredentialResponse(**data)
    except CredentialNotFoundError as exc:
        logger.info("Credentials not found for account_id=%s", account.id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CredentialAlreadyRevokedError as exc:
        logger.info("Credentials already revoked for account_id=%s", account.id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CredentialServiceError as exc:
        logger.error("Error retrieving credentials for account_id=%s", account.id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/vless",
    response_model=VlessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get canonical VLESS URI",
    description="Returns the canonical VLESS reality link for client import.",
)
async def get_vless_uri(
    account: Account = Depends(get_current_account),
    service: CredentialService = Depends(get_credential_service),
) -> VlessResponse:
    """Retrieve VLESS URI string for the active VPN profile."""
    try:
        logger.info("Retrieving VLESS URI for account_id=%s", account.id)
        uri = await service.get_vless_uri(account.id)
        return VlessResponse(vless_uri=uri)
    except CredentialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CredentialAlreadyRevokedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CredentialServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/sing-box",
    response_model=SingboxResponse,
    status_code=status.HTTP_200_OK,
    summary="Get sing-box JSON configuration",
    description="Returns dynamic sing-box 1.8+ outbound JSON configuration.",
)
async def get_singbox_config(
    account: Account = Depends(get_current_account),
    service: CredentialService = Depends(get_credential_service),
) -> SingboxResponse:
    """Retrieve generated sing-box configuration dictionary."""
    try:
        logger.info("Retrieving sing-box config for account_id=%s", account.id)
        config = await service.get_singbox_config(account.id)
        return SingboxResponse(config=config)
    except CredentialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CredentialAlreadyRevokedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CredentialServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/regenerate",
    response_model=CredentialResponse,
    status_code=status.HTTP_200_OK,
    summary="Regenerate/rotate VPN credentials",
    description="Atomically rotates UUID and REALITY parameters in the remote provisioning provider.",
)
async def regenerate_credentials(
    account: Account = Depends(get_current_account),
    service: CredentialService = Depends(get_credential_service),
) -> CredentialResponse:
    """Rotate and regenerate VPN credentials for the authenticated account."""
    try:
        logger.info("Regenerating credentials for account_id=%s", account.id)
        data = await service.regenerate_credentials(account.id)
        return CredentialResponse(**data)
    except CredentialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CredentialRotationFailedError as exc:
        logger.error("Credential rotation failed for account_id=%s", account.id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except CredentialServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/revoke",
    response_model=CredentialStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke VPN credentials",
    description="Suspends VPN access for the active profile without deleting historical records.",
)
async def revoke_credentials(
    account: Account = Depends(get_current_account),
    service: CredentialService = Depends(get_credential_service),
) -> CredentialStatusResponse:
    """Revoke active credentials for the authenticated account."""
    try:
        logger.info("Revoking credentials for account_id=%s", account.id)
        await service.revoke_credentials(account.id)
        return CredentialStatusResponse(status="revoked")
    except CredentialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CredentialAlreadyRevokedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CredentialServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/restore",
    response_model=CredentialStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Restore revoked VPN credentials",
    description="Reactivates previously revoked or suspended VPN credentials.",
)
async def restore_credentials(
    account: Account = Depends(get_current_account),
    service: CredentialService = Depends(get_credential_service),
) -> CredentialStatusResponse:
    """Restore previously revoked credentials for the authenticated account."""
    try:
        logger.info("Restoring credentials for account_id=%s", account.id)
        await service.restore_credentials(account.id)
        return CredentialStatusResponse(status="restored")
    except CredentialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CredentialAlreadyActiveError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except CredentialServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
