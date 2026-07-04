"""
lifecycle_job_service.py — Service orchestrating background lifecycle automation jobs.
Strictly adheres to architectural rules:
- No direct SQL outside domain services or repository methods
- No direct communication with third-party providers (Marzban, Razorpay)
- All state transitions use existing domain service layer methods
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProvisioningState, RetryItemStatus, SubscriptionLifecycleStatus
from app.repositories import (
    SubscriptionRepository,
    PaymentRepository,
    ProvisioningRepository,
    ProvisioningRetryRepository,
    SystemHealthRepository,
)
from app.services import (
    SubscriptionService,
    ProvisioningService,
    PaymentService,
    CredentialService,
)

logger = logging.getLogger(__name__)


class LifecycleJobService:
    """
    Orchestrator for automated background jobs.
    Each job method processes batch items with proper error isolation and transaction management.
    """

    def __init__(
        self,
        session: AsyncSession,
        subscription_service: SubscriptionService,
        provisioning_service: ProvisioningService,
        payment_service: PaymentService,
        credential_service: CredentialService | None = None,
    ) -> None:
        self.session = session
        self.subscription_service = subscription_service
        self.provisioning_service = provisioning_service
        self.payment_service = payment_service
        self.credential_service = credential_service
        self.subscription_repo = SubscriptionRepository(session)
        self.payment_repo = PaymentRepository(session)
        self.provisioning_repo = ProvisioningRepository(session)
        self.retry_repo = ProvisioningRetryRepository(session)
        self.health_repo = SystemHealthRepository(session)

    async def run_subscription_expiration_job(self, now: datetime | None = None) -> int:
        """
        Job 1: Scan active subscriptions where expires_at <= now.
        If auto_renew=True -> transition to GRACE period.
        If auto_renew=False -> transition to EXPIRED and revoke credentials.
        Returns number of subscriptions processed.
        """
        now = now or datetime.now(timezone.utc)
        expired_subs = await self.subscription_repo.get_expired_active_subscriptions(now)
        count = 0
        for sub in expired_subs:
            try:
                if sub.auto_renew:
                    await self.subscription_service.enter_grace_period(sub.id, commit=True)
                    logger.info("Subscription id=%s transitioned to GRACE period", sub.id)
                else:
                    await self.subscription_service.expire_subscription(sub.id, commit=True)
                    if self.credential_service:
                        try:
                            await self.credential_service.revoke_credentials(sub.account_id, commit=True)
                        except Exception as e:
                            logger.warning(
                                "Failed to revoke credentials during expiration account_id=%s: %s",
                                sub.account_id,
                                str(e),
                            )
                    logger.info("Subscription id=%s expired", sub.id)
                count += 1
            except Exception as exc:
                logger.error("Error running expiration job for subscription id=%s: %s", sub.id, str(exc))
                await self.session.rollback()
        return count

    async def run_grace_period_expiration_job(self, now: datetime | None = None) -> int:
        """
        Job 2: Scan grace subscriptions where grace_expires_at <= now.
        Transition to EXPIRED and revoke credentials.
        Returns number of grace subscriptions expired.
        """
        now = now or datetime.now(timezone.utc)
        expired_grace = await self.subscription_repo.get_expired_grace_subscriptions(now)
        count = 0
        for sub in expired_grace:
            try:
                await self.subscription_service.expire_subscription(sub.id, commit=True)
                if self.credential_service:
                    try:
                        await self.credential_service.revoke_credentials(sub.account_id, commit=True)
                    except Exception as e:
                        logger.warning(
                            "Failed to revoke credentials for grace expiration account_id=%s: %s",
                            sub.account_id,
                            str(e),
                        )
                logger.info("Grace period ended; subscription id=%s expired", sub.id)
                count += 1
            except Exception as exc:
                logger.error("Error running grace expiration for subscription id=%s: %s", sub.id, str(exc))
                await self.session.rollback()
        return count

    async def run_stale_pending_payment_cleanup_job(self, now: datetime | None = None) -> int:
        """
        Job 3: Scan uncaptured payments created > 24 hours ago.
        Transition status to CANCELLED.
        Returns number of payments cancelled.
        """
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)
        stale_payments = await self.payment_repo.get_stale_pending_payments(cutoff)
        count = 0
        for payment in stale_payments:
            try:
                await self.payment_service.cancel_payment(payment.id, commit=True)
                logger.info("Cancelled stale payment id=%s created at %s", payment.id, payment.created_at)
                count += 1
            except Exception as exc:
                logger.error("Error cancelling stale payment id=%s: %s", payment.id, str(exc))
                await self.session.rollback()
        return count

    async def run_orphan_provisioning_cleanup_job(self, now: datetime | None = None) -> int:
        """
        Job 4: Scan active/suspended provisioning profiles without an active subscription.
        Revoke credentials or suspend subscription to prevent unbilled VPN access.
        Returns number of orphan profiles cleaned up.
        """
        now = now or datetime.now(timezone.utc)
        profiles = await self.provisioning_repo.get_all_active_or_suspended()
        count = 0
        for profile in profiles:
            try:
                active_sub = await self.subscription_service.get_active_subscription(profile.account_id)
                if not active_sub and profile.provisioning_state == ProvisioningState.ACTIVE:
                    logger.warning(
                        "Found active provisioning profile without active subscription account_id=%s",
                        profile.account_id,
                    )
                    if self.credential_service:
                        try:
                            await self.credential_service.revoke_credentials(profile.account_id, commit=True)
                        except Exception as e:
                            logger.warning(
                                "Failed to revoke credentials in orphan cleanup account_id=%s: %s",
                                profile.account_id,
                                str(e),
                            )
                    else:
                        await self.provisioning_service.suspend_subscription(profile.account_id, commit=True)
                    count += 1
            except Exception as exc:
                logger.error("Error in orphan cleanup for account_id=%s: %s", profile.account_id, str(exc))
                await self.session.rollback()
        return count

    async def run_system_health_monitoring_job(self, now: datetime | None = None) -> dict[str, bool]:
        """
        Job 5: Check health of remote providers (Marzban, Razorpay) and record status.
        Returns dictionary mapping component key to health status boolean.
        """
        now = now or datetime.now(timezone.utc)
        results = {}
        try:
            marzban_ok = await self.provisioning_service.check_provider_health()
            results["marzban"] = marzban_ok
            await self.health_repo.upsert_status(
                "marzban",
                status="ok" if marzban_ok else "degraded",
                message="Marzban API reachable" if marzban_ok else "Marzban API health check failed",
                checked_at=now,
            )
        except Exception as exc:
            results["marzban"] = False
            try:
                await self.health_repo.upsert_status(
                    "marzban",
                    status="degraded",
                    message=f"Error checking Marzban: {str(exc)[:490]}",
                    checked_at=now,
                )
            except Exception:
                await self.session.rollback()

        try:
            payment_ok = await self.payment_service.check_provider_health()
            results["payment_gateway"] = payment_ok
            await self.health_repo.upsert_status(
                "payment_gateway",
                status="ok" if payment_ok else "degraded",
                message="Payment Gateway reachable" if payment_ok else "Payment Gateway health check failed",
                checked_at=now,
            )
        except Exception as exc:
            results["payment_gateway"] = False
            try:
                await self.health_repo.upsert_status(
                    "payment_gateway",
                    status="degraded",
                    message=f"Error checking Payment Gateway: {str(exc)[:490]}",
                    checked_at=now,
                )
            except Exception:
                await self.session.rollback()

        return results

    async def run_credential_rotation_job(self, now: datetime | None = None) -> int:
        """
        Job 6: Check active profiles for rotation conditions (e.g., last_sync_at > 30 days).
        Rotate credentials safely without revoking on transient error.
        Returns number of profiles rotated.
        """
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=30)
        profiles = await self.provisioning_repo.get_all_active_or_suspended()
        count = 0
        for profile in profiles:
            if profile.provisioning_state == ProvisioningState.ACTIVE and profile.last_sync_at <= cutoff:
                try:
                    logger.info("Performing scheduled credential rotation for account_id=%s", profile.account_id)
                    await self.provisioning_service.rotate_user_credentials(profile.account_id)
                    count += 1
                except Exception as exc:
                    logger.warning(
                        "Scheduled credential rotation failed for account_id=%s: %s",
                        profile.account_id,
                        str(exc),
                    )
                    await self.session.rollback()
        return count

    async def run_failed_provision_retry_job(self, now: datetime | None = None) -> int:
        """
        Job 7: Process pending retry items from transient provisioning errors with exponential backoff.
        On success -> status COMPLETED.
        On failure -> increment attempt_count, compute next_retry_at (30 * 2^attempts).
        If attempt_count >= 5 -> status FAILED.
        Returns number of retry items successfully completed.
        """
        now = now or datetime.now(timezone.utc)
        pending_items = await self.retry_repo.get_pending_retries(now)
        count = 0
        for item in pending_items:
            try:
                await self.provisioning_service.provision_subscription(
                    item.account_id,
                    item.plan_id,
                    expire_at=item.expires_at,
                    commit=True,
                )
                item.status = RetryItemStatus.COMPLETED
                item.updated_at = datetime.now(timezone.utc)
                await self.retry_repo.update(item, commit=True)
                logger.info(
                    "Successfully processed provisioning retry item id=%s account_id=%s",
                    item.id,
                    item.account_id,
                )
                count += 1
            except Exception as exc:
                await self.session.rollback()
                try:
                    item_db = await self.retry_repo.get_by_id(item.id, for_update=True)
                    if item_db and item_db.status == RetryItemStatus.PENDING:
                        item_db.attempt_count += 1
                        item_db.last_error = str(exc)[:499]
                        item_db.updated_at = datetime.now(timezone.utc)
                        if item_db.attempt_count >= 5:
                            item_db.status = RetryItemStatus.FAILED
                            logger.error(
                                "Provisioning retry item id=%s permanently FAILED after 5 attempts",
                                item_db.id,
                            )
                        else:
                            backoff_seconds = 30 * (2 ** item_db.attempt_count)
                            item_db.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
                            logger.warning(
                                "Provisioning retry item id=%s failed attempt %d; retrying in %ds",
                                item_db.id,
                                item_db.attempt_count,
                                backoff_seconds,
                            )
                        await self.retry_repo.update(item_db, commit=True)
                except Exception as update_exc:
                    logger.error(
                        "Failed to update retry record id=%s after retry failure: %s",
                        item.id,
                        str(update_exc),
                    )
                    await self.session.rollback()
        return count
