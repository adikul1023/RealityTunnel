"""
test_concurrency_races.py — Concurrency regression tests for Findings C-2, M-1, and M-10.

Verifies that partial unique indexes and advisory-lock + conflict recovery prevent
duplicate active subscriptions, duplicate payment orders for the same idempotency key,
and duplicate pending provisioning retry queue entries under concurrent load.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import (
    Account,
    ProvisioningRetryItem,
    RetryItemStatus,
    Subscription,
    SubscriptionLifecycleStatus,
)
from app.repositories import AccountRepository, ProvisioningRetryRepository
from app.services import PaymentOrderDTO, PaymentService, ProvisioningService, SubscriptionService
from app.services.exceptions import ProvisioningTimeoutError, SubscriptionAlreadyActiveError


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
            .where(Subscription.status.in_([
                SubscriptionLifecycleStatus.TRIAL,
                SubscriptionLifecycleStatus.ACTIVE,
                SubscriptionLifecycleStatus.GRACE,
            ]))
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
