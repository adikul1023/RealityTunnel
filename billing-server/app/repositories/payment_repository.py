"""
payment_repository.py — Persistence layer for Payment entities (Phase 2.3).
"""
from __future__ import annotations

import uuid
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DatabaseOperationError
from app.models import Payment
from app.models.payment import PaymentStatus
from app.repositories.base import BaseRepository



class PaymentRepository(BaseRepository[Payment]):
    """
    Repository for Payment queries and CRUD operations.
    Supports row-level locking for concurrency control during payment confirmation and webhook handling.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Payment, session)

    async def get_by_idempotency_key(
        self, idempotency_key: str, *, for_update: bool = False
    ) -> Payment | None:
        """
        Retrieve a payment by its unique idempotency key.
        If for_update=True, acquires row-level exclusive lock (SELECT ... FOR UPDATE).
        """
        try:
            stmt = select(Payment).where(Payment.idempotency_key == idempotency_key)
            if for_update:
                stmt = stmt.with_for_update()
            result = await self.session.execute(stmt)
            return result.scalars().first()
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying payment by idempotency key"
            ) from exc

    async def get_by_provider_order_id(
        self, provider_order_id: str, *, for_update: bool = False
    ) -> Payment | None:
        """
        Retrieve a payment by the gateway provider's order ID (e.g., Razorpay order_EKwxw...).
        If for_update=True, acquires row-level exclusive lock (SELECT ... FOR UPDATE).
        """
        try:
            stmt = select(Payment).where(Payment.provider_order_id == provider_order_id)
            if for_update:
                stmt = stmt.with_for_update()
            result = await self.session.execute(stmt)
            return result.scalars().first()
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying payment by provider order ID"
            ) from exc

    async def get_by_provider_payment_id(
        self, provider_payment_id: str, *, for_update: bool = False
    ) -> Payment | None:
        """
        Retrieve a payment by the gateway provider's payment ID (e.g., Razorpay pay_29QQo...).
        If for_update=True, acquires row-level exclusive lock (SELECT ... FOR UPDATE).
        """
        try:
            stmt = select(Payment).where(Payment.provider_payment_id == provider_payment_id)
            if for_update:
                stmt = stmt.with_for_update()
            result = await self.session.execute(stmt)
            return result.scalars().first()
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying payment by provider payment ID"
            ) from exc

    async def get_by_account_id(self, account_id: uuid.UUID) -> list[Payment]:
        """
        List all payments for an account, ordered by creation time descending.
        """
        try:
            stmt = (
                select(Payment)
                .where(Payment.account_id == account_id)
                .order_by(Payment.created_at.desc())
            )
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying payments for account"
            ) from exc

    async def list_by_account_id_paginated(
        self, account_id: uuid.UUID, limit: int, offset: int
    ) -> list[Payment]:
        """
        Retrieve a paginated list of payments for an account, ordered by creation time descending.
        """
        try:
            stmt = (
                select(Payment)
                .where(Payment.account_id == account_id)
                .order_by(Payment.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying paginated payments for account"
            ) from exc

    async def count_by_account_id(self, account_id: uuid.UUID) -> int:
        """
        Count total number of payments for an account.
        """
        try:
            stmt = select(func.count()).select_from(Payment).where(Payment.account_id == account_id)
            result = await self.session.execute(stmt)
            return int(result.scalar() or 0)
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error counting payments for account"
            ) from exc


    async def get_stale_pending_payments(
        self, cutoff_time: datetime, *, for_update: bool = False
    ) -> list[Payment]:
        """
        Retrieve all pending or created payments created before cutoff_time.
        If for_update=True, acquires row-level exclusive lock (SELECT ... FOR UPDATE).
        """
        try:
            from app.models.payment import PaymentStatus
            stmt = (
                select(Payment)
                .where(Payment.status.in_([PaymentStatus.CREATED, PaymentStatus.PENDING]))
                .where(Payment.created_at <= cutoff_time)
            )
            if for_update:
                stmt = stmt.with_for_update()
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying stale pending payments"
            ) from exc

    async def list_all_paginated(
        self,
        limit: int = 50,
        offset: int = 0,
        status: PaymentStatus | None = None,
    ) -> list[Payment]:
        """
        Retrieve a paginated list of all payments across all accounts.
        Optionally filter by payment status.
        """
        try:
            stmt = select(Payment).order_by(Payment.created_at.desc()).limit(limit).offset(offset)
            if status is not None:
                stmt = stmt.where(Payment.status == status)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying paginated payments"
            ) from exc

    async def count_all(self, status: PaymentStatus | None = None) -> int:
        """
        Count total payments across all accounts, optionally filtered by status.
        """
        try:
            stmt = select(func.count()).select_from(Payment)
            if status is not None:
                stmt = stmt.where(Payment.status == status)
            result = await self.session.execute(stmt)
            return int(result.scalar_one() or 0)
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error counting payments"
            ) from exc

    async def sum_amount_by_date_range(
        self,
        start_time: datetime,
        end_time: datetime,
        status: PaymentStatus = PaymentStatus.PAID,
    ) -> int:
        """
        Sum total payment amount in minor units for payments created within a date range.
        """
        try:
            stmt = (
                select(func.sum(Payment.amount_minor_units))
                .where(Payment.status == status)
                .where(Payment.created_at >= start_time)
                .where(Payment.created_at <= end_time)
            )
            result = await self.session.execute(stmt)
            return int(result.scalar_one() or 0)
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error summing payments by date range"
            ) from exc

    async def count_by_date_range(
        self,
        start_time: datetime,
        end_time: datetime,
        status: PaymentStatus | None = None,
    ) -> int:
        """
        Count total payments created within a date range.
        """
        try:
            stmt = (
                select(func.count())
                .select_from(Payment)
                .where(Payment.created_at >= start_time)
                .where(Payment.created_at <= end_time)
            )
            if status is not None:
                stmt = stmt.where(Payment.status == status)
            result = await self.session.execute(stmt)
            return int(result.scalar_one() or 0)
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error counting payments by date range"
            ) from exc


