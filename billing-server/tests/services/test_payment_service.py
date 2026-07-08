"""
test_payment_service.py — Comprehensive unit tests for Phase 2.3 Payment Domain & Gateway Integration.
Tests Razorpay provider HMAC verification, retries, timeouts, and PaymentService orchestration,
webhook idempotency, row-level locking, and SubscriptionService entitlement activation without internet.
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from app.config import Settings
from app.models import (
    Account,
    Payment,
    PaymentStatus,
    Subscription,
    SubscriptionLifecycleStatus,
)
from app.repositories import AccountRepository, SubscriptionRepository
from app.services import (
    PaymentOrderDTO,
    PaymentProviderError,
    PaymentRefundDTO,
    PaymentRefundError,
    PaymentService,
    PaymentTimeoutError,
    PaymentVerificationDTO,
    PaymentVerificationError,
    PaymentWebhookDTO,
    RazorpayProvider,
)
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        razorpay_key_id="test_key_id",
        razorpay_key_secret="test_key_secret",
        razorpay_webhook_secret="test_webhook_secret",
        razorpay_timeout_seconds=5.0,
        razorpay_max_retries=2,
    )


@pytest.fixture
async def test_account(db_session: AsyncSession) -> Account:
    repo = AccountRepository(db_session)
    return await repo.create(
        account_id="PAY-TEST-001",
        master_token_hash="payhash" * 8,
        plan_id="pro",
    )


@pytest.fixture
def mock_provider() -> AsyncMock:
    provider = AsyncMock()
    provider.create_order.return_value = PaymentOrderDTO(
        provider_order_id="order_test_123456",
        amount_minor_units=99900,
        currency="INR",
    )
    provider.verify_webhook.return_value = PaymentWebhookDTO(
        event_type="payment.captured",
        status="captured",
        provider_order_id="order_test_123456",
        provider_payment_id="pay_test_789012",
        amount_minor_units=99900,
        currency="INR",
        signature="mock_sig",
    )
    provider.fetch_payment.return_value = PaymentVerificationDTO(
        is_valid=True,
        provider_order_id="order_test_123456",
        provider_payment_id="pay_test_789012",
        status="captured",
        amount_minor_units=99900,
        currency="INR",
    )
    provider.refund_payment.return_value = PaymentRefundDTO(
        provider_refund_id="rfnd_test_345678",
        provider_payment_id="pay_test_789012",
        amount_minor_units=99900,
        status="processed",
    )
    return provider


@pytest.fixture
def service(db_session: AsyncSession, mock_provider: AsyncMock) -> PaymentService:
    return PaymentService(db_session, mock_provider)


# ── 1. Razorpay Provider Tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_razorpay_create_order_success(test_settings: Settings):
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "order_EKwxwAgItmmXdp",
        "amount": 50000,
        "currency": "INR",
        "status": "created",
    }
    mock_client.request.return_value = mock_response

    provider = RazorpayProvider(settings=test_settings, client=mock_client)
    dto = await provider.create_order(50000, "INR", "rcpt_test")

    assert dto.provider_order_id == "order_EKwxwAgItmmXdp"
    assert dto.amount_minor_units == 50000
    assert dto.currency == "INR"


@pytest.mark.asyncio
async def test_razorpay_verify_webhook_valid_hmac(test_settings: Settings):
    provider = RazorpayProvider(settings=test_settings)
    payload_dict = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_valid_123",
                    "order_id": "order_valid_456",
                    "status": "captured",
                    "amount": 50000,
                    "currency": "INR",
                }
            }
        },
    }
    raw_payload = json.dumps(payload_dict)
    valid_sig = hmac.new(
        test_settings.razorpay_webhook_secret.encode("utf-8"),
        raw_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    dto = await provider.verify_webhook(raw_payload, valid_sig)
    assert dto.event_type == "payment.captured"
    assert dto.provider_payment_id == "pay_valid_123"
    assert dto.provider_order_id == "order_valid_456"
    assert dto.amount_minor_units == 50000


@pytest.mark.asyncio
async def test_razorpay_verify_webhook_invalid_hmac(test_settings: Settings):
    provider = RazorpayProvider(settings=test_settings)
    with pytest.raises(PaymentVerificationError):
        await provider.verify_webhook(
            '{"event": "payment.captured"}', "invalid_signature_hex"
        )


@pytest.mark.asyncio
async def test_razorpay_fetch_payment_rejects_refunded(test_settings: Settings):
    from unittest.mock import MagicMock
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "pay_test_789",
        "order_id": "order_test_456",
        "status": "captured",
        "amount": 49900,
        "currency": "INR",
        "amount_refunded": 49900
    }
    mock_client.request.return_value = mock_response
    
    provider = RazorpayProvider(settings=test_settings, client=mock_client)
    dto = await provider.fetch_payment("pay_test_789")
    
    assert dto.is_valid is False
    assert dto.amount_refunded_minor_units == 49900
    assert dto.status == "captured"


@pytest.mark.asyncio
async def test_razorpay_timeout_and_retries(test_settings: Settings):
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.request.side_effect = httpx.TimeoutException("Connection timed out")

    provider = RazorpayProvider(settings=test_settings, client=mock_client)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(PaymentTimeoutError):
            await provider.create_order(1000, "INR", "rcpt")

    assert mock_client.request.call_count == 2


# ── 2. PaymentService Orchestration & Idempotency ───────────────────────────


@pytest.mark.asyncio
async def test_create_payment_success_and_idempotency(
    service: PaymentService, test_account: Account, mock_provider: AsyncMock
):
    key = f"idem_{uuid.uuid4().hex}"
    payment1 = await service.create_payment(
        test_account.id, 99900, "INR", key, plan_id="pro"
    )

    assert payment1.account_id == test_account.id
    assert payment1.status == PaymentStatus.CREATED
    assert payment1.provider_order_id == "order_test_123456"
    assert mock_provider.create_order.call_count == 1

    # Second call with same idempotency key returns existing payment without creating order again
    payment2 = await service.create_payment(
        test_account.id, 99900, "INR", key, plan_id="pro"
    )
    assert payment2.id == payment1.id
    assert mock_provider.create_order.call_count == 1


@pytest.mark.asyncio
async def test_confirm_payment_activates_new_subscription(
    service: PaymentService, test_account: Account, db_session: AsyncSession
):
    key = f"idem_{uuid.uuid4().hex}"
    payment = await service.create_payment(
        test_account.id, 99900, "INR", key, plan_id="pro"
    )
    assert payment.subscription_id is None

    confirmed = await service.confirm_payment(
        provider_order_id="order_test_123456",
        provider_payment_id="pay_test_789012",
        plan_id="pro",
    )
    assert confirmed.status == PaymentStatus.PAID
    assert confirmed.paid_at is not None
    assert confirmed.subscription_id is not None

    # Verify subscription created and active
    sub_repo = SubscriptionRepository(db_session)
    sub = await sub_repo.get_by_id(confirmed.subscription_id)
    assert sub is not None
    assert sub.account_id == test_account.id
    assert sub.status == SubscriptionLifecycleStatus.ACTIVE
    assert sub.plan_id == "pro"


@pytest.mark.asyncio
async def test_confirm_payment_rejects_captured_amount_mismatch(
    service: PaymentService,
    test_account: Account,
    mock_provider: AsyncMock,
    db_session: AsyncSession,
):
    """
    Regression test for Finding C-1 (payment tampering) defense-in-depth check.

    Simulates a webhook/confirmation flow where the amount actually captured at the gateway
    (as fetched live via provider.fetch_payment) is LOWER than the amount the order was
    originally created for. confirm_payment must reject this with PaymentVerificationError
    and must NOT mark the payment as PAID or activate/create any subscription.
    """
    key = f"idem_{uuid.uuid4().hex}"
    payment = await service.create_payment(
        test_account.id, 99900, "INR", key, plan_id="pro"
    )
    assert payment.subscription_id is None

    # Attacker/gateway anomaly: only 100 minor units were actually captured, not the 99900
    # the order was created for.
    mock_provider.fetch_payment.return_value = PaymentVerificationDTO(
        is_valid=True,
        provider_order_id="order_test_123456",
        provider_payment_id="pay_test_789012",
        status="captured",
        amount_minor_units=100,
        currency="INR",
    )

    with pytest.raises(PaymentVerificationError):
        await service.confirm_payment(
            provider_order_id="order_test_123456",
            provider_payment_id="pay_test_789012",
            plan_id="pro",
        )

    await db_session.refresh(payment)
    assert payment.status == PaymentStatus.CREATED
    assert payment.subscription_id is None
    assert payment.paid_at is None


@pytest.mark.asyncio
async def test_confirm_payment_rejects_refunded_payment(
    service: PaymentService,
    test_account: Account,
    mock_provider: AsyncMock,
    db_session: AsyncSession,
):
    key = f"idem_{uuid.uuid4().hex}"
    payment = await service.create_payment(
        test_account.id, 99900, "INR", key, plan_id="pro"
    )
    payment.status = PaymentStatus.REFUNDED
    await service.payment_repo.update(payment, commit=True)
    
    # Simulate stale webhook where provider hasn't been told about the refund yet
    mock_provider.fetch_payment.return_value = PaymentVerificationDTO(
        is_valid=True,
        provider_order_id="order_test_123456",
        provider_payment_id="pay_test_789012",
        status="captured",
        amount_minor_units=99900,
        currency="INR",
        amount_refunded_minor_units=0
    )

    with pytest.raises(PaymentVerificationError):
        await service.confirm_payment(
            provider_order_id="order_test_123456",
            provider_payment_id="pay_test_789012",
            plan_id="pro",
        )

    await db_session.refresh(payment)
    assert payment.status == PaymentStatus.REFUNDED
    assert payment.subscription_id is None


@pytest.mark.asyncio
async def test_confirm_payment_renews_existing_subscription(
    service: PaymentService, test_account: Account, db_session: AsyncSession
):
    sub_repo = SubscriptionRepository(db_session)
    now = datetime.now(timezone.utc)
    old_expires = now + timedelta(days=5)
    existing_sub = await sub_repo.create(
        account_id=test_account.id,
        plan_id="pro",
        status=SubscriptionLifecycleStatus.ACTIVE,
        starts_at=now - timedelta(days=25),
        expires_at=old_expires,
    )

    key = f"idem_{uuid.uuid4().hex}"
    await service.create_payment(test_account.id, 99900, "INR", key, plan_id="pro")

    confirmed = await service.confirm_payment(
        provider_order_id="order_test_123456",
        provider_payment_id="pay_test_789012",
        plan_id="pro",
    )
    assert confirmed.subscription_id == existing_sub.id

    await db_session.refresh(existing_sub)
    assert existing_sub.expires_at > old_expires


@pytest.mark.asyncio
async def test_confirm_payment_idempotency_10_webhooks(
    service: PaymentService, test_account: Account, mock_provider: AsyncMock
):
    key = f"idem_{uuid.uuid4().hex}"
    await service.create_payment(test_account.id, 99900, "INR", key, plan_id="pro")

    # Simulate delivering the same webhook / confirming payment 10 times
    first_confirm = await service.confirm_payment(
        "order_test_123456", "pay_test_789012"
    )
    sub_id = first_confirm.subscription_id

    for _ in range(9):
        res = await service.confirm_payment("order_test_123456", "pay_test_789012")
        assert res.id == first_confirm.id
        assert res.status == PaymentStatus.PAID
        assert res.subscription_id == sub_id


@pytest.mark.asyncio
async def test_concurrency_row_locking(service: PaymentService, test_account: Account):
    key = f"idem_{uuid.uuid4().hex}"
    await service.create_payment(test_account.id, 99900, "INR", key, plan_id="pro")

    with patch.object(
        service.payment_repo,
        "get_by_provider_order_id",
        wraps=service.payment_repo.get_by_provider_order_id,
    ) as mock_get:
        await service.confirm_payment("order_test_123456", "pay_test_789012")
        mock_get.assert_called_with("order_test_123456", for_update=True)


@pytest.mark.asyncio
async def test_fail_and_refund_payment(
    service: PaymentService, test_account: Account, mock_provider: AsyncMock
):
    key1 = f"idem_{uuid.uuid4().hex}"
    await service.create_payment(test_account.id, 99900, "INR", key1, plan_id="pro")
    failed = await service.fail_payment("order_test_123456", reason="Card declined")
    assert failed.status == PaymentStatus.FAILED

    # New order for refund test
    mock_provider.create_order.return_value = PaymentOrderDTO(
        "order_refund_999", 99900, "INR"
    )
    key2 = f"idem_{uuid.uuid4().hex}"
    payment = await service.create_payment(
        test_account.id, 99900, "INR", key2, plan_id="pro"
    )
    await service.confirm_payment("order_refund_999", "pay_refund_888")

    refunded = await service.refund_payment(payment.id, amount_minor_units=99900)
    assert refunded.status == PaymentStatus.REFUNDED
    mock_provider.refund_payment.assert_called_once_with(
        provider_payment_id="pay_refund_888",
        amount_minor_units=99900,
        notes=None,
    )
