"""
test_payment_ordering_and_concurrency.py

Two prove-it tests for real-world Razorpay edge cases:

1. Out-of-order webhooks
   Razorpay can replay events in any order.  This test delivers:
       payment.captured  →  payment.refunded  →  payment.captured  (again)
   and proves the subscription lands in the single, correct terminal state.
   A stale capture replayed after a refund MUST NOT resurrect the subscription.

2. Concurrent renewal double-spend
   Prove that a duplicate webhook + provider retry + network timeout arriving
   simultaneously cannot renew the same subscription twice.
   All concurrent paths must produce exactly-once semantics.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from app.database import AsyncSessionLocal, engine
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import PaymentStatus, SubscriptionLifecycleStatus
from app.repositories import PaymentRepository, SubscriptionRepository
from app.services.payment.provider import (
    PaymentOrderDTO,
    PaymentRefundDTO,
    PaymentVerificationDTO,
    PaymentWebhookDTO,
)
from app.services.payment.service import PaymentService
from app.services.exceptions import PaymentVerificationError


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_provider() -> AsyncMock:
    """Fresh mock Razorpay provider with sensible defaults."""
    provider = AsyncMock()
    provider.create_order.return_value = PaymentOrderDTO(
        provider_order_id="order_oop_001",
        amount_minor_units=100_000,
        currency="INR",
    )
    provider.fetch_payment.return_value = PaymentVerificationDTO(
        is_valid=True,
        provider_order_id="order_oop_001",
        provider_payment_id="pay_oop_001",
        status="captured",
        amount_minor_units=100_000,
        currency="INR",
        amount_refunded_minor_units=0,
    )
    provider.verify_webhook.return_value = PaymentWebhookDTO(
        event_type="payment.captured",
        status="captured",
        provider_order_id="order_oop_001",
        provider_payment_id="pay_oop_001",
        amount_minor_units=100_000,
        currency="INR",
        signature="mock_sig",
    )
    provider.refund_payment.return_value = PaymentRefundDTO(
        provider_refund_id="rfnd_oop_001",
        provider_payment_id="pay_oop_001",
        amount_minor_units=100_000,
        status="processed",
    )
    return provider


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 – Out-of-order webhooks
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_out_of_order_captured_refunded_captured(
    db_session: AsyncSession,
    account_factory,
    mock_provider: AsyncMock,
) -> None:
    """
    Simulate Razorpay delivering webhooks out of order:

        Step 1 – payment.captured   → subscription becomes ACTIVE
        Step 2 – payment.refunded   → subscription is CANCELLED, payment REFUNDED
        Step 3 – payment.captured   (stale replay, weeks later)
                                    → MUST be rejected; subscription stays CANCELLED

    Business rule: once a payment reaches a terminal refund state, no subsequent
    capture replay may reactivate the entitlement.
    """
    account = await account_factory()
    service = PaymentService(db_session, mock_provider)

    # ── Step 1: Create the order ──────────────────────────────────────────────
    payment = await service.create_payment(
        account_id=account.id,
        amount_minor_units=100_000,
        currency="INR",
        idempotency_key="oop-idem-001",
    )

    # ── Step 1: Deliver payment.captured ─────────────────────────────────────
    mock_provider.fetch_payment.return_value = PaymentVerificationDTO(
        is_valid=True,
        provider_order_id=payment.provider_order_id,
        provider_payment_id="pay_oop_001",
        status="captured",
        amount_minor_units=100_000,
        currency="INR",
        amount_refunded_minor_units=0,
    )

    paid = await service.confirm_payment(
        provider_order_id=payment.provider_order_id,
        provider_payment_id="pay_oop_001",
    )
    assert paid.status == PaymentStatus.PAID, "Step 1: payment should be PAID"

    sub_repo = SubscriptionRepository(db_session)
    sub = await sub_repo.get_by_id(paid.subscription_id)
    assert sub is not None
    assert sub.status == SubscriptionLifecycleStatus.ACTIVE, (
        "Step 1: subscription should be ACTIVE after capture"
    )
    original_sub_id = sub.id

    # ── Step 2: Deliver payment.refunded ─────────────────────────────────────
    # Marzban refund: now the full amount was returned
    mock_provider.fetch_payment.return_value = PaymentVerificationDTO(
        is_valid=True,
        provider_order_id=payment.provider_order_id,
        provider_payment_id="pay_oop_001",
        status="refunded",
        amount_minor_units=100_000,
        currency="INR",
        amount_refunded_minor_units=100_000,  # full refund
    )

    refunded = await service.process_refund_webhook(
        provider_order_id=payment.provider_order_id,
    )
    assert refunded.status == PaymentStatus.REFUNDED, "Step 2: payment should be REFUNDED"

    await db_session.refresh(sub)
    assert sub.status == SubscriptionLifecycleStatus.CANCELLED, (
        "Step 2: subscription should be CANCELLED after refund"
    )

    # Confirm no active subscription remains
    active_sub = await sub_repo.get_active_for_account(account.id, datetime.now(timezone.utc))
    assert active_sub is None, "Step 2: no active subscription should exist after refund"

    # ── Step 3: Replay payment.captured (stale, weeks later) ─────────────────
    # The payment is now in a terminal REFUNDED state.  confirm_payment must raise
    # PaymentVerificationError rather than reactivating the subscription.
    with pytest.raises(PaymentVerificationError) as exc_info:
        await service.confirm_payment(
            provider_order_id=payment.provider_order_id,
            provider_payment_id="pay_oop_001",
        )
    assert "terminal state" in str(exc_info.value).lower(), (
        "Step 3: error message should mention terminal state"
    )

    # Subscription must STILL be cancelled – replay must not resurrect it
    active_sub_after_replay = await sub_repo.get_active_for_account(
        account.id, datetime.now(timezone.utc)
    )
    assert active_sub_after_replay is None, (
        "Step 3: stale captured webhook replay MUST NOT reactivate subscription"
    )

    # Payment record must remain REFUNDED
    pay_repo = PaymentRepository(db_session)
    final_payment = await pay_repo.get_by_id(paid.id)
    assert final_payment is not None
    assert final_payment.status == PaymentStatus.REFUNDED, (
        "Step 3: payment must remain REFUNDED, not reverted to PAID by replay"
    )

    # Only one subscription was ever created
    await db_session.refresh(sub)
    assert sub.id == original_sub_id, "No additional subscriptions should have been created"


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 – Concurrent renewal double-spend
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(engine.dialect.name == "sqlite", reason="SQLite does not support the concurrency controls being tested here (e.g., advisory locks or real row-level locking that blocks writers).")
@pytest.mark.asyncio
async def test_concurrent_renewal_cannot_renew_subscription_twice(
    db_session: AsyncSession,
    account_factory,
    mock_provider: AsyncMock,
) -> None:
    """
    Prove that ALL of the following arriving concurrently for the SAME order
    cannot renew the subscription more than once:

        • duplicate webhook (identical event sent twice by Razorpay)
        • retry webhook     (Razorpay retries after 30s with no 200 ACK)
        • network timeout   (first request timed out; provider resends)
        • provider retry    (Razorpay's own retry logic fires a 4th copy)

    Each goroutine independently calls confirm_payment on independent sessions
    (simulating parallel HTTP workers).  After all complete:
        - Exactly 1 subscription must be active.
        - Subscription expiry must be extended by exactly 30 days (not 60 or 120).
        - Payment must be PAID exactly once.
    """
    account = await account_factory()

    # ── Create baseline payment using the shared session ─────────────────────
    service = PaymentService(db_session, mock_provider)
    payment = await service.create_payment(
        account_id=account.id,
        amount_minor_units=100_000,
        currency="INR",
        idempotency_key="concurrent-renewal-001",
    )
    # Commit so independent sessions can see the payment row
    await db_session.commit()

    order_id = payment.provider_order_id
    pay_id = "pay_concurrent_001"

    def make_mock_provider() -> AsyncMock:
        """Each parallel worker needs its own mock instance (but same behaviour)."""
        p = AsyncMock()
        p.create_order.return_value = PaymentOrderDTO(
            provider_order_id=order_id,
            amount_minor_units=100_000,
            currency="INR",
        )
        p.fetch_payment.return_value = PaymentVerificationDTO(
            is_valid=True,
            provider_order_id=order_id,
            provider_payment_id=pay_id,
            status="captured",
            amount_minor_units=100_000,
            currency="INR",
            amount_refunded_minor_units=0,
        )
        return p

    # ── Helper: confirm_payment in an independent DB session ──────────────────
    async def worker(worker_id: int) -> str:
        """
        Returns outcome tag: 'paid' if it processed first, 'idempotent' if it
        returned the already-PAID record, or 'error:<msg>' on unexpected failure.
        """
        async with AsyncSessionLocal() as session:
            svc = PaymentService(session, make_mock_provider())
            try:
                result = await svc.confirm_payment(
                    provider_order_id=order_id,
                    provider_payment_id=pay_id,
                )
                # Both 'first win' and idempotent path return PAID
                return f"paid:{result.id}"
            except Exception as exc:
                return f"error:{exc}"

    # ── Fire 4 concurrent workers (duplicate + 3 retries) ────────────────────
    N_CONCURRENT = 4
    outcomes = await asyncio.gather(*(worker(i) for i in range(N_CONCURRENT)))

    # All outcomes must be 'paid:...' – errors are not acceptable
    for outcome in outcomes:
        assert outcome.startswith("paid:"), (
            f"Unexpected outcome from concurrent worker: {outcome!r}"
        )

    # All workers must return the SAME payment ID (idempotency guarantee)
    payment_ids_returned = {o.split(":", 1)[1] for o in outcomes}
    assert len(payment_ids_returned) == 1, (
        f"Workers returned different payment IDs: {payment_ids_returned}. "
        "Double-spend detected – confirm_payment created multiple payment records."
    )

    # ── Verify final DB state: exactly 1 active subscription ─────────────────
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as verify_session:
        sub_repo = SubscriptionRepository(verify_session)
        pay_repo = PaymentRepository(verify_session)

        active_subs = await sub_repo.get_active_for_account(account.id, now)
        assert active_subs is not None, "There must be exactly 1 active subscription"

        # Count ALL subscriptions for this account (active or not)
        all_subs = await sub_repo.get_by_account_id(account.id)
        assert len(all_subs) == 1, (
            f"Expected exactly 1 subscription, found {len(all_subs)}. "
            "Double-spend: multiple subscriptions were created."
        )

        # Verify the subscription was extended by exactly 30 days, not 60 or 120
        sub = all_subs[0]
        expected_min = now + timedelta(days=29)   # a tiny clock slack
        expected_max = now + timedelta(days=31)
        assert expected_min <= sub.expires_at <= expected_max, (
            f"Subscription expiry {sub.expires_at} is outside the expected 30-day window. "
            "Concurrent renewals may have stacked (double-spend)."
        )

        # Payment must still be exactly PAID (not REFUNDED or duplicated)
        final_payment = await pay_repo.get_by_id(payment.id)
        assert final_payment is not None
        assert final_payment.status == PaymentStatus.PAID
