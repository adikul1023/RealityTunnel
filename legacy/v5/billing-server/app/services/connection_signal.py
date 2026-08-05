"""
connection_signal.py — Domain service for Connection Security Signal collection & analytics.

Phase 1.4.4: Enforces security event recording rules and queries without exposing database session state
or SQLAlchemy ORM errors.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app.exceptions import RepositoryError
from app.models.connection_signal import ConnectionSignal, ConnectionEventType
from app.repositories.connection_signal_repository import ConnectionSignalRepository
from app.services.exceptions import ConnectionSignalServiceError

logger = logging.getLogger(__name__)


class ConnectionSignalService:
    """
    Service responsible for recording and retrieving authentication and device security signals.
    """

    def __init__(self, repo: ConnectionSignalRepository) -> None:
        self.repo = repo

    async def record_signal(
        self,
        account_id: uuid.UUID | None,
        event_type: ConnectionEventType,
        success: bool,
        *,
        device_guid: str | None = None,
        source_ip: str | None = None,
        user_agent: str | None = None,
        occurred_at: datetime | None = None,
    ) -> ConnectionSignal:
        """
        Record a structured security event.
        Translates repository failures into clean ConnectionSignalServiceError domain exceptions.
        """
        try:
            signal = await self.repo.create(
                account_id=account_id,
                event_type=event_type,
                success=success,
                device_guid=device_guid,
                source_ip=source_ip,
                user_agent=user_agent,
                occurred_at=occurred_at or datetime.now(timezone.utc),
            )
            return signal
        except RepositoryError as exc:
            logger.error("Failed to persist connection signal in repository: %s", exc)
            raise ConnectionSignalServiceError("Database error recording connection signal") from exc
        except Exception as exc:
            logger.error("Unexpected error persisting connection signal: %s", exc)
            raise ConnectionSignalServiceError("Unexpected error recording connection signal") from exc

    async def get_recent_signals(
        self, account_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> list[ConnectionSignal]:
        """
        Retrieve recent security signals for an account, ordered newest-first.
        """
        try:
            return await self.repo.list_for_account(account_id, limit=limit, offset=offset)
        except RepositoryError as exc:
            raise ConnectionSignalServiceError("Database error querying signals for account") from exc

    async def get_recent_signals_for_device(
        self, device_guid: str, *, limit: int = 50, offset: int = 0
    ) -> list[ConnectionSignal]:
        """
        Retrieve recent security signals for a device, ordered newest-first.
        """
        try:
            return await self.repo.list_for_device(device_guid, limit=limit, offset=offset)
        except RepositoryError as exc:
            raise ConnectionSignalServiceError("Database error querying signals for device") from exc
