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
import uuid
from fastapi import APIRouter, Depends, Request, status

from app.dependencies import get_current_account, get_device_service, get_signal_service
from app.models.account import Account
from app.models.connection_signal import ConnectionEventType
from app.rate_limit import require_rate_limit
from app.services import DeviceService, ConnectionSignalService
from app.services.exceptions import InactiveDeviceError
from app.routers.device_models import (
    DeviceListResponse,
    DeviceResponse,
    RegisterDeviceRequest,
    RenameDeviceRequest,
    SuccessResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/devices", tags=["Devices"])


async def safe_record_signal(
    signal_service: ConnectionSignalService,
    account_id: uuid.UUID | None,
    event_type: ConnectionEventType,
    success: bool,
    device_guid: str | None = None,
    http_request: Request | None = None,
) -> None:
    """Safely record a security signal without letting exceptions disrupt device management."""
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
    "",
    summary="Register a client device under the authenticated account",
    response_model=DeviceResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_rate_limit("device_register"))],
    responses={
        400: {"description": "Validation error"},
        401: {"description": "Authentication failed or token invalid"},
        403: {"description": "Device limit reached for subscription plan"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Unexpected service or database error"},
    },
)
async def register_device(
    request: RegisterDeviceRequest,
    http_request: Request,
    current_account: Account = Depends(get_current_account),
    device_service: DeviceService = Depends(get_device_service),
    signal_service: ConnectionSignalService = Depends(get_signal_service),
) -> DeviceResponse:
    """Register a client device or update its timestamps if already registered."""
    try:
        device = await device_service.register_device(
            current_account.id,
            request.device_guid,
            request.friendly_name,
        )
    except Exception:
        logger.info("Register device failed")
        await safe_record_signal(
            signal_service,
            account_id=current_account.id,
            event_type=ConnectionEventType.DEVICE_REGISTER,
            success=False,
            device_guid=request.device_guid,
            http_request=http_request,
        )
        raise

    logger.info("Register device succeeded")
    await safe_record_signal(
        signal_service,
        account_id=current_account.id,
        event_type=ConnectionEventType.DEVICE_REGISTER,
        success=True,
        device_guid=request.device_guid,
        http_request=http_request,
    )
    return DeviceResponse.model_validate(device)


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
    http_request: Request,
    current_account: Account = Depends(get_current_account),
    device_service: DeviceService = Depends(get_device_service),
    signal_service: ConnectionSignalService = Depends(get_signal_service),
) -> DeviceResponse:
    """Update friendly name of an active device. Rejects updates if device is inactive."""
    try:
        device = await device_service.rename_device(
            current_account.id, device_guid, request.friendly_name
        )
    except Exception:
        logger.info("Rename device failed")
        await safe_record_signal(
            signal_service,
            account_id=current_account.id,
            event_type=ConnectionEventType.DEVICE_RENAME,
            success=False,
            device_guid=device_guid,
            http_request=http_request,
        )
        raise

    logger.info("Rename device succeeded")
    await safe_record_signal(
        signal_service,
        account_id=current_account.id,
        event_type=ConnectionEventType.DEVICE_RENAME,
        success=True,
        device_guid=device_guid,
        http_request=http_request,
    )
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
    http_request: Request,
    current_account: Account = Depends(get_current_account),
    device_service: DeviceService = Depends(get_device_service),
    signal_service: ConnectionSignalService = Depends(get_signal_service),
) -> SuccessResponse:
    """Soft-delete a device by setting is_active to False. Operation is idempotent."""
    try:
        await device_service.deactivate_device(current_account.id, device_guid)
    except InactiveDeviceError:
        logger.info("Deactivate device succeeded (already inactive)")
        await safe_record_signal(
            signal_service,
            account_id=current_account.id,
            event_type=ConnectionEventType.DEVICE_DEACTIVATE,
            success=True,
            device_guid=device_guid,
            http_request=http_request,
        )
        return SuccessResponse(success=True, message="Device deactivated successfully")
    except Exception:
        logger.info("Deactivate device failed")
        await safe_record_signal(
            signal_service,
            account_id=current_account.id,
            event_type=ConnectionEventType.DEVICE_DEACTIVATE,
            success=False,
            device_guid=device_guid,
            http_request=http_request,
        )
        raise

    logger.info("Deactivate device succeeded")
    await safe_record_signal(
        signal_service,
        account_id=current_account.id,
        event_type=ConnectionEventType.DEVICE_DEACTIVATE,
        success=True,
        device_guid=device_guid,
        http_request=http_request,
    )
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
    http_request: Request,
    current_account: Account = Depends(get_current_account),
    device_service: DeviceService = Depends(get_device_service),
    signal_service: ConnectionSignalService = Depends(get_signal_service),
) -> DeviceResponse:
    """Reactivate a previously deactivated device."""
    try:
        device = await device_service.reactivate_device(current_account.id, device_guid)
    except InactiveDeviceError:
        logger.info("Reactivate device succeeded (already active)")
        device = await device_service.get_device(current_account.id, device_guid)
        await safe_record_signal(
            signal_service,
            account_id=current_account.id,
            event_type=ConnectionEventType.DEVICE_REACTIVATE,
            success=True,
            device_guid=device_guid,
            http_request=http_request,
        )
        return DeviceResponse.model_validate(device)
    except Exception:
        logger.info("Reactivate device failed")
        await safe_record_signal(
            signal_service,
            account_id=current_account.id,
            event_type=ConnectionEventType.DEVICE_REACTIVATE,
            success=False,
            device_guid=device_guid,
            http_request=http_request,
        )
        raise

    logger.info("Reactivate device succeeded")
    await safe_record_signal(
        signal_service,
        account_id=current_account.id,
        event_type=ConnectionEventType.DEVICE_REACTIVATE,
        success=True,
        device_guid=device_guid,
        http_request=http_request,
    )
    return DeviceResponse.model_validate(device)
