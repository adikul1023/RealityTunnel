import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subscription, SubscriptionLifecycleStatus
from app.services.admin_billing_service import AdminBillingService
from app.services import SubscriptionService, PaymentService, ProvisioningService


def make_billing_service(db_session: AsyncSession) -> AdminBillingService:
    """Construct AdminBillingService with mocked sub-services."""
    mock_sub_service = AsyncMock(spec=SubscriptionService)
    mock_payment_service = AsyncMock(spec=PaymentService)
    mock_provisioning_service = AsyncMock(spec=ProvisioningService)

    service = AdminBillingService(
        session=db_session,
        subscription_service=mock_sub_service,
        payment_service=mock_payment_service,
        provisioning_service=mock_provisioning_service,
    )
    return service


def make_sub(sub_id: uuid.UUID, account_id: uuid.UUID, plan_id: str, status) -> MagicMock:
    """Build a mock Subscription without touching SQLAlchemy's constructor."""
    sub = MagicMock(spec=Subscription)
    sub.id = sub_id
    sub.account_id = account_id
    sub.plan_id = plan_id
    sub.status = status
    sub.auto_renew = True
    sub.revoked_by = None
    sub.revoke_reason = None
    sub.revoked_at = None
    sub.starts_at = None
    sub.expires_at = None
    sub.grace_expires_at = None
    sub.created_at = datetime.now(timezone.utc)
    sub.updated_at = datetime.now(timezone.utc)
    return sub


@pytest.mark.asyncio
async def test_revoke_subscription(db_session: AsyncSession):
    sub_id = uuid.uuid4()
    account_id = uuid.uuid4()
    admin_id = str(uuid.uuid4())

    sub = make_sub(sub_id, account_id, "standard", SubscriptionLifecycleStatus.ACTIVE)

    service = make_billing_service(db_session)
    service.subscription_repo.get_by_id = AsyncMock(return_value=sub)
    service.subscription_repo.update = AsyncMock(return_value=sub)

    await service.revoke_subscription(str(sub_id), admin_id, "Policy violation")

    assert sub.status == SubscriptionLifecycleStatus.REVOKED
    assert str(sub.revoked_by) == admin_id  # stored as UUID, compare via str()
    assert sub.revoke_reason == "Policy violation"
    assert sub.revoked_at is not None
    assert sub.auto_renew is False

    service.provisioning_service.terminate_subscription.assert_awaited_once_with(account_id)


@pytest.mark.asyncio
async def test_edit_plan_valid(db_session: AsyncSession):
    sub_id = uuid.uuid4()
    account_id = uuid.uuid4()

    sub = make_sub(sub_id, account_id, "free", SubscriptionLifecycleStatus.ACTIVE)

    service = make_billing_service(db_session)
    service.subscription_repo.get_by_id = AsyncMock(return_value=sub)
    service.subscription_repo.update = AsyncMock(return_value=sub)

    await service.edit_plan(str(sub_id), "standard")

    assert sub.plan_id == "standard"
    service.subscription_repo.update.assert_awaited_once_with(sub)


@pytest.mark.asyncio
async def test_edit_plan_invalid_raises(db_session: AsyncSession):
    sub_id = uuid.uuid4()
    account_id = uuid.uuid4()

    sub = make_sub(sub_id, account_id, "free", SubscriptionLifecycleStatus.ACTIVE)

    service = make_billing_service(db_session)
    service.subscription_repo.get_by_id = AsyncMock(return_value=sub)

    from app.services.exceptions import ServiceError
    with pytest.raises(ServiceError, match="Unknown subscription plan"):
        await service.edit_plan(str(sub_id), "hacker_plan_xxx")
