"""
connection_signal_repository.py — Persistence layer for ConnectionSignal entities.

Phase 1.4.4: Supports inserting and paginated querying of security event signals
ordered by occurred_at descending.
"""
from __future__ import annotations

import uuid
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DatabaseOperationError
from app.models.connection_signal import ConnectionSignal
from app.repositories.base import BaseRepository


class ConnectionSignalRepository(BaseRepository[ConnectionSignal]):
    """
    Repository for ConnectionSignal queries and persistence.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ConnectionSignal, session)

    async def list_for_account(
        self, account_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> list[ConnectionSignal]:
        """
        List connection signals for a specific account, ordered newest-first.
        Supports limit and offset pagination.
        """
        try:
            stmt = (
                select(ConnectionSignal)
                .where(ConnectionSignal.account_id == account_id)
                .order_by(ConnectionSignal.occurred_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying connection signals for account"
            ) from exc

    async def list_for_device(
        self, device_guid: str, *, limit: int = 50, offset: int = 0
    ) -> list[ConnectionSignal]:
        """
        List connection signals for a specific device, ordered newest-first.
        Supports limit and offset pagination.
        """
        try:
            stmt = (
                select(ConnectionSignal)
                .where(ConnectionSignal.device_guid == device_guid)
                .order_by(ConnectionSignal.occurred_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying connection signals for device"
            ) from exc
