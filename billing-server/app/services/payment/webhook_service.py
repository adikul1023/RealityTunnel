import logging
from typing import Any
from app.models.payment import Payment
from app.services.payment.service import PaymentService
from app.services.exceptions import PaymentWebhookError


logger = logging.getLogger(__name__)


class WebhookService:
    """
    Dedicated service for processing incoming payment gateway webhooks.
    Orchestrates the domain dependency chain:
    Webhook Router -> WebhookService -> PaymentService -> SubscriptionService -> ProvisioningService -> CredentialService.
    """

    def __init__(self, payment_service: PaymentService) -> None:
        self.payment_service = payment_service

    async def process_event(
        self,
        raw_payload: bytes | str,
        signature: str,
    ) -> Payment | None:
        """
        Verify webhook signature, parse event DTO, and dispatch to appropriate PaymentService method.
        Idempotent: duplicate webhook deliveries return clean existing state.
        Zero-secret logging: logs event types and IDs without logging secrets or raw HMACs.
        """
        dto = await self.payment_service.provider.verify_webhook(raw_payload, signature)

        logger.info(
            "Processing verified webhook event=%s order_id=%s payment_id=%s",
            dto.event_type,
            dto.provider_order_id,
            dto.provider_payment_id,
        )

        if dto.event_type in ("payment.captured", "payment.authorized", "order.paid"):
            if not dto.provider_order_id:
                raise PaymentWebhookError("Webhook payload for captured payment missing order ID")
            if not dto.provider_payment_id:
                raise PaymentWebhookError("Webhook payload for captured payment missing payment ID")
            return await self.payment_service.confirm_payment(
                provider_order_id=dto.provider_order_id,
                provider_payment_id=dto.provider_payment_id,
            )
        elif dto.event_type in ("payment.failed",):
            if not dto.provider_order_id:
                raise PaymentWebhookError("Webhook payload for failed payment missing order ID")
            return await self.payment_service.fail_payment(
                provider_order_id=dto.provider_order_id,
                reason="Webhook payment.failed event",
            )
        elif dto.event_type in ("refund.processed",):
            return await self.payment_service.process_refund_webhook(
                provider_order_id=dto.provider_order_id,
                provider_payment_id=dto.provider_payment_id,
            )

        logger.info("Ignored unhandled webhook event type: %s", dto.event_type)
        return None
