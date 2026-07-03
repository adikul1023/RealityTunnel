"""
device_repository.py — Persistence layer for Device entities.
"""
from __future__ import annotations

import uuid
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DatabaseOperationError
from app.models import Device
from app.repositories.base import BaseRepository


class DeviceRepository(BaseRepository[Device]):
    """
    Repository for Device model queries and CRUD operations.
    Manages active client instances registered to user accounts.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Device, session)

    async def get_by_guid(self, device_guid: str, *, for_update: bool = False) -> Device | None:
        """
        Retrieve a device instance by its client-generated GUID.
        If for_update=True, acquires row-level exclusive lock (SELECT ... FOR UPDATE).
        """
        try:
            stmt = select(Device).where(Device.device_guid == device_guid)
            if for_update:
                stmt = stmt.with_for_update()
            result = await self.session.execute(stmt)
            return result.scalars().first()
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying Device by device_guid"
            ) from exc

    async def get_devices_for_account(self, account_id: uuid.UUID) -> list[Device]:
        """
        List all active devices registered under a specific account,
        ordered by most recently seen first.
        """
        try:
            stmt = (
                select(Device)
                .where(Device.account_id == account_id)
                .order_by(Device.last_seen_at.desc())
            )
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying devices for account"
            ) from exc
