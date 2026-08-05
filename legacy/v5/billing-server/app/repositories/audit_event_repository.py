"""
audit_event_repository.py — Repository for durable audit event storage (Phase 3.0.5).

Provides append-only database operations for security audit events.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent


class AuditEventRepository:
    """Repository for durable audit event storage with append-only semantics."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        event_type: str,
        actor_id: str,
        target_id: str,
        details: dict[str, Any],
        ip_hash: str | None = None,
    ) -> AuditEvent:
        """
        Create and persist a new audit event.
        This is an append-only operation - events cannot be modified after creation.
        """
        event = AuditEvent(
            event_type=event_type,
            actor_id=actor_id,
            target_id=target_id,
            details=details,
            ip_hash=ip_hash,
        )
        self._session.add(event)
        await self._session.flush()
        await self._session.refresh(event)
        return event

    async def list_events(
        self,
        event_type: str | None = None,
        actor_id: str | None = None,
        target_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """
        Retrieve audit events with optional filtering.
        Returns events in reverse chronological order (newest first).
        """
        query = select(AuditEvent)

        if event_type is not None:
            query = query.where(AuditEvent.event_type == event_type)
        if actor_id is not None:
            query = query.where(AuditEvent.actor_id == actor_id)
        if target_id is not None:
            query = query.where(AuditEvent.target_id == target_id)

        query = query.order_by(desc(AuditEvent.timestamp))
        query = query.limit(limit).offset(offset)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def list_events_cursor(
        self,
        cursor: str | None = None,
        since: datetime | None = None,
        event_type: str | None = None,
        actor_id: str | None = None,
        target_id: str | None = None,
        limit: int = 50,
    ) -> tuple[list[AuditEvent], str | None, bool]:
        """
        Retrieve audit events using cursor-based keyset pagination (descending order by timestamp, event_id).
        Returns: (events, next_cursor, has_more)
        """
        from sqlalchemy import or_, and_
        query = select(AuditEvent)

        if since is not None:
            query = query.where(AuditEvent.timestamp >= since)
        if event_type is not None:
            query = query.where(AuditEvent.event_type == event_type)
        if actor_id is not None:
            query = query.where(AuditEvent.actor_id == actor_id)
        if target_id is not None:
            query = query.where(AuditEvent.target_id == target_id)

        if cursor:
            try:
                parts = cursor.split("|", 1)
                if len(parts) == 2:
                    cursor_ts = datetime.fromisoformat(parts[0])
                    cursor_id = parts[1]
                    query = query.where(
                        or_(
                            AuditEvent.timestamp < cursor_ts,
                            and_(AuditEvent.timestamp == cursor_ts, AuditEvent.event_id < cursor_id)
                        )
                    )
            except (ValueError, TypeError):
                pass  # Ignore invalid cursor format

        query = query.order_by(desc(AuditEvent.timestamp), desc(AuditEvent.event_id))
        query = query.limit(limit + 1)

        result = await self._session.execute(query)
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]
            last = rows[-1]
            next_cursor = f"{last.timestamp.isoformat()}|{last.event_id}"
        else:
            next_cursor = None

        return rows, next_cursor, has_more

    async def get_by_event_id(self, event_id: str) -> AuditEvent | None:
        """Retrieve a specific audit event by its ID."""
        query = select(AuditEvent).where(AuditEvent.event_id == event_id)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_queue_status(self) -> dict[str, Any]:
        """Return audit event statistics for health monitoring."""
        from sqlalchemy import func

        total_query = select(func.count()).select_from(AuditEvent)
        result = await self._session.execute(total_query)
        total_events = result.scalar() or 0

        return {
            "total_events_recorded": total_events,
            "storage": "database",
            "immutable": True,
            "status": "ok",
        }
