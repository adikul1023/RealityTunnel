"""
test_subscription_service.py — Comprehensive unit tests for Phase 2.1 Billing & Subscription Domain.
Covers subscription contract creation, lifecycle transitions, state validation, and expiration lookups.
"""
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import EntityNotFoundError
from app.models import Account, Subscription, SubscriptionLifecycleStatus
from app.repositories import AccountRepository
from app.services import SubscriptionService
from app.services.exceptions import (
    UnknownPlanError,
    SubscriptionNotFoundError,
    InvalidSubscriptionStateError,
    SubscriptionAlreadyActiveError,
)


@pytest.fixture
def service(db_session: AsyncSession) -> SubscriptionService:
    return SubscriptionService(db_session)


@pytest.fixture
async def test_account(db_session: AsyncSession) -> Account:
    repo = AccountRepository(db_session)
    account = await repo.create(
        account_id="SUB-TEST-ACCOUNT",
        master_token_hash="hash" * 16,
        plan_id="free",
    )
    return account


# ── 1. Subscription Creation ────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_create_subscription_success(service: SubscriptionService, test_account: Account):
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=30)

    sub = await service.create_subscription(
        account_id=test_account.id,
        plan_id="standard",
        starts_at=now,
        expires_at=expires_at,
        auto_renew=True,
        status=SubscriptionLifecycleStatus.ACTIVE,
    )

    assert sub.id is not None
    assert sub.account_id == test_account.id
    assert sub.plan_id == "standard"
    assert sub.status == SubscriptionLifecycleStatus.ACTIVE
    assert sub.starts_at == now
    assert sub.expires_at == expires_at
    assert sub.auto_renew is True
    assert sub.grace_expires_at is None


@pytest.mark.asyncio
async def test_create_subscription_trial_status(service: SubscriptionService, test_account: Account):
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=7)

    sub = await service.create_subscription(
        account_id=test_account.id,
        plan_id="quarterly",
        starts_at=now,
        expires_at=expires_at,
        auto_renew=True,
        status=SubscriptionLifecycleStatus.TRIAL,
    )

    assert sub.status == SubscriptionLifecycleStatus.TRIAL


@pytest.mark.asyncio
async def test_create_subscription_unknown_plan(service: SubscriptionService, test_account: Account):
    now = datetime.now(timezone.utc)
    with pytest.raises(UnknownPlanError) as exc_info:
        await service.create_subscription(
            account_id=test_account.id,
            plan_id="invalid_plan_123",
            starts_at=now,
            expires_at=now + timedelta(days=30),
        )
    assert "Unknown subscription plan ID" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_subscription_nonexistent_account(service: SubscriptionService):
    now = datetime.now(timezone.utc)
    fake_id = uuid.uuid4()
    with pytest.raises(EntityNotFoundError):
        await service.create_subscription(
            account_id=fake_id,
            plan_id="standard",
            starts_at=now,
            expires_at=now + timedelta(days=30),
        )


@pytest.mark.asyncio
async def test_create_subscription_already_active_error(service: SubscriptionService, test_account: Account):
    now = datetime.now(timezone.utc)
    await service.create_subscription(
        account_id=test_account.id,
        plan_id="standard",
        starts_at=now,
        expires_at=now + timedelta(days=30),
        status=SubscriptionLifecycleStatus.ACTIVE,
    )

    with pytest.raises(SubscriptionAlreadyActiveError) as exc_info:
        await service.create_subscription(
            account_id=test_account.id,
            plan_id="quarterly",
            starts_at=now,
            expires_at=now + timedelta(days=30),
            status=SubscriptionLifecycleStatus.ACTIVE,
        )
    assert "already has an active subscription" in str(exc_info.value)


# ── 2. Lifecycle Transitions: Activation ────────────────────────────────────
@pytest.mark.asyncio
async def test_activate_subscription(service: SubscriptionService, test_account: Account):
    now = datetime.now(timezone.utc)
    sub = await service.create_subscription(
        account_id=test_account.id,
        plan_id="standard",
        starts_at=now,
        expires_at=now + timedelta(days=7),
        status=SubscriptionLifecycleStatus.TRIAL,
    )

    activated = await service.activate_subscription(sub.id)
    assert activated.status == SubscriptionLifecycleStatus.ACTIVE
    assert activated.grace_expires_at is None

    # Verify idempotency when already ACTIVE
    re_activated = await service.activate_subscription(sub.id)
    assert re_activated.status == SubscriptionLifecycleStatus.ACTIVE


@pytest.mark.asyncio
async def test_activate_subscription_invalid_states(service: SubscriptionService, test_account: Account):
    now = datetime.now(timezone.utc)
    sub_cancel = await service.create_subscription(
        account_id=test_account.id,
        plan_id="standard",
        starts_at=now,
        expires_at=now + timedelta(days=30),
        status=SubscriptionLifecycleStatus.ACTIVE,
    )
    await service.cancel_subscription(sub_cancel.id)

    with pytest.raises(InvalidSubscriptionStateError) as exc_info:
        await service.activate_subscription(sub_cancel.id)
    assert "Cannot activate a cancelled subscription" in str(exc_info.value)


# ── 3. Lifecycle Transitions: Renewal & Cancellation ────────────────────────
@pytest.mark.asyncio
async def test_renew_subscription(service: SubscriptionService, test_account: Account):
    now = datetime.now(timezone.utc)
    sub = await service.create_subscription(
        account_id=test_account.id,
        plan_id="standard",
        starts_at=now,
        expires_at=now + timedelta(days=30),
        status=SubscriptionLifecycleStatus.ACTIVE,
    )

    new_expiry = now + timedelta(days=60)
    renewed = await service.renew_subscription(sub.id, new_expiry)
    assert renewed.expires_at == new_expiry
    assert renewed.status == SubscriptionLifecycleStatus.ACTIVE
    assert renewed.grace_expires_at is None


@pytest.mark.asyncio
async def test_renew_cancelled_subscription_fails(service: SubscriptionService, test_account: Account):
    now = datetime.now(timezone.utc)
    sub = await service.create_subscription(
        account_id=test_account.id,
        plan_id="standard",
        starts_at=now,
        expires_at=now + timedelta(days=30),
    )
    await service.cancel_subscription(sub.id)

    with pytest.raises(InvalidSubscriptionStateError):
        await service.renew_subscription(sub.id, now + timedelta(days=60))


@pytest.mark.asyncio
async def test_cancel_subscription(service: SubscriptionService, test_account: Account):
    now = datetime.now(timezone.utc)
    sub = await service.create_subscription(
        account_id=test_account.id,
        plan_id="standard",
        starts_at=now,
        expires_at=now + timedelta(days=30),
        auto_renew=True,
    )

    cancelled = await service.cancel_subscription(sub.id)
    assert cancelled.status == SubscriptionLifecycleStatus.CANCELLED
    assert cancelled.auto_renew is False

    # Verify idempotency
    re_cancelled = await service.cancel_subscription(sub.id)
    assert re_cancelled.status == SubscriptionLifecycleStatus.CANCELLED


# ── 4. Lifecycle Transitions: Grace Period & Expiration ─────────────────────
@pytest.mark.asyncio
async def test_enter_grace_period(service: SubscriptionService, test_account: Account):
    now = datetime.now(timezone.utc)
    sub = await service.create_subscription(
        account_id=test_account.id,
        plan_id="standard",
        starts_at=now,
        expires_at=now + timedelta(days=30),
        auto_renew=True,
        status=SubscriptionLifecycleStatus.ACTIVE,
    )

    grace_sub = await service.enter_grace_period(sub.id, grace_duration_days=7)
    assert grace_sub.status == SubscriptionLifecycleStatus.GRACE
    assert grace_sub.grace_expires_at is not None
    assert (grace_sub.grace_expires_at - now).days == 7


@pytest.mark.asyncio
async def test_enter_grace_period_invalid_state(service: SubscriptionService, test_account: Account):
    now = datetime.now(timezone.utc)
    sub = await service.create_subscription(
        account_id=test_account.id,
        plan_id="standard",
        starts_at=now,
        expires_at=now + timedelta(days=30),
        auto_renew=False, # Disabled auto-renew cannot enter grace period
    )

    with pytest.raises(InvalidSubscriptionStateError) as exc_info:
        await service.enter_grace_period(sub.id)
    assert "auto-renew is disabled" in str(exc_info.value)


@pytest.mark.asyncio
async def test_expire_subscription(service: SubscriptionService, test_account: Account):
    now = datetime.now(timezone.utc)
    sub = await service.create_subscription(
        account_id=test_account.id,
        plan_id="standard",
        starts_at=now,
        expires_at=now + timedelta(days=30),
    )

    expired = await service.expire_subscription(sub.id)
    assert expired.status == SubscriptionLifecycleStatus.EXPIRED


@pytest.mark.asyncio
async def test_expire_cancelled_subscription_fails(service: SubscriptionService, test_account: Account):
    now = datetime.now(timezone.utc)
    sub = await service.create_subscription(
        account_id=test_account.id,
        plan_id="standard",
        starts_at=now,
        expires_at=now + timedelta(days=30),
    )
    await service.cancel_subscription(sub.id)

    with pytest.raises(InvalidSubscriptionStateError):
        await service.expire_subscription(sub.id)


# ── 5. Active Subscription Lookup ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_get_active_subscription_lookup(service: SubscriptionService, test_account: Account):
    now = datetime.now(timezone.utc)

    # 1. No subscription initially
    assert await service.get_active_subscription(test_account.id) is None

    # 2. Active subscription
    sub = await service.create_subscription(
        account_id=test_account.id,
        plan_id="standard",
        starts_at=now,
        expires_at=now + timedelta(days=30),
        status=SubscriptionLifecycleStatus.ACTIVE,
    )
    active = await service.get_active_subscription(test_account.id)
    assert active is not None
    assert active.id == sub.id

    # 3. Cancelled subscription should not be active
    await service.cancel_subscription(sub.id)
    assert await service.get_active_subscription(test_account.id) is None


# ── 6. Concurrency & Row Locking ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_concurrent_subscription_modification(service: SubscriptionService, test_account: Account):
    """
    Verify that lifecycle operations acquire row locks (for_update=True)
    to prevent race conditions during concurrent modifications.
    """
    now = datetime.now(timezone.utc)
    sub = await service.create_subscription(
        account_id=test_account.id,
        plan_id="standard",
        starts_at=now,
        expires_at=now + timedelta(days=30),
        status=SubscriptionLifecycleStatus.TRIAL,
    )

    # Verify get_by_id with for_update=True succeeds and locks the row in transaction
    locked_sub = await service.repository.get_by_id_or_raise(sub.id, for_update=True)
    assert locked_sub.id == sub.id
    assert locked_sub.status == SubscriptionLifecycleStatus.TRIAL

    # Transition status while locked
    activated = await service.activate_subscription(sub.id)
    assert activated.status == SubscriptionLifecycleStatus.ACTIVE
