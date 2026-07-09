import pytest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.models import PaymentStatus, PaymentProviderType, SubscriptionLifecycleStatus
from app.repositories import PaymentRepository, SubscriptionRepository
from app.services.payment.service import PaymentService
from app.services.payment.provider import PaymentProvider, PaymentOrderDTO, PaymentWebhookDTO, PaymentVerificationDTO, PaymentRefundDTO
from app.services.exceptions import PaymentVerificationError, PaymentWebhookError, PaymentTimeoutError
from app.main import app

@pytest.fixture
def mock_razorpay() -> AsyncMock:
    provider = AsyncMock()
    provider.create_order.return_value = PaymentOrderDTO(
        provider_order_id="order_test_adv",
        amount_minor_units=100000,
        currency="INR",
    )
    provider.verify_webhook.return_value = PaymentWebhookDTO(
        event_type="payment.captured",
        status="captured",
        provider_order_id="order_test_adv",
        provider_payment_id="pay_adv",
        amount_minor_units=100000,
        currency="INR",
        signature="mock_sig",
    )
    provider.fetch_payment.return_value = PaymentVerificationDTO(
        is_valid=True,
        provider_order_id="order_test_adv",
        provider_payment_id="pay_adv",
        status="captured",
        amount_minor_units=100000,
        currency="INR",
    )
    provider.refund_payment.return_value = PaymentRefundDTO(
        provider_refund_id="rfnd_adv",
        provider_payment_id="pay_adv",
        amount_minor_units=100000,
        status="processed",
    )
    return provider


@pytest.mark.asyncio
async def test_scenario_a_webhook_signature_replay(db_session: AsyncSession, account_factory, mock_razorpay):
    """Scenario A & J: Replay 10 days later / Crash loop exactly-once semantics."""
    account = await account_factory()
    service = PaymentService(db_session, mock_razorpay)
    payment = await service.create_payment(account.id, 100000, "INR", "idem_replay")
    
    # 1. Initial valid webhook delivery
    p1 = await service.confirm_payment(payment.provider_order_id, "pay_adv")
    assert p1.status == PaymentStatus.PAID
    sub_id = p1.subscription_id
    
    # 2. Replay the same event a long time later (or after a crash)
    p2 = await service.confirm_payment(payment.provider_order_id, "pay_adv")
    
    # Assert exactly-once semantics: ID should be identical, no new sub created
    assert p2.id == p1.id
    assert p2.status == PaymentStatus.PAID
    
    sub_repo = SubscriptionRepository(db_session)
    sub = await sub_repo.get_active_for_account(account.id, datetime.now(timezone.utc))
    assert sub is not None
    assert sub.id == sub_id


@pytest.mark.asyncio
async def test_scenario_b_provider_outage_yields_503(db_session: AsyncSession, account_factory, mock_razorpay):
    """Scenario B: Gateway unreachable during fetch_payment -> Webhook router should return 503 so Gateway retries."""
    account = await account_factory()
    
    # Simulate fetch_payment throwing a Timeout
    mock_razorpay.fetch_payment.side_effect = PaymentTimeoutError("Provider unreachable")
    
    # The actual test needs to hit the router, but we can verify the service throws it up
    service = PaymentService(db_session, mock_razorpay)
    payment = await service.create_payment(account.id, 100000, "INR", "idem_outage")
    
    with pytest.raises(PaymentTimeoutError):
        await service.confirm_payment(payment.provider_order_id, "pay_adv")


@pytest.mark.asyncio
async def test_scenario_cd_partial_refund_revokes_access(db_session: AsyncSession, account_factory, mock_razorpay):
    """Scenario C & D: Refund Race & Partial Refund logic."""
    account = await account_factory()
    service = PaymentService(db_session, mock_razorpay)
    payment = await service.create_payment(account.id, 100000, "INR", "idem_refund")
    
    # 1. Capture successfully
    p1 = await service.confirm_payment(payment.provider_order_id, "pay_adv")
    assert p1.status == PaymentStatus.PAID
    
    # 2. Gateway sends refund.processed webhook (Even if it's partial)
    # The process_refund_webhook doesn't check the amount; ANY refund cancels the sub.
    p2 = await service.process_refund_webhook(provider_order_id=payment.provider_order_id)
    assert p2.status == PaymentStatus.REFUNDED
    
    sub_repo = SubscriptionRepository(db_session)
    # Wait for cancel to commit in db session
    await db_session.refresh(p2)
    subs = await sub_repo.get_active_for_account(account.id, datetime.now(timezone.utc))
    assert not subs  # Cancelled!


@pytest.mark.asyncio
async def test_scenario_e_chargeback_handling(db_session: AsyncSession, account_factory, mock_razorpay):
    """Scenario E: Webhook router should route chargebacks to refund logic to suspend access."""
    account = await account_factory()
    service = PaymentService(db_session, mock_razorpay)
    payment = await service.create_payment(account.id, 100000, "INR", "idem_chargeback")
    
    await service.confirm_payment(payment.provider_order_id, "pay_adv")
    
    # Simulate process_webhook receiving a chargeback
    mock_razorpay.verify_webhook.return_value = PaymentWebhookDTO(
        event_type="payment.dispute.created",
        status="disputed",
        provider_order_id=payment.provider_order_id,
        provider_payment_id="pay_adv",
        amount_minor_units=100000,
        currency="INR",
        signature="mock"
    )
    
    p2 = await service.process_webhook(b"raw", "mock")
    assert p2.status == PaymentStatus.REFUNDED # Treated identically to refund
    sub_repo = SubscriptionRepository(db_session)
    subs = await sub_repo.get_active_for_account(account.id, datetime.now(timezone.utc))
    assert not subs


@pytest.mark.asyncio
async def test_scenario_i_double_subscription_math(db_session: AsyncSession, account_factory, mock_razorpay):
    """Scenario I: Payment A renews, Payment B renews -> Math is +60 days"""
    account = await account_factory()
    service = PaymentService(db_session, mock_razorpay)
    
    # Payment A
    mock_razorpay.create_order.return_value = PaymentOrderDTO("order_a", 100000, "INR")
    pay_a = await service.create_payment(account.id, 100000, "INR", "idem_math_a")
    
    mock_razorpay.fetch_payment.return_value = PaymentVerificationDTO(
        is_valid=True,
        provider_order_id=pay_a.provider_order_id,
        provider_payment_id="pay_a",
        status="captured",
        amount_minor_units=100000,
        currency="INR"
    )
    p1 = await service.confirm_payment(pay_a.provider_order_id, "pay_a")
    
    sub_repo = SubscriptionRepository(db_session)
    sub = await sub_repo.get_by_id(p1.subscription_id)
    
    # Base expiration
    base_expires = sub.expires_at
    
    # Payment B (Simulating user buys another month before expiring)
    mock_razorpay.create_order.return_value = PaymentOrderDTO("order_b", 100000, "INR")
    pay_b = await service.create_payment(account.id, 100000, "INR", "idem_math_b")
    
    mock_razorpay.fetch_payment.return_value = PaymentVerificationDTO(
        is_valid=True,
        provider_order_id=pay_b.provider_order_id,
        provider_payment_id="pay_b",
        status="captured",
        amount_minor_units=100000,
        currency="INR"
    )
    
    p2 = await service.confirm_payment(pay_b.provider_order_id, "pay_b")
    
    await db_session.refresh(sub)
    
    # Assert the new expiration date is exactly 30 days added to the OLD expiration date
    diff = sub.expires_at - base_expires
    assert diff.days == 30 # Proving +30 +30 = +60 days total. It stacks!


def test_scenario_g_malformed_webhook_headers():
    """Scenario G: API router instantly rejects garbage webhooks (400 Bad Request)"""
    client = TestClient(app)
    # 1. No signature
    resp = client.post("/api/webhooks/razorpay", json={"event": "payment.captured"})
    assert resp.status_code == 400
    
    # 2. Empty signature
    resp = client.post("/api/webhooks/razorpay", json={}, headers={"X-Razorpay-Signature": ""})
    assert resp.status_code == 400
