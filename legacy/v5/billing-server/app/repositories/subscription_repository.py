"""
subscription_repository.py — Persistence layer for Subscription entities (Phase 2.1).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import select, or_, and_, func
from sqlalchemy.exc import SQLAlchemyError

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DatabaseOperationError
from app.models import Subscription, SubscriptionLifecycleStatus
from app.repositories.base import BaseRepository


class SubscriptionRepository(BaseRepository[Subscription]):
    """
    Repository for Subscription model queries and CRUD operations.
    Manages subscription lifecycle persistence and active contract lookups.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Subscription, session)

    async def get_by_account_id(self, account_id: uuid.UUID) -> list[Subscription]:
        """
        List all subscriptions for an account, ordered by creation time descending.
        """
        try:
            stmt = (
                select(Subscription)
                .where(Subscription.account_id == account_id)
                .order_by(Subscription.created_at.desc())
            )
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying subscriptions for account"
            ) from exc

    async def get_active_for_account(
        self, account_id: uuid.UUID, now: datetime, *, for_update: bool = False
    ) -> Subscription | None:
        """
        Retrieve the current active, trial, or unexpired grace subscription for an account.
        If for_update=True, acquires row-level exclusive lock (SELECT ... FOR UPDATE).
        """
        try:
            stmt = (
                select(Subscription)
                .where(Subscription.account_id == account_id)
                .where(
                    Subscription.status.in_([
                        SubscriptionLifecycleStatus.TRIAL,
                        SubscriptionLifecycleStatus.ACTIVE,
                        SubscriptionLifecycleStatus.GRACE,
                    ])
                )
                .where(
                    or_(
                        Subscription.expires_at > now,
                        and_(
                            Subscription.status == SubscriptionLifecycleStatus.GRACE,
                            Subscription.grace_expires_at.is_not(None),
                            Subscription.grace_expires_at > now,
                        ),
                    )
                )
                .order_by(Subscription.created_at.desc())
            )
            if for_update:
                stmt = stmt.with_for_update()
            result = await self.session.execute(stmt)
            return result.scalars().first()
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying active subscription for account"
            ) from exc

    async def get_expired_active_subscriptions(
        self, now: datetime, *, for_update: bool = False, skip_locked: bool = False
    ) -> list[Subscription]:
        """
        Retrieve all active subscriptions whose expiration timestamp has passed.
        If for_update=True, acquires row-level exclusive lock (SELECT ... FOR UPDATE).
        """
        try:
            stmt = (
                select(Subscription)
                .where(Subscription.status == SubscriptionLifecycleStatus.ACTIVE)
                .where(Subscription.expires_at <= now)
            )
            if for_update:
                stmt = stmt.with_for_update(skip_locked=skip_locked)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying expired active subscriptions"
            ) from exc

    async def get_expired_grace_subscriptions(
        self, now: datetime, *, for_update: bool = False, skip_locked: bool = False
    ) -> list[Subscription]:
        """
        Retrieve all grace subscriptions whose grace period timestamp has elapsed.
        If for_update=True, acquires row-level exclusive lock (SELECT ... FOR UPDATE).
        """
        try:
            stmt = (
                select(Subscription)
                .where(Subscription.status == SubscriptionLifecycleStatus.GRACE)
                .where(Subscription.grace_expires_at.is_not(None))
                .where(Subscription.grace_expires_at <= now)
            )
            if for_update:
                stmt = stmt.with_for_update(skip_locked=skip_locked)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying expired grace subscriptions"
            ) from exc

    async def list_all_paginated(
        self,
        limit: int = 50,
        offset: int = 0,
        status: SubscriptionLifecycleStatus | None = None,
    ) -> list[Subscription]:
        """
        Retrieve a paginated list of all subscriptions across all accounts.
        Optionally filter by lifecycle status.
        """
        try:
            stmt = select(Subscription).order_by(Subscription.created_at.desc()).limit(limit).offset(offset)
            if status is not None:
                stmt = stmt.where(Subscription.status == status)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying paginated subscriptions"
            ) from exc

    async def count_all(self, status: SubscriptionLifecycleStatus | None = None) -> int:
        """
        Count total subscriptions across all accounts, optionally filtered by lifecycle status.
        """
        try:
            stmt = select(func.count()).select_from(Subscription)
            if status is not None:
                stmt = stmt.where(Subscription.status == status)
            result = await self.session.execute(stmt)
            return int(result.scalar_one() or 0)
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error counting subscriptions"
            ) from exc


