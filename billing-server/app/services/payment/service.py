"""
service.py — PaymentService orchestrating payment transactions, gateway interactions,
and entitlement activation via SubscriptionService (Phase 2.3).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import EntityNotFoundError
from app.models import Payment, PaymentStatus, PaymentProviderType
from app.models.base import SubscriptionLifecycleStatus
from app.repositories import PaymentRepository, SubscriptionRepository
from app.services.subscription_service import SubscriptionService
from app.services.payment.provider import PaymentProvider
from app.services.exceptions import (
    PaymentServiceError,
    PaymentVerificationError,
    PaymentWebhookError,
    DuplicateWebhookError,
    PaymentRefundError,
)

logger = logging.getLogger(__name__)


class PaymentService:
    """
    Orchestration service for payment lifecycle, webhook verification, and entitlement updates.
    Strictly decoupled from VPN provisioning: all entitlement changes flow through SubscriptionService.
    Never communicates with ProvisioningService or Marzban directly.
    """

    def __init__(
        self,
        session: AsyncSession,
        provider: PaymentProvider,
    ) -> None:
        self.session = session
        self.provider = provider
        self.payment_repo = PaymentRepository(session)
        self.subscription_repo = SubscriptionRepository(session)
        self.subscription_service = SubscriptionService(session)

    async def create_payment(
        self,
        account_id: uuid.UUID,
        amount_minor_units: int,
        currency: str,
        idempotency_key: str,
        plan_id: str = "pro",
        subscription_id: uuid.UUID | None = None,
    ) -> Payment:
        """
        Create a new payment transaction and initiate an order on the payment gateway.
        Idempotent: if idempotency_key already exists, returns the existing payment record.
        """
        existing = await self.payment_repo.get_by_idempotency_key(idempotency_key, for_update=True)
        if existing:
            logger.info("Returning existing payment id=%s for idempotency_key=%s", existing.id, idempotency_key)
            return existing

        receipt = f"rcpt_{idempotency_key[:24]}"
        notes = {
            "account_id": str(account_id),
            "plan_id": plan_id,
        }
        if subscription_id:
            notes["subscription_id"] = str(subscription_id)

        order_dto = await self.provider.create_order(
            amount_minor_units=amount_minor_units,
            currency=currency,
            receipt=receipt,
            notes=notes,
        )

        payment = await self.payment_repo.create(
            account_id=account_id,
            subscription_id=subscription_id,
            provider=PaymentProviderType.RAZORPAY,
            provider_order_id=order_dto.provider_order_id,
            amount_minor_units=order_dto.amount_minor_units,
            currency=order_dto.currency,
            status=PaymentStatus.CREATED,
            idempotency_key=idempotency_key,
        )
        logger.info("Created new payment id=%s order_id=%s status=%s", payment.id, payment.provider_order_id, payment.status.value)
        return payment

    async def confirm_payment(
        self,
        provider_order_id: str,
        provider_payment_id: str,
        signature: str | None = None,
        raw_payload: bytes | str | None = None,
        plan_id: str = "pro",
    ) -> Payment:
        """
        Confirm a payment upon gateway webhook or redirect verification.
        Must:
        1. Verify webhook signature (if provided).
        2. Verify provider payment status via fetch_payment.
        3. Verify idempotency using row lock (for_update=True).
        4. Persist payment state to PAID.
        5. Activate or renew subscription via SubscriptionService.
        """
        if signature and raw_payload:
            await self.provider.verify_webhook(raw_payload, signature)

        verification = await self.provider.fetch_payment(provider_payment_id)
        if not verification.is_valid:
            raise PaymentVerificationError(
                f"Payment {provider_payment_id} is not valid or captured on the gateway (status={verification.status})"
            )

        payment = await self.payment_repo.get_by_provider_order_id(provider_order_id, for_update=True)
        if not payment:
            raise EntityNotFoundError(f"Payment for order ID {provider_order_id} not found.")

        if payment.status == PaymentStatus.PAID:
            logger.info("Payment id=%s (order=%s) is already PAID. Idempotent return.", payment.id, provider_order_id)
            return payment

        now = datetime.now(timezone.utc)
        payment.provider_payment_id = provider_payment_id
        payment.status = PaymentStatus.PAID
        payment.paid_at = now
        await self.payment_repo.update(payment)

        # Entitlement Activation via SubscriptionService
        if payment.subscription_id:
            sub = await self.subscription_repo.get_by_id(payment.subscription_id, for_update=True)
            if sub:
                if sub.status in (SubscriptionLifecycleStatus.ACTIVE, SubscriptionLifecycleStatus.GRACE, SubscriptionLifecycleStatus.TRIAL):
                    new_expires_at = max(sub.expires_at, now) + timedelta(days=30)
                    await self.subscription_service.renew_subscription(sub.id, new_expires_at)
                else:
                    await self.subscription_service.activate_subscription(sub.id)
                logger.info("Updated existing subscription id=%s for payment id=%s", sub.id, payment.id)
                return payment

        # Look for an existing active subscription for this account
        existing_active = await self.subscription_repo.get_active_for_account(payment.account_id, now, for_update=True)
        if existing_active:
            new_expires_at = max(existing_active.expires_at, now) + timedelta(days=30)
            renewed = await self.subscription_service.renew_subscription(existing_active.id, new_expires_at)
            payment.subscription_id = renewed.id
            await self.payment_repo.update(payment)
            logger.info("Renewed active subscription id=%s for payment id=%s", renewed.id, payment.id)
            return payment

        # Otherwise, create a new active subscription for the account
        new_sub = await self.subscription_service.create_subscription(
            account_id=payment.account_id,
            plan_id=plan_id,
            starts_at=now,
            expires_at=now + timedelta(days=30),
            status=SubscriptionLifecycleStatus.ACTIVE,
        )
        payment.subscription_id = new_sub.id
        await self.payment_repo.update(payment)
        logger.info("Created and linked new subscription id=%s for payment id=%s", new_sub.id, payment.id)
        return payment

    async def fail_payment(
        self,
        provider_order_id: str,
        reason: str | None = None,
    ) -> Payment:
        """
        Mark a payment as failed after notification from the gateway.
        Idempotent if already marked FAILED or CANCELLED.
        """
        payment = await self.payment_repo.get_by_provider_order_id(provider_order_id, for_update=True)
        if not payment:
            raise EntityNotFoundError(f"Payment for order ID {provider_order_id} not found.")

        if payment.status in (PaymentStatus.FAILED, PaymentStatus.CANCELLED):
            return payment

        payment.status = PaymentStatus.FAILED
        await self.payment_repo.update(payment)
        logger.info("Marked payment id=%s as FAILED. Reason: %s", payment.id, reason or "Gateway notification")
        return payment

    async def refund_payment(
        self,
        payment_id: uuid.UUID,
        amount_minor_units: int | None = None,
        notes: dict[str, str] | None = None,
    ) -> Payment:
        """
        Issue a refund for a paid transaction via the gateway provider.
        """
        payment = await self.payment_repo.get_by_id(payment_id, for_update=True)
        if not payment:
            raise EntityNotFoundError(f"Payment with ID {payment_id} not found.")

        if payment.status != PaymentStatus.PAID:
            raise PaymentRefundError(f"Cannot refund payment id={payment_id} in status {payment.status.value}")

        if not payment.provider_payment_id:
            raise PaymentRefundError(f"Payment id={payment_id} is missing provider_payment_id")

        await self.provider.refund_payment(
            provider_payment_id=payment.provider_payment_id,
            amount_minor_units=amount_minor_units or payment.amount_minor_units,
            notes=notes,
        )

        payment.status = PaymentStatus.REFUNDED
        await self.payment_repo.update(payment)
        logger.info("Refunded payment id=%s amount=%s", payment.id, amount_minor_units or payment.amount_minor_units)
        return payment

    async def cancel_payment(
        self,
        payment_id: uuid.UUID,
    ) -> Payment:
        """
        Cancel a pending or created payment before capture.
        """
        payment = await self.payment_repo.get_by_id(payment_id, for_update=True)
        if not payment:
            raise EntityNotFoundError(f"Payment with ID {payment_id} not found.")

        if payment.status in (PaymentStatus.PAID, PaymentStatus.REFUNDED):
            raise PaymentServiceError(f"Cannot cancel payment id={payment_id} in status {payment.status.value}")

        if payment.status == PaymentStatus.CANCELLED:
            return payment

        payment.status = PaymentStatus.CANCELLED
        await self.payment_repo.update(payment)
        logger.info("Cancelled payment id=%s", payment.id)
        return payment

    async def get_payment(self, payment_id: uuid.UUID) -> Payment:
        """
        Retrieve payment details by internal UUID.
        """
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment:
            raise EntityNotFoundError(f"Payment with ID {payment_id} not found.")
        return payment

    async def process_webhook(
        self,
        raw_payload: bytes | str,
        signature: str,
    ) -> Payment | None:
        """
        Process an incoming gateway webhook with idempotency guarantees.
        """
        dto = await self.provider.verify_webhook(raw_payload, signature)
        if not dto.provider_order_id:
            raise PaymentWebhookError("Webhook payload missing order ID")

        if dto.event_type in ("payment.captured", "payment.authorized", "order.paid"):
            if not dto.provider_payment_id:
                raise PaymentWebhookError("Payment captured webhook missing payment ID")
            return await self.confirm_payment(
                provider_order_id=dto.provider_order_id,
                provider_payment_id=dto.provider_payment_id,
            )
        elif dto.event_type in ("payment.failed",):
            return await self.fail_payment(
                provider_order_id=dto.provider_order_id,
                reason="Webhook payment.failed event",
            )

        logger.info("Ignored unhandled webhook event type: %s", dto.event_type)
        return None
