"""
devices.py — Device Management API Endpoints Router (Phase 1.4.2).

Thin orchestration layer connecting HTTP requests to domain DeviceService.
Strictly decoupled from business logic, validation logic, and direct database queries.

Endpoints:
  - GET    /api/devices
  - GET    /api/devices/{device_guid}
  - PATCH  /api/devices/{device_guid}
  - DELETE /api/devices/{device_guid}
  - POST   /api/devices/{device_guid}/reactivate

LOGGING INVARIANT:
Never logs Account IDs, database UUIDs, or Device GUIDs.
Logs only generic outcome descriptions: "List devices succeeded", "Get device succeeded",
"Rename device succeeded", "Deactivate device succeeded", "Reactivate device succeeded".
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_account, get_device_service
from app.models.account import Account
from app.services import DeviceService
from app.services.exceptions import InactiveDeviceError
from app.routers.device_models import (
    DeviceListResponse,
    DeviceResponse,
    RenameDeviceRequest,
    SuccessResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/devices", tags=["Devices"])


@router.get(
    "",
    summary="List all registered client devices for current account",
    response_model=DeviceListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Authentication failed or token invalid"},
        500: {"description": "Unexpected service or database error"},
    },
)
async def list_devices(
    current_account: Account = Depends(get_current_account),
    device_service: DeviceService = Depends(get_device_service),
) -> DeviceListResponse:
    """Return all client devices owned by the authenticated account."""
    devices = await device_service.get_devices_for_account(current_account.id)
    logger.info("List devices succeeded")
    return DeviceListResponse(
        devices=[DeviceResponse.model_validate(d) for d in devices]
    )


@router.get(
    "/{device_guid}",
    summary="Retrieve details for a specific registered device",
    response_model=DeviceResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Authentication failed or token invalid"},
        404: {"description": "Device not found or owned by another account"},
        500: {"description": "Unexpected service or database error"},
    },
)
async def get_device(
    device_guid: str,
    current_account: Account = Depends(get_current_account),
    device_service: DeviceService = Depends(get_device_service),
) -> DeviceResponse:
    """Retrieve exactly one device. Returns 404 if device is missing or belongs to another account."""
    device = await device_service.get_device(current_account.id, device_guid)
    logger.info("Get device succeeded")
    return DeviceResponse.model_validate(device)


@router.patch(
    "/{device_guid}",
    summary="Update friendly name for a specific registered device",
    response_model=DeviceResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Validation error or device inactive"},
        401: {"description": "Authentication failed or token invalid"},
        404: {"description": "Device not found or owned by another account"},
        500: {"description": "Unexpected service or database error"},
    },
)
async def rename_device(
    device_guid: str,
    request: RenameDeviceRequest,
    current_account: Account = Depends(get_current_account),
    device_service: DeviceService = Depends(get_device_service),
) -> DeviceResponse:
    """Update friendly name of an active device. Rejects updates if device is inactive."""
    device = await device_service.rename_device(
        current_account.id, device_guid, request.friendly_name
    )
    logger.info("Rename device succeeded")
    return DeviceResponse.model_validate(device)


@router.delete(
    "/{device_guid}",
    summary="Soft-deactivate a registered client device",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Authentication failed or token invalid"},
        404: {"description": "Device not found or owned by another account"},
        500: {"description": "Unexpected service or database error"},
    },
)
async def deactivate_device(
    device_guid: str,
    current_account: Account = Depends(get_current_account),
    device_service: DeviceService = Depends(get_device_service),
) -> SuccessResponse:
    """Soft-delete a device by setting is_active to False. Operation is idempotent."""
    try:
        await device_service.deactivate_device(current_account.id, device_guid)
    except InactiveDeviceError:
        logger.info("Deactivate device succeeded (already inactive)")
        return SuccessResponse(success=True, message="Device deactivated successfully")

    logger.info("Deactivate device succeeded")
    return SuccessResponse(success=True, message="Device deactivated successfully")


@router.post(
    "/{device_guid}/reactivate",
    summary="Reactivate a soft-deactivated client device",
    response_model=DeviceResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Validation error or device already active"},
        401: {"description": "Authentication failed or token invalid"},
        404: {"description": "Device not found or owned by another account"},
        500: {"description": "Unexpected service or database error"},
    },
)
async def reactivate_device(
    device_guid: str,
    current_account: Account = Depends(get_current_account),
    device_service: DeviceService = Depends(get_device_service),
) -> DeviceResponse:
    """Reactivate a previously deactivated device."""
    device = await device_service.reactivate_device(current_account.id, device_guid)
    logger.info("Reactivate device succeeded")
    return DeviceResponse.model_validate(device)
