"""
provisioning_retry_repository.py — Persistence layer for transient provisioning retries (Phase 2.6).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DatabaseOperationError
from app.models.provisioning_retry import ProvisioningRetryItem, RetryItemStatus
from app.repositories.base import BaseRepository


class ProvisioningRetryRepository(BaseRepository[ProvisioningRetryItem]):
    """
    Repository for ProvisioningRetryItem queries and CRUD operations.
    Supports row-level locking for concurrency control when scheduler jobs process retries.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ProvisioningRetryItem, session)

    async def get_pending_retries(
        self, now: datetime, *, for_update: bool = False
    ) -> list[ProvisioningRetryItem]:
        """
        Retrieve all pending retry items whose scheduled execution time has arrived.
        If for_update=True, acquires row-level exclusive lock (SELECT ... FOR UPDATE).
        """
        try:
            stmt = (
                select(ProvisioningRetryItem)
                .where(ProvisioningRetryItem.status == RetryItemStatus.PENDING)
                .where(ProvisioningRetryItem.next_retry_at <= now)
                .order_by(ProvisioningRetryItem.next_retry_at.asc())
            )
            if for_update:
                stmt = stmt.with_for_update()
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying pending provisioning retries"
            ) from exc

    async def get_by_account_id(
        self, account_id: uuid.UUID, *, for_update: bool = False
    ) -> list[ProvisioningRetryItem]:
        """
        Retrieve all retry items for a specific account.
        """
        try:
            stmt = select(ProvisioningRetryItem).where(ProvisioningRetryItem.account_id == account_id)
            if for_update:
                stmt = stmt.with_for_update()
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying provisioning retries by account ID"
            ) from exc

    async def list_all(
        self, limit: int = 50, offset: int = 0, status: RetryItemStatus | None = None
    ) -> list[ProvisioningRetryItem]:
        """Retrieve paginated list of retry items."""
        try:
            stmt = select(ProvisioningRetryItem).order_by(ProvisioningRetryItem.created_at.desc()).limit(limit).offset(offset)
            if status is not None:
                stmt = stmt.where(ProvisioningRetryItem.status == status)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error listing provisioning retries"
            ) from exc

    async def count_all(self, status: RetryItemStatus | None = None) -> int:
        """Count total retry items, optionally filtered by status."""
        try:
            stmt = select(func.count()).select_from(ProvisioningRetryItem)
            if status is not None:
                stmt = stmt.where(ProvisioningRetryItem.status == status)
            result = await self.session.execute(stmt)
            return int(result.scalar_one() or 0)
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error counting provisioning retries"
            ) from exc

