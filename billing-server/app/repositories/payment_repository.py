"""
payment_repository.py — Persistence layer for Payment entities (Phase 2.3).
"""
from __future__ import annotations

import uuid
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DatabaseOperationError
from app.models import Payment
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
