"""
subscription_service.py — Domain service for managing subscription contracts and lifecycle transitions (Phase 2.1).
"""
from __future__ import annotations

import logging
import uuid
from typing import Any
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import EntityNotFoundError, DatabaseOperationError
from app.models import Subscription, SubscriptionLifecycleStatus
from app.models.subscription_plan import PLANS_REGISTRY
from app.repositories import AccountRepository, SubscriptionRepository
from app.services.exceptions import (
    UnknownPlanError,
    SubscriptionNotFoundError,
    InvalidSubscriptionStateError,
    SubscriptionAlreadyActiveError,
)

logger = logging.getLogger(__name__)


class SubscriptionService:
    """
    Pure domain service responsible for subscription creation, renewal, cancellation,
    and lifecycle transitions. Independent of HTTP and framework layers.
    """

    def __init__(self, session: AsyncSession, provisioning_service: Any | None = None) -> None:
        self.session = session
        self.provisioning_service = provisioning_service
        self.repository = SubscriptionRepository(session)
        self.account_repo = AccountRepository(session)

    async def create_subscription(
        self,
        account_id: uuid.UUID,
        plan_id: str,
        starts_at: datetime,
        expires_at: datetime,
        *,
        auto_renew: bool = True,
        status: SubscriptionLifecycleStatus = SubscriptionLifecycleStatus.ACTIVE,
        commit: bool = True,
    ) -> Subscription:
        """
        Create a new subscription contract for an account.
        Validates account existence, plan validity, and verifies no conflicting active subscription exists.
        """
        account = await self.account_repo.get_by_id(account_id)
        if not account:
            raise EntityNotFoundError(f"Account with ID {account_id} not found.")

        clean_plan_id = (plan_id or "").strip().lower()
        if clean_plan_id not in PLANS_REGISTRY:
            raise UnknownPlanError(f"Unknown subscription plan ID: '{clean_plan_id}'")

        now = datetime.now(timezone.utc)
        existing_active = await self.repository.get_active_for_account(account_id, now, for_update=True)
        if existing_active:
            raise SubscriptionAlreadyActiveError(
                f"Account {account_id} already has an active subscription (id={existing_active.id})."
            )

        subscription = await self.repository.create(
            account_id=account_id,
            plan_id=clean_plan_id,
            status=status,
            starts_at=starts_at,
            expires_at=expires_at,
            auto_renew=auto_renew,
            commit=commit,
        )
        logger.info("Created new subscription id=%s for plan=%s status=%s", subscription.id, clean_plan_id, status.value)
        if self.provisioning_service and status == SubscriptionLifecycleStatus.ACTIVE:
            await self.provisioning_service.provision_subscription(account_id, clean_plan_id, expires_at, commit=commit)
        return subscription

    async def activate_subscription(self, subscription_id: uuid.UUID, *, commit: bool = True) -> Subscription:
        """
        Activate a pending, trial, or grace subscription.
        Idempotent if already ACTIVE. Blocks activation of CANCELLED or EXPIRED subscriptions.
        """
        sub = await self.repository.get_by_id(subscription_id, for_update=True)
        if not sub:
            raise SubscriptionNotFoundError(f"Subscription {subscription_id} not found.")

        if sub.status == SubscriptionLifecycleStatus.CANCELLED:
            raise InvalidSubscriptionStateError("Cannot activate a cancelled subscription.")
        if sub.status == SubscriptionLifecycleStatus.EXPIRED:
            raise InvalidSubscriptionStateError("Cannot activate an expired subscription.")
        if sub.status == SubscriptionLifecycleStatus.ACTIVE:
            return sub

        sub.status = SubscriptionLifecycleStatus.ACTIVE
        sub.grace_expires_at = None
        await self.repository.update(sub, commit=commit)
        logger.info("Activated subscription id=%s", sub.id)
        if self.provisioning_service:
            await self.provisioning_service.provision_subscription(sub.account_id, sub.plan_id, sub.expires_at, commit=commit)
        return sub

    async def renew_subscription(self, subscription_id: uuid.UUID, new_expires_at: datetime, *, commit: bool = True) -> Subscription:
        """
        Renew an existing subscription by extending its expiration date and resetting status to ACTIVE.
        Blocks renewal of CANCELLED subscriptions.
        """
        sub = await self.repository.get_by_id(subscription_id, for_update=True)
        if not sub:
            raise SubscriptionNotFoundError(f"Subscription {subscription_id} not found.")

        if sub.status == SubscriptionLifecycleStatus.CANCELLED:
            raise InvalidSubscriptionStateError("Cannot renew a cancelled subscription.")

        sub.expires_at = new_expires_at
        sub.status = SubscriptionLifecycleStatus.ACTIVE
        sub.grace_expires_at = None
        await self.repository.update(sub, commit=commit)
        logger.info("Renewed subscription id=%s until %s", sub.id, new_expires_at.isoformat())
        if self.provisioning_service:
            await self.provisioning_service.extend_subscription(sub.account_id, new_expires_at, commit=commit)
        return sub

    async def cancel_subscription(self, subscription_id: uuid.UUID, *, commit: bool = True) -> Subscription:
        """
        Cancel a subscription and disable auto-renewal.
        Idempotent if already CANCELLED.
        """
        sub = await self.repository.get_by_id(subscription_id, for_update=True)
        if not sub:
            raise SubscriptionNotFoundError(f"Subscription {subscription_id} not found.")

        if sub.status == SubscriptionLifecycleStatus.CANCELLED:
            return sub

        sub.status = SubscriptionLifecycleStatus.CANCELLED
        sub.auto_renew = False
        await self.repository.update(sub, commit=commit)
        logger.info("Cancelled subscription id=%s", sub.id)
        if self.provisioning_service:
            await self.provisioning_service.suspend_subscription(sub.account_id, commit=commit)
        return sub

    async def enter_grace_period(self, subscription_id: uuid.UUID, grace_duration_days: int = 7, *, commit: bool = True) -> Subscription:
        """
        Transition an ACTIVE subscription into a GRACE period after payment failure or renewal warning.
        Requires the subscription to be currently ACTIVE with auto_renew enabled.
        """
        sub = await self.repository.get_by_id(subscription_id, for_update=True)
        if not sub:
            raise SubscriptionNotFoundError(f"Subscription {subscription_id} not found.")

        if sub.status != SubscriptionLifecycleStatus.ACTIVE:
            raise InvalidSubscriptionStateError(
                f"Cannot enter grace period from status '{sub.status.value}'; must be ACTIVE."
            )
        if not sub.auto_renew:
            raise InvalidSubscriptionStateError("Cannot enter grace period when auto-renew is disabled.")

        now = datetime.now(timezone.utc)
        sub.status = SubscriptionLifecycleStatus.GRACE
        sub.grace_expires_at = now + timedelta(days=grace_duration_days)
        await self.repository.update(sub, commit=commit)
        logger.info("Subscription id=%s entered grace period until %s", sub.id, sub.grace_expires_at.isoformat())
        return sub

    async def expire_subscription(self, subscription_id: uuid.UUID, *, commit: bool = True) -> Subscription:
        """
        Mark a subscription as EXPIRED when it reaches end of term or grace period without renewal.
        Cannot expire a CANCELLED subscription.
        """
        sub = await self.repository.get_by_id(subscription_id, for_update=True)
        if not sub:
            raise SubscriptionNotFoundError(f"Subscription {subscription_id} not found.")

        if sub.status == SubscriptionLifecycleStatus.CANCELLED:
            raise InvalidSubscriptionStateError("Cannot expire an already cancelled subscription.")

        sub.status = SubscriptionLifecycleStatus.EXPIRED
        await self.repository.update(sub, commit=commit)
        logger.info("Expired subscription id=%s", sub.id)
        if self.provisioning_service:
            await self.provisioning_service.suspend_subscription(sub.account_id, commit=commit)
        return sub

    async def get_active_subscription(self, account_id: uuid.UUID) -> Subscription | None:
        """
        Retrieve the current active, trial, or unexpired grace subscription for an account.
        """
        now = datetime.now(timezone.utc)
        return await self.repository.get_active_for_account(account_id, now)
