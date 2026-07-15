"""
admin_operations.py — Router for Phase 2A infrastructure status, audit event cursor pagination, and version reporting.
All endpoints protected by admin authentication and rate limiting.
"""
from __future__ import annotations

import logging
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Request, status

from app.dependencies import get_current_admin, get_operations_service
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
    limit: int = Query(default=50, ge=1, le=200, description="Number of events to retrieve"),
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
