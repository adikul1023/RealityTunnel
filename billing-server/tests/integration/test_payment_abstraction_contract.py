import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from unittest.mock import AsyncMock

from app.models import PaymentStatus
from app.services.payment.service import PaymentService
from app.services.payment.provider import PaymentProvider, PaymentOrderDTO, PaymentWebhookDTO, PaymentVerificationDTO, PaymentRefundDTO
from app.repositories import SubscriptionRepository

class MockLemonSqueezyProvider(PaymentProvider):
    async def create_order(self, amount_minor_units: int, currency: str, receipt: str, notes: dict | None = None) -> PaymentOrderDTO:
        return PaymentOrderDTO(provider_order_id=f"ls_{receipt}", amount_minor_units=amount_minor_units, currency=currency)
        
    async def verify_webhook(self, payload: bytes | str, signature: str, secret: str | None = None) -> PaymentWebhookDTO:
        return PaymentWebhookDTO(
            event_type="payment.captured",
            status="paid",
            provider_order_id="ls_receipt1",
            provider_payment_id="ls_pay_1",
            amount_minor_units=1000,
            currency="USD",
        )
        
    async def fetch_payment(self, provider_payment_id: str) -> PaymentVerificationDTO:
        return PaymentVerificationDTO(
            is_valid=True,
            provider_order_id="ls_receipt1",
            provider_payment_id=provider_payment_id,
            status="paid",
            amount_minor_units=1000,
            currency="USD"
        )
        
    async def refund_payment(self, provider_payment_id: str, amount_minor_units: int | None = None, notes: dict | None = None) -> PaymentRefundDTO:
        return PaymentRefundDTO(provider_refund_id="ls_ref_1", provider_payment_id=provider_payment_id, amount_minor_units=amount_minor_units or 1000, status="refunded")

    async def health_check(self) -> bool:
        return True


class MockPaytmProvider(PaymentProvider):
    async def create_order(self, amount_minor_units: int, currency: str, receipt: str, notes: dict | None = None) -> PaymentOrderDTO:
        return PaymentOrderDTO(provider_order_id=f"ptm_{receipt}", amount_minor_units=amount_minor_units, currency=currency)
        
    async def verify_webhook(self, payload: bytes | str, signature: str, secret: str | None = None) -> PaymentWebhookDTO:
        return PaymentWebhookDTO(
            event_type="payment.captured",
            status="TXN_SUCCESS",
            provider_order_id="ptm_receipt1",
            provider_payment_id="ptm_pay_1",
            amount_minor_units=1000,
            currency="INR",
        )
        
    async def fetch_payment(self, provider_payment_id: str) -> PaymentVerificationDTO:
        return PaymentVerificationDTO(
            is_valid=True,
            provider_order_id="ptm_receipt1",
            provider_payment_id=provider_payment_id,
            status="TXN_SUCCESS",
            amount_minor_units=1000,
            currency="INR"
        )
        
    async def refund_payment(self, provider_payment_id: str, amount_minor_units: int | None = None, notes: dict | None = None) -> PaymentRefundDTO:
        return PaymentRefundDTO(provider_refund_id="ptm_ref_1", provider_payment_id=provider_payment_id, amount_minor_units=amount_minor_units or 1000, status="REFUND_SUCCESS")

    async def health_check(self) -> bool:
        return True


@pytest.fixture(params=[MockLemonSqueezyProvider(), MockPaytmProvider()])
def provider_adapter(request):
    return request.param

@pytest.mark.asyncio
async def test_provider_abstraction_contract(db_session: AsyncSession, account_factory, provider_adapter):
    """Payment-8: Run exactly the same contract tests against Lemon Squeezy adapter and Paytm adapter."""
    account = await account_factory()
    service = PaymentService(db_session, provider_adapter)
    
    # 1. Create order
    payment = await service.create_payment(account.id, 1000, "USD", "receipt1")
    assert payment.status == PaymentStatus.CREATED
    
    # 2. Confirm payment
    pay_id = "ls_pay_1" if isinstance(provider_adapter, MockLemonSqueezyProvider) else "ptm_pay_1"
    
    confirmed = await service.confirm_payment(payment.provider_order_id, pay_id)
    assert confirmed.status == PaymentStatus.PAID
    
    # Check subscription
    sub_repo = SubscriptionRepository(db_session)
    subs = await sub_repo.get_by_account_id(account.id)
    assert len(subs) == 1
    
    # 3. Refund payment
    refunded = await service.refund_payment(confirmed.id)
    assert refunded.status == PaymentStatus.REFUNDED
