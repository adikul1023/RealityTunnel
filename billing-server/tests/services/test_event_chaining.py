from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.models import (
    Account,
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
    CredentialService,
    PaymentOrderDTO,
    PaymentRefundDTO,
    PaymentService,
    PaymentVerificationDTO,
    PaymentWebhookDTO,
    ProvisionedUserDTO,
    ProvisioningService,
    SubscriptionService,
    WebhookService,
)
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def setup_chain_account(db_session: AsyncSession) -> Account:
    repo = AccountRepository(db_session)
    return await repo.create(
        account_id="CHAIN-ACC-001",
        master_token_hash="hash" * 8,
        plan_id="standard",
    )


@pytest.fixture
def mock_marzban_provider() -> AsyncMock:
    provider = AsyncMock()
    user_dto = ProvisionedUserDTO(
        remote_user_id="user_chain_acc_001",
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


@pytest.fixture
def mock_razorpay_provider() -> AsyncMock:
    provider = AsyncMock()
    provider.create_order.return_value = PaymentOrderDTO(
        provider_order_id="order_chain_123",
        amount_minor_units=99900,
        currency="INR",
    )
    provider.verify_webhook.return_value = PaymentWebhookDTO(
        event_type="payment.captured",
        status="captured",
        provider_order_id="order_chain_123",
        provider_payment_id="pay_chain_789",
        amount_minor_units=99900,
        currency="INR",
    )
    provider.fetch_payment.return_value = PaymentVerificationDTO(
        is_valid=True,
        provider_order_id="order_chain_123",
        provider_payment_id="pay_chain_789",
        status="captured",
        amount_minor_units=99900,
        currency="INR",
    )
    provider.refund_payment.return_value = PaymentRefundDTO(
        provider_refund_id="rfnd_chain_345",
        provider_payment_id="pay_chain_789",
        amount_minor_units=99900,
        status="processed",
    )
    return provider


@pytest.fixture
def services_chain(
    db_session: AsyncSession,
    mock_marzban_provider: AsyncMock,
    mock_razorpay_provider: AsyncMock,
) -> tuple[
    WebhookService,
    PaymentService,
    SubscriptionService,
    ProvisioningService,
    CredentialService,
]:
    prov_svc = ProvisioningService(db_session, mock_marzban_provider)
    cred_svc = CredentialService(db_session, prov_svc)
    prov_svc.credential_service = cred_svc
    sub_svc = SubscriptionService(db_session, provisioning_service=prov_svc)
    pay_svc = PaymentService(
        db_session, mock_razorpay_provider, subscription_service=sub_svc
    )
    webhook_svc = WebhookService(pay_svc)
    return webhook_svc, pay_svc, sub_svc, prov_svc, cred_svc


@pytest.mark.asyncio
async def test_full_event_chain_payment_captured_activates_all(
    db_session: AsyncSession,
    setup_chain_account: Account,
    services_chain: tuple[
        WebhookService,
        PaymentService,
        SubscriptionService,
        ProvisioningService,
        CredentialService,
    ],
):
    webhook_svc, pay_svc, sub_svc, prov_svc, cred_svc = services_chain

    # 1. Create a pending payment order
    payment = await pay_svc.create_payment(
        account_id=setup_chain_account.id,
        amount_minor_units=99900,
        currency="INR",
        idempotency_key="idem_chain_1",
        plan_id="standard",
    )
    assert payment.status == PaymentStatus.CREATED

    # 2. Ingest payment.captured webhook
    payload = b'{"event":"payment.captured"}'
    processed_payment = await webhook_svc.process_event(payload, "valid_sig")

    assert processed_payment is not None
    assert processed_payment.status == PaymentStatus.PAID
    assert processed_payment.subscription_id is not None

    # 3. Verify Subscription state
    sub_repo = SubscriptionRepository(db_session)
    sub = await sub_repo.get_by_id(processed_payment.subscription_id)
    assert sub is not None
    assert sub.status == SubscriptionLifecycleStatus.ACTIVE
    assert sub.plan_id == "standard"

    # 4. Verify Provisioning profile state
    prov_repo = ProvisioningRepository(db_session)
    prov_profile = await prov_repo.get_by_account_id(setup_chain_account.id)
    assert prov_profile is not None
    assert prov_profile.provisioning_state == ProvisioningState.ACTIVE
    assert prov_profile.remote_user_id == "user_chain_acc_001"

    # 5. Verify CredentialService can retrieve active configuration
    creds = await cred_svc.get_credentials(setup_chain_account.id)
    assert creds["vless_uri"].startswith("vless://")
    assert creds["uuid"] == "test-uuid"


@pytest.mark.asyncio
async def test_full_event_chain_refund_terminates_all(
    db_session: AsyncSession,
    setup_chain_account: Account,
    services_chain: tuple[
        WebhookService,
        PaymentService,
        SubscriptionService,
        ProvisioningService,
        CredentialService,
    ],
    mock_razorpay_provider: AsyncMock,
):
    webhook_svc, pay_svc, sub_svc, prov_svc, cred_svc = services_chain

    # 1. Create and capture payment first
    await pay_svc.create_payment(
        account_id=setup_chain_account.id,
        amount_minor_units=99900,
        currency="INR",
        idempotency_key="idem_chain_2",
        plan_id="standard",
    )
    captured = await webhook_svc.process_event(
        b'{"event":"payment.captured"}', "valid_sig"
    )
    assert captured.status == PaymentStatus.PAID

    # 2. Setup mock for refund webhook
    mock_razorpay_provider.verify_webhook.return_value = PaymentWebhookDTO(
        event_type="refund.processed",
        status="processed",
        provider_order_id="order_chain_123",
        provider_payment_id="pay_chain_789",
    )

    # 3. Process refund webhook
    refunded_payment = await webhook_svc.process_event(
        b'{"event":"refund.processed"}', "valid_sig"
    )
    assert refunded_payment.status == PaymentStatus.REFUNDED

    # 4. Verify Subscription is CANCELLED
    sub_repo = SubscriptionRepository(db_session)
    sub = await sub_repo.get_by_id(refunded_payment.subscription_id)
    assert sub.status == SubscriptionLifecycleStatus.CANCELLED

    # 5. Verify Provisioning profile is SUSPENDED
    prov_repo = ProvisioningRepository(db_session)
    prov_profile = await prov_repo.get_by_account_id(setup_chain_account.id)
    assert prov_profile.provisioning_state == ProvisioningState.SUSPENDED
