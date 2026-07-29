"""
system_health_repository.py — Persistence layer for generic operational health check status (Phase 2.6).
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DatabaseOperationError
from app.models.system_health import SystemHealthStatus
from app.repositories.base import BaseRepository


class SystemHealthRepository(BaseRepository[SystemHealthStatus]):
    """
    Repository for SystemHealthStatus queries and CRUD operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SystemHealthStatus, session)

    async def get_by_key(
        self, component_key: str, *, for_update: bool = False
    ) -> SystemHealthStatus | None:
        """
        Retrieve system health status by component key (e.g., 'marzban', 'payment_gateway').
        """
        try:
            stmt = select(SystemHealthStatus).where(SystemHealthStatus.component_key == component_key)
            if for_update:
                stmt = stmt.with_for_update()
            result = await self.session.execute(stmt)
            return result.scalars().first()
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying system health status by component key"
            ) from exc

    async def upsert_status(
        self,
        component_key: str,
        status: str,
        message: str | None,
        checked_at: datetime,
    ) -> SystemHealthStatus:
        """
        Insert or update system health status for a component.
        """
        try:
            record = await self.get_by_key(component_key, for_update=True)
            if not record:
                record = SystemHealthStatus(
                    component_key=component_key,
                    status=status,
                    message=message,
                    last_checked_at=checked_at,
                )
                await self.create(record, commit=False)
            else:
                record.status = status
                record.message = message
                record.last_checked_at = checked_at
                await self.update(record, commit=False)
            await self.session.commit()
            await self.session.refresh(record)
            return record
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise DatabaseOperationError(
                "Database error upserting system health status"
            ) from exc

    async def get_all_statuses(self) -> list[SystemHealthStatus]:
        """Retrieve all system health status records."""
        try:
            stmt = select(SystemHealthStatus)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError("Database error retrieving all health status records") from exc

