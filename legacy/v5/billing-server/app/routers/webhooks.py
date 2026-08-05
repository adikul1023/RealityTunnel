import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from app.dependencies import get_webhook_service
from app.services.payment.webhook_service import WebhookService
from app.services.exceptions import (
    PaymentWebhookError,
    PaymentVerificationError,
    ProvisioningTimeoutError,
    ProvisioningUnavailableError,
    ProvisioningSynchronizationError,
    PaymentTimeoutError,
    PaymentServiceError,
    ServiceError,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


@router.post("/razorpay", status_code=status.HTTP_200_OK)
async def handle_razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(None),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> dict[str, str]:
    """
    Ingest Razorpay webhook notifications.
    Verifies HMAC-SHA256 signature in X-Razorpay-Signature header.
    Maps domain exceptions to HTTP status codes:
    - 200 OK: Successfully processed or duplicate event (idempotent).
    - 400 Bad Request: Invalid signature, malformed JSON, or validation error (no retry).
    - 503 Service Unavailable: Transient gateway or provisioning timeout (provider retries).
    """
    if not x_razorpay_signature:
        logger.warning("Rejected webhook request: missing X-Razorpay-Signature header")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Razorpay-Signature header",
        )

    try:
        raw_payload = await request.body()
        await webhook_service.process_event(raw_payload, x_razorpay_signature)
        return {"status": "ok"}

    except (PaymentWebhookError, PaymentVerificationError, ValueError) as exc:
        logger.warning("Webhook verification/validation failed: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except (ProvisioningTimeoutError, ProvisioningUnavailableError, PaymentTimeoutError) as exc:
        logger.error("Transient error during webhook processing: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable, please retry",
        )
    except Exception as exc:
        logger.error("Unhandled exception processing webhook: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
