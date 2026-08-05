"""
admin_operations.py — Router for Phase 2A infrastructure status, audit event cursor pagination, and version reporting.
All endpoints protected by admin authentication and rate limiting.
"""
from __future__ import annotations

import logging
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Request, status

import hmac
import hashlib
import json
import secrets
import time

from app.dependencies import get_current_admin, get_operations_service, get_settings
from app.config import Settings
from app.models.admin_user import AdminUser
from app.rate_limit import require_rate_limit
from app.services.operations_dtos import (
    AdminVersionResponseDTO,
    AuditEventCursorPageDTO,
    InfrastructureStatusDTO,
)
from app.services.operations_service import OperationsService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin Operations"],
    dependencies=[Depends(require_rate_limit("admin_endpoints"))],
)


@router.get(
    "/infrastructure/status",
    summary="Get infrastructure component health map (1-2s timeouts)",
    response_model=InfrastructureStatusDTO,
    status_code=status.HTTP_200_OK,
    responses={401: {"description": "Admin authentication required"}},
)
async def get_infrastructure_status(
    request: Request,
    current_admin: AdminUser = Depends(get_current_admin),
    operations_service: OperationsService = Depends(get_operations_service),
) -> InfrastructureStatusDTO:
    """
    Return concurrent health status checks for billing_api, database, marzban, xray,
    scheduler, redis, caddy, and edge nodes. Each probe has a strict 1.5s timeout.
    """
    logger.info("Admin %s requesting infrastructure status", current_admin.id)
    return await operations_service.get_infrastructure_status(request.app.state)


@router.get(
    "/audit-events",
    summary="Get cursor-paginated audit log events with source filtering",
    response_model=AuditEventCursorPageDTO,
    status_code=status.HTTP_200_OK,
    responses={401: {"description": "Admin authentication required"}},
)
async def list_audit_events(
    cursor: str | None = Query(default=None, description="Pagination keyset cursor"),
    since: datetime | None = Query(default=None, description="Filter events since this timestamp"),
    source: str | None = Query(default=None, description="Filter by event source (billing, marzban, scheduler, operator, system)"),
    event_type: str | None = Query(default=None, description="Filter by exact event type"),
    limit: int = Query(default=20, ge=1, le=100, description="Number of events to retrieve (max 100)"),
    current_admin: AdminUser = Depends(get_current_admin),
    operations_service: OperationsService = Depends(get_operations_service),
) -> AuditEventCursorPageDTO:
    """
    Retrieve audit log events using keyset cursor pagination descending by timestamp and event_id.
    Supports filtering by source subsystem (`billing`, `marzban`, `scheduler`, `operator`, `system`).
    """
    logger.info("Admin %s querying audit events cursor=%s source=%s", current_admin.id, cursor, source)
    return await operations_service.get_audit_events_cursor(
        cursor=cursor,
        since=since,
        source=source,
        event_type=event_type,
        limit=limit,
    )


@router.get(
    "/version",
    summary="Get backend and component version identifiers",
    response_model=AdminVersionResponseDTO,
    status_code=status.HTTP_200_OK,
    responses={401: {"description": "Admin authentication required"}},
)
async def get_version(
    current_admin: AdminUser = Depends(get_current_admin),
    operations_service: OperationsService = Depends(get_operations_service),
) -> AdminVersionResponseDTO:
    """
    Retrieve exact backend build and component versions for operator troubleshooting.
    """
    return operations_service.get_version_info()


@router.post(
    "/infrastructure/{service_name}/restart",
    summary="Restart a backend infrastructure service",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        401: {"description": "Admin authentication required"},
        400: {"description": "Invalid service name"},
    },
)
async def restart_infrastructure_service(
    service_name: str,
    current_admin: AdminUser = Depends(get_current_admin),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Request a restart of a backend service (e.g. marzban, xray, caddy).
    Writes a signed JSON command to the IPC file for the host agent to pick up.
    """
    logger.info("Admin %s requesting restart of service %s", current_admin.id, service_name)
    
    valid_services = ["marzban", "xray", "caddy", "redis", "scheduler"]
    if service_name not in valid_services:
        raise HTTPException(status_code=400, detail=f"Invalid service name. Allowed: {', '.join(valid_services)}")
        
    import os
    ipc_file = os.getenv("IPC_COMMAND_DIR", "/app/ipc") + "/commands.txt"
    try:
        os.makedirs(os.path.dirname(ipc_file), exist_ok=True)

        timestamp = int(time.time())
        nonce = secrets.token_hex(16)  # 128-bit random nonce; single-use
        service = service_name
        action = "restart"
        msg = f"{service}:{action}:{timestamp}:{nonce}"

        secret = settings.ipc_secret_key.get_secret_value().encode('utf-8')
        signature = hmac.new(secret, msg.encode('utf-8'), hashlib.sha256).hexdigest()

        payload = {
            "service": service,
            "action": action,
            "timestamp": timestamp,
            "nonce": nonce,
            "hmac": signature,
        }

        with open(ipc_file, "a") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception as e:
        logger.error(f"Failed to write IPC command: {e}")
        raise HTTPException(status_code=500, detail="Failed to enqueue restart command")

    return {"status": "accepted", "message": f"Restart command for {service_name} enqueued"}


@router.post(
    "/infrastructure/xray/reload",
    summary="Reload Xray configuration without dropping connections",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        401: {"description": "Admin authentication required"},
    },
)
async def reload_xray_config(
    current_admin: AdminUser = Depends(get_current_admin),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Request a hot-reload of the Xray configuration without dropping active connections.
    Writes a signed JSON command to the IPC file for the host agent to pick up.
    """
    logger.info("Admin %s requesting xray reload", current_admin.id)
    
    import os
    ipc_file = os.getenv("IPC_COMMAND_DIR", "/app/ipc") + "/commands.txt"
    try:
        os.makedirs(os.path.dirname(ipc_file), exist_ok=True)

        timestamp = int(time.time())
        nonce = secrets.token_hex(16)  # 128-bit random nonce; single-use
        service = "xray"
        action = "reload"
        msg = f"{service}:{action}:{timestamp}:{nonce}"

        secret = settings.ipc_secret_key.get_secret_value().encode('utf-8')
        signature = hmac.new(secret, msg.encode('utf-8'), hashlib.sha256).hexdigest()

        payload = {
            "service": service,
            "action": action,
            "timestamp": timestamp,
            "nonce": nonce,
            "hmac": signature,
        }

        with open(ipc_file, "a") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception as e:
        logger.error(f"Failed to write IPC command: {e}")
        raise HTTPException(status_code=500, detail="Failed to enqueue reload command")

    return {"status": "accepted", "message": "Xray reload command enqueued"}
