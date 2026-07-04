"""
billing.py — Customer Billing API Endpoints Router (Phase 2.7).

Thin orchestration layer connecting HTTP requests to domain BillingService.
Strictly decoupled from business logic, validation logic, and direct database queries.

Endpoints:
  - GET  /api/billing/subscription
  - GET  /api/billing/plans
  - GET  /api/billing/payments
  - GET  /api/billing/payment/{payment_id}
  - POST /api/billing/purchase
  - POST /api/billing/cancel-auto-renew
  - POST /api/billing/reactivate

SECURITY & LOGGING INVARIANTS:
1. Requires authenticated active customer JWT for all endpoints.
2. Anti-IDOR: Account A cannot read Account B's resources. Returns 404 on cross-account access attempts.
3. Zero-Secret Logging: Never logs payment payloads, customer identifiers, or credentials. Logs only generic event descriptions.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_current_account, get_billing_service
from app.models.account import Account
from app.services import BillingService
from app.services.billing_dtos import (

    SubscriptionDTO,
    PlanDTO,
    PaymentDTO,
    PaymentListDTO,
    PurchaseRequestDTO,
    PurchaseResponseDTO,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/billing", tags=["Billing"])


@router.get(
    "/subscription",
    summary="Get active subscription details",
    response_model=SubscriptionDTO,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Authentication required"},
        500: {"description": "Unexpected service error"},
    },
)
async def get_subscription(
    current_account: Account = Depends(get_current_account),
    billing_service: BillingService = Depends(get_billing_service),
) -> SubscriptionDTO:
    """
    Retrieve customer view of their current active subscription.
    Returns clean default DTO with status 'NONE' if no subscription is active.
    """
    logger.info("Customer subscription lookup.")
    return await billing_service.get_customer_subscription(current_account.id)


@router.get(
    "/plans",
    summary="List available subscription plans",
    response_model=list[PlanDTO],
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Authentication required"},
        500: {"description": "Unexpected service error"},
    },
)
async def list_plans(
    current_account: Account = Depends(get_current_account),
    billing_service: BillingService = Depends(get_billing_service),
) -> list[PlanDTO]:
    """
    List all available subscription plans and their configured limits and pricing from the registry.
    """
    logger.info("Customer plans listing lookup.")
    return billing_service.list_plans()


@router.get(
    "/payments",
    summary="List customer payment history",
    response_model=PaymentListDTO,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Authentication required"},
        500: {"description": "Unexpected service error"},
    },
)
async def list_payments(
    limit: int = Query(default=20, ge=1, le=100, description="Page size limit"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    current_account: Account = Depends(get_current_account),
    billing_service: BillingService = Depends(get_billing_service),
) -> PaymentListDTO:
    """
    Retrieve paginated payment history for the authenticated customer account, newest first.
    """
    logger.info("Customer payment history lookup.")
    return await billing_service.list_customer_payments(current_account.id, limit=limit, offset=offset)


@router.get(
    "/payment/{payment_id}",
    summary="Get payment transaction details",
    response_model=PaymentDTO,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Authentication required"},
        404: {"description": "Payment not found or owned by another account"},
        500: {"description": "Unexpected service error"},
    },
)
async def get_payment(
    payment_id: str,
    current_account: Account = Depends(get_current_account),
    billing_service: BillingService = Depends(get_billing_service),
) -> PaymentDTO:
    """
    Retrieve details of a specific payment transaction.
    Enforces Anti-IDOR: returns 404 if payment does not exist or belongs to another account.
    """
    logger.info("Customer payment detail lookup.")
    return await billing_service.get_customer_payment(current_account.id, payment_id)


@router.post(
    "/purchase",
    summary="Initiate subscription purchase order",
    response_model=PurchaseResponseDTO,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Validation error or invalid plan ID"},
        401: {"description": "Authentication required"},
        409: {"description": "Idempotency key conflict"},
        500: {"description": "Unexpected service or gateway error"},
    },
)
async def purchase_subscription(
    request: PurchaseRequestDTO,
    current_account: Account = Depends(get_current_account),
    billing_service: BillingService = Depends(get_billing_service),
) -> PurchaseResponseDTO:
    """
    Initiate a new subscription purchase order via payment gateway provider.
    Does NOT activate subscription; activation happens exclusively via verified webhooks.
    """
    logger.info("Initiating subscription purchase order.")
    return await billing_service.purchase_subscription(current_account.id, request)


@router.post(
    "/cancel-auto-renew",
    summary="Disable automatic renewal for active subscription",
    response_model=SubscriptionDTO,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Subscription already cancelled or invalid state"},
        401: {"description": "Authentication required"},
        404: {"description": "No active subscription found"},
        500: {"description": "Unexpected service error"},
    },
)
async def cancel_auto_renew(
    current_account: Account = Depends(get_current_account),
    billing_service: BillingService = Depends(get_billing_service),
) -> SubscriptionDTO:
    """
    Disable automatic renewal for the customer's active subscription. Idempotent.
    """
    logger.info("Disabling auto renewal for customer subscription.")
    return await billing_service.cancel_auto_renew(current_account.id)


@router.post(
    "/reactivate",
    summary="Reactivate automatic renewal for active subscription",
    response_model=SubscriptionDTO,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Subscription cancelled or invalid state"},
        401: {"description": "Authentication required"},
        404: {"description": "No active subscription found"},
        500: {"description": "Unexpected service error"},
    },
)
async def reactivate_subscription(
    current_account: Account = Depends(get_current_account),
    billing_service: BillingService = Depends(get_billing_service),
) -> SubscriptionDTO:
    """
    Enable automatic renewal for the customer's active subscription. Idempotent.
    """
    logger.info("Reactivating auto renewal for customer subscription.")
    return await billing_service.reactivate_auto_renew(current_account.id)
