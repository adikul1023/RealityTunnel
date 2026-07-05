import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from app.database import get_db
from app.dependencies import get_marzban_provider, get_razorpay_provider
from app.main import app
from app.models import (
    Account,
    PaymentProviderType,
    PaymentStatus,
    ProvisioningState,
    SubscriptionLifecycleStatus,
)
from app.repositories import (
    AccountRepository,
    PaymentRepository,
    ProvisioningRepository,
    SubscriptionRepository,
)
from app.services import (
    PaymentOrderDTO,
    PaymentTimeoutError,
    PaymentVerificationDTO,
    PaymentVerificationError,
    PaymentWebhookDTO,
    ProvisionedUserDTO,
    ProvisioningTimeoutError,
)
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_razorpay() -> AsyncMock:
    provider = AsyncMock()
    provider.create_order.return_value = PaymentOrderDTO(
        provider_order_id="order_webhook_int_1",
        amount_minor_units=99900,
        currency="INR",
    )
    provider.verify_webhook.return_value = PaymentWebhookDTO(
        event_type="payment.captured",
        status="captured",
        provider_order_id="order_webhook_int_1",
        provider_payment_id="pay_webhook_int_1",
        amount_minor_units=99900,
        currency="INR",
    )
    provider.fetch_payment.return_value = PaymentVerificationDTO(
        is_valid=True,
        provider_order_id="order_webhook_int_1",
        provider_payment_id="pay_webhook_int_1",
        status="captured",
        amount_minor_units=99900,
        currency="INR",
    )
    return provider


@pytest.fixture
def mock_marzban() -> AsyncMock:
    provider = AsyncMock()
    user_dto = ProvisionedUserDTO(
        remote_user_id="user_webhook_int_1",
        status="active",
        data_limit=107374182400,
        expire_at=1900000000,
        links=[
            "vless://test-uuid@vpn.realitytunnel.com:443?type=tcp&security=reality&pbk=pub&sni=sni&sid=id#tag"
        ],
    )
    provider.create_user.return_value = user_dto
    provider.get_user.return_value = user_dto
    provider.update_user.return_value = user_dto
    provider.delete_user.return_value = None
    return provider


@pytest_asyncio.fixture(scope="function")
async def client(
    db_session: AsyncSession,
    mock_razorpay: AsyncMock,
    mock_marzban: AsyncMock,
) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_razorpay_provider] = lambda: mock_razorpay
    app.dependency_overrides[get_marzban_provider] = lambda: mock_marzban

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def setup_account(db_session: AsyncSession) -> Account:
    repo = AccountRepository(db_session)
    return await repo.create(
        account_id="WEBHOOK-ACC-1",
        master_token_hash="hash" * 8,
        plan_id="pro",
    )


@pytest.mark.asyncio
async def test_webhook_missing_signature_returns_400(client: AsyncClient):
    resp = await client.post(
        "/api/webhooks/razorpay", content=b'{"event":"payment.captured"}'
    )
    assert resp.status_code == 400
    assert "Missing X-Razorpay-Signature" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_webhook_invalid_signature_returns_400(
    client: AsyncClient, mock_razorpay: AsyncMock
):
    mock_razorpay.verify_webhook.side_effect = PaymentVerificationError(
        "Invalid HMAC signature"
    )
    resp = await client.post(
        "/api/webhooks/razorpay",
        content=b'{"event":"payment.captured"}',
        headers={"X-Razorpay-Signature": "invalid_sig"},
    )
    assert resp.status_code == 400
    assert "Invalid HMAC signature" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_webhook_transient_error_returns_503(
    client: AsyncClient, mock_razorpay: AsyncMock
):
    mock_razorpay.verify_webhook.side_effect = PaymentTimeoutError("Gateway timeout")
    resp = await client.post(
        "/api/webhooks/razorpay",
        content=b'{"event":"payment.captured"}',
        headers={"X-Razorpay-Signature": "valid_sig"},
    )
    assert resp.status_code == 503
    assert "temporarily unavailable" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_webhook_success_creates_all_resources(
    client: AsyncClient,
    db_session: AsyncSession,
    setup_account: Account,
):
    # 1. Create initial PENDING payment order directly via repo
    pay_repo = PaymentRepository(db_session)
    await pay_repo.create(
        account_id=setup_account.id,
        subscription_id=None,
        provider=PaymentProviderType.RAZORPAY,
        provider_order_id="order_webhook_int_1",
        amount_minor_units=99900,
        currency="INR",
        status=PaymentStatus.CREATED,
        idempotency_key="idem_webhook_int_1",
    )
    await db_session.commit()

    # 2. Post webhook
    resp = await client.post(
        "/api/webhooks/razorpay",
        content=b'{"event":"payment.captured"}',
        headers={"X-Razorpay-Signature": "valid_sig"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

    # 3. Verify Payment
    payment = await pay_repo.get_by_provider_order_id("order_webhook_int_1")
    assert payment.status == PaymentStatus.PAID
    assert payment.subscription_id is not None

    # 4. Verify Subscription
    sub_repo = SubscriptionRepository(db_session)
    sub = await sub_repo.get_by_id(payment.subscription_id)
    assert sub.status == SubscriptionLifecycleStatus.ACTIVE
    assert sub.plan_id == "pro"

    # 5. Verify Provisioning
    prov_repo = ProvisioningRepository(db_session)
    prov = await prov_repo.get_by_account_id(setup_account.id)
    assert prov.provisioning_state == ProvisioningState.ACTIVE


@pytest.mark.asyncio
async def test_webhook_idempotency_10x_loop(
    client: AsyncClient,
    db_session: AsyncSession,
    setup_account: Account,
):
    pay_repo = PaymentRepository(db_session)
    await pay_repo.create(
        account_id=setup_account.id,
        subscription_id=None,
        provider=PaymentProviderType.RAZORPAY,
        provider_order_id="order_webhook_int_1",
        amount_minor_units=99900,
        currency="INR",
        status=PaymentStatus.CREATED,
        idempotency_key="idem_webhook_int_10x",
    )
    await db_session.commit()

    # Send exact same webhook 10 times in a loop
    for i in range(10):
        resp = await client.post(
            "/api/webhooks/razorpay",
            content=b'{"event":"payment.captured"}',
            headers={"X-Razorpay-Signature": "valid_sig"},
        )
        assert resp.status_code == 200, f"Failed on iteration {i}"
        assert resp.json() == {"status": "ok"}

    # Verify database state has exactly 1 subscription and 1 payment
    sub_repo = SubscriptionRepository(db_session)
    subs = await sub_repo.get_by_account_id(setup_account.id)
    assert len(subs) == 1
    assert subs[0].status == SubscriptionLifecycleStatus.ACTIVE

    payment = await pay_repo.get_by_provider_order_id("order_webhook_int_1")
    assert payment.status == PaymentStatus.PAID
