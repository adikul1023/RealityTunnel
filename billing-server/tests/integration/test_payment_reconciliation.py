"""
test_payment_reconciliation.py — Integration tests for the new Payment Reconciliation job (Job 9).
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock

from app.models import PaymentStatus, PaymentProviderType
from app.repositories import PaymentRepository, SubscriptionRepository
from app.services.payment.provider import PaymentVerificationDTO
from app.services import LifecycleJobService, PaymentService, SubscriptionService, ProvisioningService

pytestmark = pytest.mark.asyncio


async def test_payment_reconciliation_lost_webhook_recovered(
    db_session,
    account_factory,
):
    """
    Simulate a lost webhook where the order is captured in Razorpay but PENDING in our DB.
    The reconciliation job should poll Razorpay and confirm the payment.
    """
    account = await account_factory()
    account_id = account.id
    provider_order_id = "order_lost_webhook_123"
    
    # 1. Create a payment from 2 hours ago (within the 30m - 48h window)
    payment_repo = PaymentRepository(db_session)
    payment = await payment_repo.create(
        account_id=account_id,
        subscription_id=None,
        provider=PaymentProviderType.RAZORPAY,
        provider_order_id=provider_order_id,
        amount_minor_units=100000,
        currency="INR",
        status=PaymentStatus.PENDING,
        idempotency_key="idem_lost_webhook_123",
    )
    
    # Backdate the payment
    payment.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
    await payment_repo.update(payment, commit=True)
    
    # 2. Mock providers and services
    from app.services.provisioning.provider import ProvisionedUserDTO
    razorpay_provider_mock = AsyncMock()
    marzban_provider_mock = AsyncMock()
    marzban_provider_mock.create_user = AsyncMock(return_value=ProvisionedUserDTO(
        remote_user_id="marzban_123",
        status="active",
        links=["http://vpn/link"],
    ))
    
    razorpay_provider_mock.fetch_order_payments = AsyncMock(return_value=[
        PaymentVerificationDTO(
            is_valid=True,
            provider_order_id=provider_order_id,
            provider_payment_id="pay_captured_123",
            status="captured",
            amount_minor_units=100000,
            currency="INR",
            amount_refunded_minor_units=0,
            raw_data={"status": "captured"}
        )
    ])
    
    razorpay_provider_mock.fetch_payment = AsyncMock(return_value=PaymentVerificationDTO(
        is_valid=True,
        provider_order_id=provider_order_id,
        provider_payment_id="pay_captured_123",
        status="captured",
        amount_minor_units=100000,
        currency="INR",
        amount_refunded_minor_units=0,
        raw_data={"status": "captured"}
    ))

    provisioning_service = ProvisioningService(db_session, marzban_provider_mock)
    subscription_service = SubscriptionService(db_session, provisioning_service)
    payment_service = PaymentService(db_session, razorpay_provider_mock, subscription_service)

    # 3. Run the reconciliation job
    job_service = LifecycleJobService(
        db_session,
        subscription_service,
        provisioning_service,
        payment_service,
    )
    
    count = await job_service.run_payment_reconciliation_job()
    assert count == 1, "Should reconcile exactly 1 payment"
    
    # 4. Assert payment is now PAID and subscription is created
    updated_payment = await payment_repo.get_by_id(payment.id)
    assert updated_payment.status == PaymentStatus.PAID
    assert updated_payment.provider_payment_id == "pay_captured_123"
    
    sub_repo = SubscriptionRepository(db_session)
    active_subs = await sub_repo.get_by_account_id(account_id)
    assert len(active_subs) == 1
    assert active_subs[0].id == updated_payment.subscription_id


async def test_payment_reconciliation_ignores_recent_payments(
    db_session,
    account_factory,
):
    """
    Ensure the job does not interfere with payments created in the last 30 minutes.
    """
    account = await account_factory()
    account_id = account.id
    provider_order_id = "order_recent_123"
    
    payment_repo = PaymentRepository(db_session)
    payment = await payment_repo.create(
        account_id=account_id,
        subscription_id=None,
        provider=PaymentProviderType.RAZORPAY,
        provider_order_id=provider_order_id,
        amount_minor_units=100000,
        currency="INR",
        status=PaymentStatus.PENDING,
        idempotency_key="idem_recent_123",
    )
    
    # Created exactly now (within 30m window)
    
    razorpay_provider_mock = AsyncMock()
    razorpay_provider_mock.fetch_order_payments = AsyncMock(return_value=[])
    marzban_provider_mock = AsyncMock()
    
    provisioning_service = ProvisioningService(db_session, marzban_provider_mock)
    subscription_service = SubscriptionService(db_session, provisioning_service)
    payment_service = PaymentService(db_session, razorpay_provider_mock, subscription_service)

    job_service = LifecycleJobService(
        db_session,
        subscription_service,
        provisioning_service,
        payment_service,
    )
    
    count = await job_service.run_payment_reconciliation_job()
    assert count == 0, "Should ignore recent payments"
    assert razorpay_provider_mock.fetch_order_payments.call_count == 0
