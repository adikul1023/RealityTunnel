import logging
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.models.payment import Payment, PaymentStatus
from app.services.payment.webhook_service import WebhookService
from app.services.payment.provider import PaymentWebhookDTO
from app.services.exceptions import PaymentWebhookError


@pytest.fixture
def mock_payment_service() -> MagicMock:
    service = MagicMock()
    service.provider = MagicMock()
    service.provider.verify_webhook = AsyncMock()
    service.confirm_payment = AsyncMock()
    service.fail_payment = AsyncMock()
    service.process_refund_webhook = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_process_event_authorized_payment_ignored(mock_payment_service: MagicMock):
    service = WebhookService(mock_payment_service)
    mock_payment_service.provider.verify_webhook.return_value = PaymentWebhookDTO(
        event_type="payment.authorized",
        status="authorized",
        provider_order_id="order_TEST123",
        provider_payment_id="pay_TEST123",
    )

    result = await service.process_event(b'{"event":"payment.authorized"}', "valid_signature")

    assert result is None
    mock_payment_service.confirm_payment.assert_not_called()


@pytest.mark.asyncio
async def test_process_event_captured_payment_success(mock_payment_service: MagicMock):
    service = WebhookService(mock_payment_service)
    mock_payment_service.provider.verify_webhook.return_value = PaymentWebhookDTO(
        event_type="payment.captured",
        status="captured",
        provider_order_id="order_TEST123",
        provider_payment_id="pay_TEST123",
    )
    expected_payment = Payment(status=PaymentStatus.PAID)
    mock_payment_service.confirm_payment.return_value = expected_payment

    result = await service.process_event(b'{"event":"payment.captured"}', "valid_signature")

    assert result == expected_payment
    mock_payment_service.confirm_payment.assert_called_once_with(
        provider_order_id="order_TEST123",
        provider_payment_id="pay_TEST123",
    )


@pytest.mark.asyncio
async def test_process_event_failed_payment_success(mock_payment_service: MagicMock):
    service = WebhookService(mock_payment_service)
    mock_payment_service.provider.verify_webhook.return_value = PaymentWebhookDTO(
        event_type="payment.failed",
        status="failed",
        provider_order_id="order_FAIL123",
    )
    expected_payment = Payment(status=PaymentStatus.FAILED)
    mock_payment_service.fail_payment.return_value = expected_payment

    result = await service.process_event(b'{"event":"payment.failed"}', "valid_signature")

    assert result == expected_payment
    mock_payment_service.fail_payment.assert_called_once_with(
        provider_order_id="order_FAIL123",
        reason="Webhook payment.failed event",
    )


@pytest.mark.asyncio
async def test_process_event_refund_processed_success(mock_payment_service: MagicMock):
    service = WebhookService(mock_payment_service)
    mock_payment_service.provider.verify_webhook.return_value = PaymentWebhookDTO(
        event_type="refund.processed",
        status="processed",
        provider_order_id="order_REF123",
        provider_payment_id="pay_REF123",
    )
    expected_payment = Payment(status=PaymentStatus.REFUNDED)
    mock_payment_service.process_refund_webhook.return_value = expected_payment

    result = await service.process_event(b'{"event":"refund.processed"}', "valid_signature")

    assert result == expected_payment
    mock_payment_service.process_refund_webhook.assert_called_once_with(
        provider_order_id="order_REF123",
        provider_payment_id="pay_REF123",
    )


@pytest.mark.asyncio
async def test_process_event_unhandled_type(mock_payment_service: MagicMock):
    service = WebhookService(mock_payment_service)
    mock_payment_service.provider.verify_webhook.return_value = PaymentWebhookDTO(
        event_type="unsupported.event",
        status="unknown",
        provider_order_id="order_UNH123",
    )

    result = await service.process_event(b'{"event":"unsupported.event"}', "valid_signature")

    assert result is None
    mock_payment_service.confirm_payment.assert_not_called()
    mock_payment_service.fail_payment.assert_not_called()


@pytest.mark.asyncio
async def test_process_event_missing_order_id_raises_error(mock_payment_service: MagicMock):
    service = WebhookService(mock_payment_service)
    mock_payment_service.provider.verify_webhook.return_value = PaymentWebhookDTO(
        event_type="payment.captured",
        status="captured",
        provider_order_id=None,
        provider_payment_id="pay_123",
    )

    with pytest.raises(PaymentWebhookError, match="missing order ID"):
        await service.process_event(b'{"event":"payment.captured"}', "valid_signature")


@pytest.mark.asyncio
async def test_zero_secret_logging_in_webhook_service(mock_payment_service: MagicMock, caplog: pytest.LogCaptureFixture):
    service = WebhookService(mock_payment_service)
    mock_payment_service.provider.verify_webhook.return_value = PaymentWebhookDTO(
        event_type="payment.captured",
        status="captured",
        provider_order_id="order_TEST123",
        provider_payment_id="pay_TEST123",
    )
    mock_payment_service.confirm_payment.return_value = Payment(status=PaymentStatus.PAID)

    with caplog.at_level(logging.INFO):
        await service.process_event(b'{"secret":"super_secret_payload"}', "hmac_secret_signature_999")

    log_text = caplog.text
    assert "event=payment.captured" in log_text
    assert "order_id=order_TEST123" in log_text
    assert "super_secret_payload" not in log_text
    assert "hmac_secret_signature_999" not in log_text

