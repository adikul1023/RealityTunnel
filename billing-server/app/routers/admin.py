"""
admin.py — Administrative Account Management Router.

Provides HTTP endpoints for operator-level account inspection and management.
This module is a THIN orchestration layer only.

ARCHITECTURAL INVARIANTS:
1. No repository access. All data operations go through AdminAccountService,
   DeviceService, or ConnectionSignalService.
2. No business logic. The router validates input, calls the service, maps to DTO, returns.
3. Every endpoint requires Depends(get_current_admin) (read) or Depends(require_super_admin) (write).
4. All routes are under /api/admin and use AdminBearer scheme in OpenAPI.
5. Never logs account IDs, tokens, hashes, or usernames.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import (
    get_admin_account_service,
    get_current_admin,
    get_device_service,
    get_operations_service,
    get_signal_service,
    require_super_admin,
)
from app.models.admin_user import AdminUser
from app.models.account import Account
from app.rate_limit import require_rate_limit
from app.routers.admin_dtos import (
    AdminAccountListResponse,
    AdminAccountResponse,
    AdminDeviceListResponse,
    AdminDeviceResponse,
    AdminLogoutAllResponse,
    AdminSignalListResponse,
    AdminSignalResponse,
    ExtendSubscriptionRequest,
)
from app.services.admin_account import AdminAccountService
from app.services.connection_signal import ConnectionSignalService
from app.services.device import DeviceService
from app.services.exceptions import (
    AdminAccountNotFoundError,
    AdminServiceError,
    DeviceNotFoundError,
    DeviceOwnershipError,
    InactiveDeviceError,
    DeviceServiceError,
)
from app.services.operations_dtos import DeviceRemovalResponseDTO, UnifiedAccountDetailsDTO
from app.services.operations_service import OperationsService
from app.security_hardening.audit import audit_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin Accounts"],
    dependencies=[Depends(require_rate_limit("admin_endpoints"))],
)

# ── DTO builders ─────────────────────────────────────────────────────────────

def _build_account_dto(account: Account) -> AdminAccountResponse:
    """Map an Account model to AdminAccountResponse. Never includes credential fields."""
    return AdminAccountResponse(
        id=str(account.id),
        account_id=account.account_id,
        status=account.status.value,
        plan_id=account.plan_id,
        subscription_expires_at=account.subscription_expires_at,
        created_at=account.created_at,
    )


# ── Account endpoints ─────────────────────────────────────────────────────────


@router.get(
    "/accounts",
    summary="List all accounts (paginated)",
    response_model=AdminAccountListResponse,
    status_code=status.HTTP_200_OK,
    responses={401: {"description": "Admin authentication required"}},
)
async def list_accounts(
    limit: int = Query(default=50, ge=1, le=200, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
    current_admin: AdminUser = Depends(get_current_admin),
    admin_account_service: AdminAccountService = Depends(get_admin_account_service),
) -> AdminAccountListResponse:
    """
    Return a paginated list of all customer accounts, newest first.
    Available to all authenticated administrators.
    """
    logger.info("Administrative account lookup.")
    accounts = await admin_account_service.list_accounts(limit=limit, offset=offset)
    return AdminAccountListResponse(
        accounts=[_build_account_dto(a) for a in accounts],
        total=len(accounts),
    )


@router.get(
    "/accounts/{account_id}",
    summary="Get account detail",
    response_model=AdminAccountResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Admin authentication required"},
        404: {"description": "Account not found"},
    },
)
async def get_account(
    account_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    admin_account_service: AdminAccountService = Depends(get_admin_account_service),
) -> AdminAccountResponse:
    """
    Retrieve details of a specific customer account by its human-readable account_id.
    Available to all authenticated administrators.
    """
    logger.info("Administrative account lookup.")
    try:
        account = await admin_account_service.get_account(account_id)
    except AdminAccountNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    except AdminServiceError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Service error")
    return _build_account_dto(account)


@router.get(
    "/account/{account_id}",
    summary="Get unified account details (account, sub, devices, prov, marzban, vpn, usage)",
    response_model=UnifiedAccountDetailsDTO,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Admin authentication required"},
        404: {"description": "Account not found"},
    },
)
async def get_unified_account(
    account_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    operations_service: OperationsService = Depends(get_operations_service),
) -> UnifiedAccountDetailsDTO:
    """
    Retrieve unified account details across all 7 subsystems in a single request.
    """
    logger.info("Admin %s requesting unified details for account %s", current_admin.id, account_id)
    try:
        return await operations_service.get_unified_account_details(account_id)
    except AdminAccountNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    except AdminServiceError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.patch(
    "/accounts/{account_id}/suspend",
    summary="Suspend a customer account (super-admin only)",
    response_model=AdminAccountResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Admin authentication required"},
        403: {"description": "Super-admin privilege required"},
        404: {"description": "Account not found"},
    },
)
async def suspend_account(
    account_id: str,
    current_admin: AdminUser = Depends(require_super_admin),
    admin_account_service: AdminAccountService = Depends(get_admin_account_service),
) -> AdminAccountResponse:
    """
    Suspend a customer account. Requires super-admin privileges.
    Idempotent — suspending an already-suspended account has no side effects.
    """
    try:
        account = await admin_account_service.suspend_account(account_id)
        # Audit log: account suspension
        await audit_service.record_event(
            event_type="admin_action",
            actor_id=str(current_admin.id),
            target_id=account_id,
            details={"action": "suspend_account", "account_id": account_id, "new_status": account.status.value},
        )
    except AdminAccountNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    except AdminServiceError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Service error")
    return _build_account_dto(account)


@router.patch(
    "/accounts/{account_id}/activate",
    summary="Activate a customer account (super-admin only)",
    response_model=AdminAccountResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Admin authentication required"},
        403: {"description": "Super-admin privilege required"},
        404: {"description": "Account not found"},
    },
)
async def activate_account(
    account_id: str,
    current_admin: AdminUser = Depends(require_super_admin),
    admin_account_service: AdminAccountService = Depends(get_admin_account_service),
) -> AdminAccountResponse:
    """
    Activate a customer account. Requires super-admin privileges.
    Idempotent — activating an already-active account has no side effects.
    """
    try:
        account = await admin_account_service.activate_account(account_id)
        # Audit log: account activation
        await audit_service.record_event(
            event_type="admin_action",
            actor_id=str(current_admin.id),
            target_id=account_id,
            details={"action": "activate_account", "account_id": account_id, "new_status": account.status.value},
        )
    except AdminAccountNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    except AdminServiceError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Service error")
    return _build_account_dto(account)


@router.patch(
    "/accounts/{account_id}/extend-subscription",
    summary="Extend account subscription (super-admin only)",
    response_model=AdminAccountResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Invalid extension duration"},
        401: {"description": "Admin authentication required"},
        403: {"description": "Super-admin privilege required"},
        404: {"description": "Account not found"},
    },
)
async def extend_subscription(
    account_id: str,
    body: ExtendSubscriptionRequest,
    current_admin: AdminUser = Depends(require_super_admin),
    admin_account_service: AdminAccountService = Depends(get_admin_account_service),
) -> AdminAccountResponse:
    """
    Extend the subscription of a customer account by the specified number of days.
    Requires super-admin privileges.
    If the account is EXPIRED, it is automatically set to ACTIVE.
    """
    try:
        account = await admin_account_service.extend_subscription(account_id, body.days)
        # Audit log: subscription extension
        await audit_service.record_event(
            event_type="subscription_change",
            actor_id=str(current_admin.id),
            target_id=account_id,
            details={"action": "extend_subscription", "account_id": account_id, "days": body.days, "new_status": account.status.value},
        )
    except AdminAccountNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    except AdminServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _build_account_dto(account)


# ── Device endpoint ───────────────────────────────────────────────────────────


@router.get(
    "/accounts/{account_id}/devices",
    summary="List devices for an account",
    response_model=AdminDeviceListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Admin authentication required"},
        404: {"description": "Account not found"},
    },
)
async def list_devices(
    account_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    admin_account_service: AdminAccountService = Depends(get_admin_account_service),
    device_service: DeviceService = Depends(get_device_service),
) -> AdminDeviceListResponse:
    """
    List all registered devices for a customer account.
    Available to all authenticated administrators. Read-only.
    """
    logger.info("Administrative account lookup.")
    try:
        account = await admin_account_service.get_account(account_id)
    except AdminAccountNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    except AdminServiceError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Service error")

    devices = await device_service.get_devices_for_account(account.id)
    return AdminDeviceListResponse(
        devices=[
            AdminDeviceResponse(
                device_guid=d.device_guid,
                friendly_name=d.friendly_name,
                is_active=d.is_active,
                first_seen_at=d.first_seen_at,
                last_seen_at=d.last_seen_at,
            )
            for d in devices
        ]
    )


@router.delete(
    "/accounts/{account_id}/devices/{device_guid}",
    summary="Delete a registered device from an account (super-admin only)",
    response_model=DeviceRemovalResponseDTO,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Cannot delete active device without deactivation or invalid state"},
        401: {"description": "Admin authentication required"},
        403: {"description": "Super-admin privilege required"},
        404: {"description": "Account or device not found"},
    },
)
async def delete_account_device(
    account_id: str,
    device_guid: str,
    current_admin: AdminUser = Depends(require_super_admin),
    admin_account_service: AdminAccountService = Depends(get_admin_account_service),
    device_service: DeviceService = Depends(get_device_service),
) -> DeviceRemovalResponseDTO:
    """
    Delete a device registration and revoke all associated refresh tokens.
    Returns whether removal succeeded and the number of active devices remaining on the account.
    """
    logger.info("Admin %s removing device %s from account %s", current_admin.id, device_guid, account_id)
    try:
        account = await admin_account_service.get_account(account_id)
    except AdminAccountNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    except AdminServiceError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Service error")

    try:
        revoked_count = await device_service.remove_device(account.id, device_guid)
        await audit_service.record_event(
            event_type="device_deletion",
            actor_id=str(current_admin.id),
            target_id=account_id,
            details={
                "action": "remove_device",
                "device_guid": device_guid,
                "account_id": account_id,
                "refresh_tokens_revoked": revoked_count,
                "source": "operator",
            },
        )
    except DeviceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    except (DeviceOwnershipError, InactiveDeviceError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except DeviceServiceError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Service error removing device")

    remaining_devices = await device_service.get_devices_for_account(account.id)
    active_remaining = len([d for d in remaining_devices if d.is_active])
    return DeviceRemovalResponseDTO(
        removed=True,
        remaining_devices=active_remaining,
        refresh_tokens_revoked=revoked_count,
    )


# ── Session endpoint ──────────────────────────────────────────────────────────


@router.post(
    "/accounts/{account_id}/logout-all",
    summary="Force logout all sessions for an account (super-admin only)",
    response_model=AdminLogoutAllResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Admin authentication required"},
        403: {"description": "Super-admin privilege required"},
        404: {"description": "Account not found"},
    },
)
async def logout_all(
    account_id: str,
    current_admin: AdminUser = Depends(require_super_admin),
    admin_account_service: AdminAccountService = Depends(get_admin_account_service),
) -> AdminLogoutAllResponse:
    """
    Revoke all active refresh token sessions for a customer account.
    Requires super-admin privileges. Reuses RefreshTokenService — no RTR logic is duplicated.
    """
    try:
        revoked_count = await admin_account_service.logout_all(account_id)
        # Audit log: forced logout all sessions
        await audit_service.record_event(
            event_type="admin_action",
            actor_id=str(current_admin.id),
            target_id=account_id,
            details={"action": "logout_all", "account_id": account_id, "revoked_count": revoked_count},
        )
    except AdminAccountNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    except AdminServiceError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Service error")
    logger.info("Administrative logout-all executed.")
    return AdminLogoutAllResponse(revoked_count=revoked_count)


# ── Signals endpoint ──────────────────────────────────────────────────────────


@router.get(
    "/accounts/{account_id}/signals",
    summary="List connection signals for an account (paginated)",
    response_model=AdminSignalListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Admin authentication required"},
        404: {"description": "Account not found"},
    },
)
async def list_signals(
    account_id: str,
    limit: int = Query(default=50, ge=1, le=200, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
    current_admin: AdminUser = Depends(get_current_admin),
    admin_account_service: AdminAccountService = Depends(get_admin_account_service),
    signal_service: ConnectionSignalService = Depends(get_signal_service),
) -> AdminSignalListResponse:
    """
    Retrieve connection security signals for a customer account, newest first.
    Available to all authenticated administrators. Read-only.
    """
    logger.info("Administrative account lookup.")
    try:
        account = await admin_account_service.get_account(account_id)
    except AdminAccountNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    except AdminServiceError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Service error")

    signals = await signal_service.get_recent_signals(account.id, limit=limit, offset=offset)
    return AdminSignalListResponse(
        signals=[
            AdminSignalResponse(
                id=str(s.id),
                event_type=s.event_type.value,
                source_ip=s.source_ip,
                user_agent=s.user_agent,
                occurred_at=s.occurred_at,
                success=s.success,
            )
            for s in signals
        ],
        total=len(signals),
    )
