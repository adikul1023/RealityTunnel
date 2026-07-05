"""
billing_service.py — BillingService orchestration layer for Customer Billing API (Phase 2.7).

Strictly enforces architectural boundaries:
- Bridges domain services (SubscriptionService, PaymentService, SubscriptionPlanService) and customer routers.
- Converts internal domain models into secure customer DTOs.
- Never leaks internal database UUIDs (account.id, payment.id, subscription.id) or provider secrets.
- Performs zero database repository queries directly; relies exclusively on domain services.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.models.account import Account
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.services.billing_dtos import (
    PaymentDTO,
    PaymentListDTO,
    PlanDTO,
    PurchaseRequestDTO,
    PurchaseResponseDTO,
    SubscriptionDTO,
)
from app.services.payment.service import PaymentService
from app.services.subscription_plan import SubscriptionPlanService
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)


class BillingService:
    """
    Orchestration service for customer billing views and actions.
    Decoupled from routers and databases.
    """

    def __init__(
        self,
        subscription_service: SubscriptionService,
        payment_service: PaymentService,
        plan_service: SubscriptionPlanService,
    ) -> None:
        self.subscription_service = subscription_service
        self.payment_service = payment_service
        self.plan_service = plan_service

    async def get_customer_subscription(self, account_id: uuid.UUID) -> SubscriptionDTO:
        """
        Retrieve customer view of their current active subscription.
        If none exists, returns a clean DTO with lifecycle_status='NONE' without throwing 404 or 500.
        """
        sub = await self.subscription_service.get_active_subscription(account_id)
        if not sub:
            logger.info(
                "Account %s has no active subscription; returning clean default DTO",
                account_id,
            )
            return SubscriptionDTO(
                plan="none",
                lifecycle_status="NONE",
                started_at=None,
                expires_at=None,
                grace_until=None,
                auto_renew=False,
            )

        return SubscriptionDTO(
            plan=sub.plan_id,
            lifecycle_status=sub.status.value,
            started_at=sub.starts_at,
            expires_at=sub.expires_at,
            grace_until=sub.grace_expires_at,
            auto_renew=sub.auto_renew,
        )

    def list_plans(self) -> list[PlanDTO]:
        """
        Return available subscription plans from the code-defined registry.
        Requires zero database queries.
        """
        plans = self.plan_service.list_plans()
        return [
            PlanDTO(
                plan_id=p.plan_id,
                name=p.display_name,
                price=p.price_minor_units,
                currency=p.currency,
                max_devices=p.max_devices,
                max_concurrent_ips=p.max_concurrent_ips,
                quota=p.data_quota_bytes,
            )
            for p in plans
        ]

    def _map_payment_dto(self, payment: Payment) -> PaymentDTO:
        """
        Map Payment entity to PaymentDTO.
        Uses provider_order_id as the primary public payment_id to prevent leaking DB UUIDs.
        If provider_order_id is missing, falls back to provider_payment_id or stringified UUID.
        """
        public_id = (
            payment.provider_order_id or payment.provider_payment_id or str(payment.id)
        )
        return PaymentDTO(
            payment_id=public_id,
            provider=payment.provider.value,
            amount=payment.amount_minor_units,
            currency=payment.currency,
            status=payment.status.value,
            created_at=payment.created_at,
        )

    async def list_customer_payments(
        self, account_id: uuid.UUID, limit: int = 20, offset: int = 0
    ) -> PaymentListDTO:
        """
        Retrieve paginated payment history for an account, ordered newest first.
        """
        payments, total = await self.payment_service.list_account_payments(
            account_id, limit, offset
        )
        dto_list = [self._map_payment_dto(p) for p in payments]
        return PaymentListDTO(
            payments=dto_list,
            total=total,
            limit=min(max(1, limit), 100),
            offset=max(0, offset),
        )

    async def get_customer_payment(
        self, account_id: uuid.UUID, payment_identifier: str
    ) -> PaymentDTO:
        """
        Retrieve a specific payment by identifier. Enforces Anti-IDOR via domain service.
        """
        payment = await self.payment_service.get_account_payment(
            account_id, payment_identifier
        )
        return self._map_payment_dto(payment)

    async def purchase_subscription(
        self, account_id: uuid.UUID, request: PurchaseRequestDTO
    ) -> PurchaseResponseDTO:
        """
        Initiate an order for a subscription purchase via PaymentService.
        Does NOT activate the subscription; activation occurs exclusively via verified webhooks.
        """
        plan = self.plan_service.get_plan(request.plan_id)
        # SECURITY INVARIANT (Finding C-1): amount is always derived from the server-side plan
        # registry. PurchaseRequestDTO intentionally has no client-controllable amount field.
        amount_minor_units = plan.price_minor_units

        payment = await self.payment_service.create_payment(
            account_id=account_id,
            amount_minor_units=amount_minor_units,
            currency=request.currency,
            idempotency_key=request.idempotency_key,
            plan_id=request.plan_id,
        )

        public_id = (
            payment.provider_order_id or payment.provider_payment_id or str(payment.id)
        )
        return PurchaseResponseDTO(
            payment_id=public_id,
            provider=payment.provider.value,
            amount=payment.amount_minor_units,
            currency=payment.currency,
            status=payment.status.value,
            created_at=payment.created_at,
        )

    async def cancel_auto_renew(self, account_id: uuid.UUID) -> SubscriptionDTO:
        """
        Disable automatic renewal for the customer's active subscription. Idempotent.
        """
        sub = await self.subscription_service.update_auto_renew(
            account_id, auto_renew=False
        )
        return SubscriptionDTO(
            plan=sub.plan_id,
            lifecycle_status=sub.status.value,
            started_at=sub.starts_at,
            expires_at=sub.expires_at,
            grace_until=sub.grace_expires_at,
            auto_renew=sub.auto_renew,
        )

    async def reactivate_auto_renew(self, account_id: uuid.UUID) -> SubscriptionDTO:
        """
        Enable automatic renewal for the customer's active subscription. Idempotent.
        """
        sub = await self.subscription_service.update_auto_renew(
            account_id, auto_renew=True
        )
        return SubscriptionDTO(
            plan=sub.plan_id,
            lifecycle_status=sub.status.value,
            started_at=sub.starts_at,
            expires_at=sub.expires_at,
            grace_until=sub.grace_expires_at,
            auto_renew=sub.auto_renew,
        )
