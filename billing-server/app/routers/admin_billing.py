"""
admin_billing.py — Administrative Billing & Operations API Router (Phase 2.8).

Provides authenticated HTTP endpoints for admin dashboard, subscriptions, payments,
provisioning profiles, retry queue, and system health.
Thin router layer only: no direct database access or third-party provider calls.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import (
    get_admin_billing_service,
    get_current_admin,
    require_super_admin,
)
from app.models.admin_user import AdminUser
from app.rate_limit import require_rate_limit
from app.services.admin_billing_service import AdminBillingService
from app.services.admin_billing_dtos import (
    AdminDashboardDTO,
    AdminSubscriptionDTO,
    AdminSubscriptionListDTO,
    AdminSubscriptionRenewRequest,
    AdminSubscriptionGraceRequest,
    AdminPaymentDTO,
    AdminPaymentListDTO,
    AdminPaymentResolveRequest,
    AdminProvisioningDTO,
    AdminProvisioningListDTO,
    AdminRetryItemDTO,
    AdminRetryQueueDTO,
    AdminSystemHealthDTO,
)
from app.services.exceptions import (
    SubscriptionNotFoundError,
    PaymentNotFoundError,
    ProvisioningServiceError,
    ServiceError,
)
from app.exceptions import EntityNotFoundError
from app.security_hardening.audit import audit_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin Billing & Operations"],
    dependencies=[Depends(require_rate_limit("admin_endpoints"))],
)


def _handle_error(exc: Exception, action: str) -> None:
    logger.error("Error during admin action=%s: %s", action, str(exc))
    if isinstance(exc, (SubscriptionNotFoundError, PaymentNotFoundError, EntityNotFoundError)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (ServiceError, ProvisioningServiceError, ValueError)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


# ── Dashboard ───────────────────────────────────────────────────────────────

@router.get(
    "/dashboard",
    response_model=AdminDashboardDTO,
    summary="Retrieve administrative billing dashboard metrics",
)
async def get_dashboard(
    _admin: AdminUser = Depends(get_current_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminDashboardDTO:
    """Get aggregated operational metrics and today's revenue."""
    try:
        return await service.get_dashboard_metrics()
    except Exception as exc:
        _handle_error(exc, "get_dashboard")


# ── Subscriptions ───────────────────────────────────────────────────────────

@router.get(
    "/subscriptions",
    response_model=AdminSubscriptionListDTO,
    summary="List customer subscriptions",
)
async def list_subscriptions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: str | None = Query(None, alias="status"),
    _admin: AdminUser = Depends(get_current_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminSubscriptionListDTO:
    """Retrieve paginated list of customer subscriptions."""
    try:
        return await service.list_subscriptions(limit=limit, offset=offset, status=status_filter)
    except Exception as exc:
        _handle_error(exc, "list_subscriptions")


@router.get(
    "/subscription/{subscription_id}",
    response_model=AdminSubscriptionDTO,
    summary="Get subscription details",
)
async def get_subscription(
    subscription_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminSubscriptionDTO:
    """Retrieve details for a specific subscription by ID."""
    try:
        return await service.get_subscription(subscription_id)
    except Exception as exc:
        _handle_error(exc, "get_subscription")


@router.post(
    "/subscription/{id}/activate",
    response_model=AdminSubscriptionDTO,
    summary="Activate subscription",
)
async def activate_subscription(
    id: str,
    _admin: AdminUser = Depends(require_super_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminSubscriptionDTO:
    """Administratively force activate a subscription."""
    try:
        result = await service.activate_subscription(id)
        # Audit log: subscription activation
        await audit_service.record_event(
            event_type="subscription_change",
            actor_id=str(_admin.id),
            target_id=id,
            details={"action": "activate_subscription", "subscription_id": id},
        )
        return result
    except Exception as exc:
        _handle_error(exc, "activate_subscription")


@router.post(
    "/subscription/{id}/grace",
    response_model=AdminSubscriptionDTO,
    summary="Put subscription in grace period",
)
async def grace_subscription(
    id: str,
    body: AdminSubscriptionGraceRequest = AdminSubscriptionGraceRequest(),
    _admin: AdminUser = Depends(require_super_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminSubscriptionDTO:
    """Administratively put a subscription into a grace period."""
    try:
        result = await service.grace_subscription(id, grace_duration_days=body.grace_duration_days)
        await audit_service.record_event(
            event_type="subscription_change",
            actor_id=str(_admin.id),
            target_id=id,
            details={"action": "grace_subscription", "subscription_id": id, "grace_duration_days": body.grace_duration_days},
        )
        return result
    except Exception as exc:
        _handle_error(exc, "grace_subscription")


@router.post(
    "/subscription/{id}/expire",
    response_model=AdminSubscriptionDTO,
    summary="Expire subscription",
)
async def expire_subscription(
    id: str,
    _admin: AdminUser = Depends(require_super_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminSubscriptionDTO:
    """Administratively expire a subscription."""
    try:
        result = await service.expire_subscription(id)
        await audit_service.record_event(
            event_type="subscription_change",
            actor_id=str(_admin.id),
            target_id=id,
            details={"action": "expire_subscription", "subscription_id": id},
        )
        return result
    except Exception as exc:
        _handle_error(exc, "expire_subscription")


@router.post(
    "/subscription/{id}/cancel",
    response_model=AdminSubscriptionDTO,
    summary="Cancel subscription",
)
async def cancel_subscription(
    id: str,
    _admin: AdminUser = Depends(require_super_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminSubscriptionDTO:
    """Administratively cancel a subscription."""
    try:
        result = await service.cancel_subscription(id)
        await audit_service.record_event(
            event_type="subscription_change",
            actor_id=str(_admin.id),
            target_id=id,
            details={"action": "cancel_subscription", "subscription_id": id},
        )
        return result
    except Exception as exc:
        _handle_error(exc, "cancel_subscription")


@router.post(
    "/subscription/{id}/renew",
    response_model=AdminSubscriptionDTO,
    summary="Renew subscription expiration",
)
async def renew_subscription(
    id: str,
    body: AdminSubscriptionRenewRequest,
    _admin: AdminUser = Depends(require_super_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminSubscriptionDTO:
    """Administratively renew or extend subscription expiration."""
    try:
        result = await service.renew_subscription(id, new_expires_at=body.new_expires_at)
        await audit_service.record_event(
            event_type="subscription_change",
            actor_id=str(_admin.id),
            target_id=id,
            details={"action": "renew_subscription", "subscription_id": id},
        )
        return result
    except Exception as exc:
        _handle_error(exc, "renew_subscription")


# ── Payments ────────────────────────────────────────────────────────────────

@router.get(
    "/payments",
    response_model=AdminPaymentListDTO,
    summary="List payment transactions",
)
async def list_payments(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: str | None = Query(None, alias="status"),
    _admin: AdminUser = Depends(get_current_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminPaymentListDTO:
    """Retrieve paginated list of payment transactions."""
    try:
        return await service.list_payments(limit=limit, offset=offset, status=status_filter)
    except Exception as exc:
        _handle_error(exc, "list_payments")


@router.get(
    "/payment/{payment_id}",
    response_model=AdminPaymentDTO,
    summary="Get payment details",
)
async def get_payment(
    payment_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminPaymentDTO:
    """Retrieve details for a specific payment."""
    try:
        return await service.get_payment(payment_id)
    except Exception as exc:
        _handle_error(exc, "get_payment")


@router.post(
    "/payment/{id}/reconcile",
    response_model=AdminPaymentDTO,
    summary="Reconcile payment with gateway",
)
async def reconcile_payment(
    id: str,
    _admin: AdminUser = Depends(require_super_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminPaymentDTO:
    """Reconcile payment state with remote payment gateway."""
    try:
        result = await service.reconcile_payment(id)
        await audit_service.record_event(
            event_type="payment_event",
            actor_id=str(_admin.id),
            target_id=id,
            details={"action": "reconcile_payment", "payment_id": id},
        )
        return result
    except Exception as exc:
        _handle_error(exc, "reconcile_payment")


@router.post(
    "/payment/{id}/resolve",
    response_model=AdminPaymentDTO,
    summary="Manually resolve payment",
)
async def resolve_payment(
    id: str,
    body: AdminPaymentResolveRequest = AdminPaymentResolveRequest(),
    _admin: AdminUser = Depends(require_super_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminPaymentDTO:
    """Manually resolve a failed or stuck payment."""
    try:
        result = await service.resolve_payment(id, reason=body.reason)
        await audit_service.record_event(
            event_type="payment_event",
            actor_id=str(_admin.id),
            target_id=id,
            details={"action": "resolve_payment", "payment_id": id, "reason": body.reason},
        )
        return result
    except Exception as exc:
        _handle_error(exc, "resolve_payment")


# ── Provisioning ────────────────────────────────────────────────────────────

@router.get(
    "/provisioning",
    response_model=AdminProvisioningListDTO,
    summary="List provisioning profiles",
)
async def list_provisioning(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    state_filter: str | None = Query(None, alias="state"),
    _admin: AdminUser = Depends(get_current_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminProvisioningListDTO:
    """Retrieve paginated list of VPN provisioning profiles."""
    try:
        return await service.list_provisioning(limit=limit, offset=offset, state=state_filter)
    except Exception as exc:
        _handle_error(exc, "list_provisioning")


@router.post(
    "/provisioning/{id}/sync",
    response_model=AdminProvisioningDTO,
    summary="Synchronize provisioning profile",
)
async def sync_provisioning(
    id: str,
    _admin: AdminUser = Depends(require_super_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminProvisioningDTO:
    """Synchronize VPN profile with remote Marzban server."""
    try:
        result = await service.sync_provisioning(id)
        await audit_service.record_event(
            event_type="admin_action",
            actor_id=str(_admin.id),
            target_id=id,
            details={"action": "sync_provisioning", "profile_id": id},
        )
        return result
    except Exception as exc:
        _handle_error(exc, "sync_provisioning")


@router.post(
    "/provisioning/{id}/retry",
    response_model=AdminProvisioningDTO,
    summary="Retry provisioning",
)
async def retry_provisioning(
    id: str,
    _admin: AdminUser = Depends(require_super_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminProvisioningDTO:
    """Retry provisioning an account on VPN gateway."""
    try:
        result = await service.retry_provisioning(id)
        await audit_service.record_event(
            event_type="admin_action",
            actor_id=str(_admin.id),
            target_id=id,
            details={"action": "retry_provisioning", "profile_id": id},
        )
        return result
    except Exception as exc:
        _handle_error(exc, "retry_provisioning")


@router.post(
    "/provisioning/{id}/suspend",
    response_model=AdminProvisioningDTO,
    summary="Suspend provisioning profile",
)
async def suspend_provisioning(
    id: str,
    _admin: AdminUser = Depends(require_super_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminProvisioningDTO:
    """Suspend user on remote VPN server."""
    try:
        result = await service.suspend_provisioning(id)
        await audit_service.record_event(
            event_type="admin_action",
            actor_id=str(_admin.id),
            target_id=id,
            details={"action": "suspend_provisioning", "profile_id": id},
        )
        return result
    except Exception as exc:
        _handle_error(exc, "suspend_provisioning")


@router.post(
    "/provisioning/{id}/restore",
    response_model=AdminProvisioningDTO,
    summary="Restore suspended provisioning profile",
)
async def restore_provisioning(
    id: str,
    _admin: AdminUser = Depends(require_super_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminProvisioningDTO:
    """Restore suspended user on remote VPN server."""
    try:
        result = await service.restore_provisioning(id)
        await audit_service.record_event(
            event_type="admin_action",
            actor_id=str(_admin.id),
            target_id=id,
            details={"action": "restore_provisioning", "profile_id": id},
        )
        return result
    except Exception as exc:
        _handle_error(exc, "restore_provisioning")


@router.post(
    "/provisioning/{id}/terminate",
    response_model=AdminProvisioningDTO | None,
    summary="Terminate provisioning profile",
)
async def terminate_provisioning(
    id: str,
    _admin: AdminUser = Depends(require_super_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminProvisioningDTO | None:
    """Terminate and delete user on remote VPN server."""
    try:
        result = await service.terminate_provisioning(id)
        await audit_service.record_event(
            event_type="admin_action",
            actor_id=str(_admin.id),
            target_id=id,
            details={"action": "terminate_provisioning", "profile_id": id},
        )
        return result
    except Exception as exc:
        _handle_error(exc, "terminate_provisioning")


# ── Retry Queue ─────────────────────────────────────────────────────────────

@router.get(
    "/retry-queue",
    response_model=AdminRetryQueueDTO,
    summary="Inspect provisioning retry queue",
)
async def get_retry_queue(
    _admin: AdminUser = Depends(get_current_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminRetryQueueDTO:
    """Inspect pending and permanently failed provisioning retry items."""
    try:
        return await service.get_retry_queue()
    except Exception as exc:
        _handle_error(exc, "get_retry_queue")


@router.post(
    "/retry/{id}/retry-now",
    response_model=AdminRetryItemDTO,
    summary="Execute immediate retry",
)
async def retry_now(
    id: str,
    _admin: AdminUser = Depends(require_super_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminRetryItemDTO:
    """Force immediate retry execution for a pending retry queue item."""
    try:
        result = await service.retry_now(id)
        await audit_service.record_event(
            event_type="admin_action",
            actor_id=str(_admin.id),
            target_id=id,
            details={"action": "retry_now", "retry_id": id},
        )
        return result
    except Exception as exc:
        _handle_error(exc, "retry_now")


@router.post(
    "/retry/{id}/discard",
    response_model=AdminRetryItemDTO,
    summary="Discard retry item",
)
async def discard_retry(
    id: str,
    _admin: AdminUser = Depends(require_super_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminRetryItemDTO:
    """Discard a pending retry queue item."""
    try:
        result = await service.discard_retry(id)
        await audit_service.record_event(
            event_type="admin_action",
            actor_id=str(_admin.id),
            target_id=id,
            details={"action": "discard_retry", "retry_id": id},
        )
        return result
    except Exception as exc:
        _handle_error(exc, "discard_retry")


# ── System Health ───────────────────────────────────────────────────────────

@router.get(
    "/system-health",
    response_model=AdminSystemHealthDTO,
    summary="Inspect system health",
)
async def get_system_health(
    _admin: AdminUser = Depends(get_current_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminSystemHealthDTO:
    """Check health of PostgreSQL, Marzban, Razorpay, and background services."""
    try:
        return await service.get_system_health()
    except Exception as exc:
        _handle_error(exc, "get_system_health")
