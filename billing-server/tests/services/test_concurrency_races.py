"""
test_concurrency_races.py — Concurrency regression tests for Findings C-2, M-1, M-10, and H-4.

Verifies that partial unique indexes and advisory-lock + conflict recovery prevent
duplicate active subscriptions, duplicate payment orders for the same idempotency key,
and duplicate pending provisioning retry queue entries under concurrent load. Also verifies
that AccountRepository row-level locking prevents lost updates when concurrent admin
subscription extensions target the same account (Finding H-4).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from app.database import AsyncSessionLocal
from app.models import (
    Account,
    ProvisioningRetryItem,
    RetryItemStatus,
    Subscription,
    SubscriptionLifecycleStatus,
)
from app.repositories import (
    AccountRepository,
    ProvisioningRetryRepository,
    RefreshTokenRepository,
)
from app.services import (
    PaymentOrderDTO,
    PaymentService,
    ProvisioningService,
    SubscriptionService,
)
from app.services.admin_account import AdminAccountService
from app.services.exceptions import (
    ProvisioningTimeoutError,
    SubscriptionAlreadyActiveError,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_test_account() -> Account:
    async with AsyncSessionLocal() as session:
        repo = AccountRepository(session)
        account = await repo.create(
            account_id=f"CONC-{uuid.uuid4().hex[:8].upper()}",
            master_token_hash=f"hash_{uuid.uuid4().hex}",
            plan_id="pro",
        )
        return account


@pytest.mark.asyncio
async def test_concurrent_create_subscription_exactly_one_succeeds():
    """
    Finding C-2: two simultaneous create_subscription calls for the same account
    must yield exactly one success and one SubscriptionAlreadyActiveError.
    """
    account = await _create_test_account()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=30)
    barrier = asyncio.Barrier(2)

    async def attempt_create() -> Subscription | Exception:
        async with AsyncSessionLocal() as session:
            try:
                await barrier.wait()
                service = SubscriptionService(session)
                return await service.create_subscription(
                    account_id=account.id,
                    plan_id="pro",
                    starts_at=now,
                    expires_at=expires_at,
                    status=SubscriptionLifecycleStatus.ACTIVE,
                )
            except Exception as exc:
                return exc

    results = await asyncio.gather(attempt_create(), attempt_create())

    successes = [r for r in results if isinstance(r, Subscription)]
    failures = [r for r in results if isinstance(r, Exception)]

    assert len(successes) == 1, f"Expected exactly 1 success, got {results}"
    assert len(failures) == 1
    assert isinstance(failures[0], SubscriptionAlreadyActiveError)

    async with AsyncSessionLocal() as session:
        count_stmt = (
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.account_id == account.id)
            .where(
                Subscription.status.in_(
                    [
                        SubscriptionLifecycleStatus.TRIAL,
                        SubscriptionLifecycleStatus.ACTIVE,
                        SubscriptionLifecycleStatus.GRACE,
                    ]
                )
            )
        )
        active_count = int((await session.execute(count_stmt)).scalar_one())
        assert active_count == 1


@pytest.mark.asyncio
async def test_concurrent_create_payment_single_provider_order():
    """
    Finding M-1: two simultaneous create_payment calls with the same idempotency_key
    must produce exactly one provider.create_order call and one payment row.
    """
    account = await _create_test_account()
    idempotency_key = f"conc-pay-{uuid.uuid4().hex}"
    barrier = asyncio.Barrier(2)
    create_order_calls = 0
    create_order_lock = asyncio.Lock()

    provider = AsyncMock()

    async def tracked_create_order(**kwargs: Any) -> PaymentOrderDTO:
        nonlocal create_order_calls
        async with create_order_lock:
            create_order_calls += 1
        await asyncio.sleep(0.05)
        return PaymentOrderDTO(
            provider_order_id=f"order_{uuid.uuid4().hex[:12]}",
            amount_minor_units=kwargs.get("amount_minor_units", 99900),
            currency=kwargs.get("currency", "INR"),
        )

    provider.create_order.side_effect = tracked_create_order

    async def attempt_create() -> Any:
        async with AsyncSessionLocal() as session:
            await barrier.wait()
            service = PaymentService(session, provider)
            return await service.create_payment(
                account_id=account.id,
                amount_minor_units=99900,
                currency="INR",
                idempotency_key=idempotency_key,
                plan_id="pro",
            )

    payment_a, payment_b = await asyncio.gather(attempt_create(), attempt_create())

    assert payment_a.id == payment_b.id
    assert create_order_calls == 1, (
        f"Expected provider.create_order to be called once, got {create_order_calls}"
    )

    async with AsyncSessionLocal() as session:
        from app.models import Payment

        count_stmt = (
            select(func.count())
            .select_from(Payment)
            .where(Payment.idempotency_key == idempotency_key)
        )
        row_count = int((await session.execute(count_stmt)).scalar_one())
        assert row_count == 1


@pytest.mark.asyncio
async def test_concurrent_provisioning_retry_enqueue_exactly_one_pending():
    """
    Finding M-10: two simultaneous _maybe_enqueue_retry calls for the same account
    must leave exactly one PENDING row in provisioning_retry_queue.
    """
    account = await _create_test_account()
    barrier = asyncio.Barrier(2)
    provider = AsyncMock()

    async def attempt_enqueue() -> None:
        async with AsyncSessionLocal() as session:
            await barrier.wait()
            service = ProvisioningService(session, provider)
            await service._maybe_enqueue_retry(
                account_id=account.id,
                plan_id="pro",
                expire_at=datetime.now(timezone.utc) + timedelta(days=30),
                exc=ProvisioningTimeoutError("simulated gateway timeout"),
            )

    await asyncio.gather(attempt_enqueue(), attempt_enqueue())

    async with AsyncSessionLocal() as session:
        retry_repo = ProvisioningRetryRepository(session)
        items = await retry_repo.get_by_account_id(account.id)
        pending = [item for item in items if item.status == RetryItemStatus.PENDING]
        assert len(pending) == 1

        count_stmt = (
            select(func.count())
            .select_from(ProvisioningRetryItem)
            .where(ProvisioningRetryItem.account_id == account.id)
            .where(ProvisioningRetryItem.status == RetryItemStatus.PENDING)
        )
        pending_count = int((await session.execute(count_stmt)).scalar_one())
        assert pending_count == 1


@pytest.mark.asyncio
async def test_concurrent_extend_subscription_both_extensions_apply():
    """
    Finding H-4: two simultaneous AdminAccountService.extend_subscription(account_id, 30)
    calls for the same account must both take effect (total +60 days from the original
    base), not silently lose one extension to a stale read-modify-write race.

    Before the fix, AccountRepository.get_by_account_id() had no for_update support, so
    both concurrent calls could read the same stale subscription_expires_at, compute
    base + 30 days from that same stale value, and the second write would overwrite the
    first with no error and no audit trail — leaving the account extended by only 30 days
    total instead of 60.

    DETERMINISM: without deliberately widening the race window, two real Postgres round
    trips issued back-to-back can easily fail to interleave within a single test run,
    making the test pass "by luck" regardless of whether the lock is actually held. To
    force genuine contention, AccountRepository.update() (the write-then-commit step,
    which is what releases the SELECT ... FOR UPDATE lock) is patched to sleep briefly
    before committing, guaranteeing the second concurrent call's row-lock acquisition must
    actually wait — the exact mechanism the fix relies on.
    """
    account = await _create_test_account()
    now = datetime.now(timezone.utc)
    original_expiry = now + timedelta(days=10)

    async with AsyncSessionLocal() as session:
        repo = AccountRepository(session)
        fresh = await repo.get_by_id(account.id)
        assert fresh is not None
        fresh.subscription_expires_at = original_expiry
        await repo.update(fresh)

    barrier = asyncio.Barrier(2)
    original_update = AccountRepository.update

    async def delayed_update(
        self: AccountRepository, entity, *, commit: bool = True, **kwargs
    ):
        await asyncio.sleep(0.3)
        return await original_update(self, entity, commit=commit, **kwargs)

    async def attempt_extend() -> Account:
        async with AsyncSessionLocal() as session:
            account_repo = AccountRepository(session)
            refresh_repo = RefreshTokenRepository(session)
            service = AdminAccountService(account_repo, refresh_repo)
            await barrier.wait()
            return await service.extend_subscription(account.account_id, 30)

    with patch.object(AccountRepository, "update", delayed_update):
        await asyncio.gather(attempt_extend(), attempt_extend())

    async with AsyncSessionLocal() as session:
        repo = AccountRepository(session)
        final = await repo.get_by_id(account.id)
        assert final is not None
        final_expiry = final.subscription_expires_at
        if final_expiry.tzinfo is None:
            final_expiry = final_expiry.replace(tzinfo=timezone.utc)

        expected_expiry = original_expiry + timedelta(days=60)
        # Allow a small tolerance for wall-clock drift between the assertion and the
        # original write above; the key assertion is that BOTH +30 day extensions applied
        # (i.e. the result is close to +60 days total), not just one (+30 days).
        delta_from_expected = abs((final_expiry - expected_expiry).total_seconds())
        assert delta_from_expected < 5, (
            f"Expected subscription_expires_at close to {expected_expiry.isoformat()} "
            f"(both +30 day extensions applied), got {final_expiry.isoformat()} "
            f"(delta={delta_from_expected}s). A lost update would show a delta of ~30 days "
            f"(2592000s) instead."
        )
