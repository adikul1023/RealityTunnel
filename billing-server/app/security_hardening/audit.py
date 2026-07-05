"""
audit.py — Immutable security audit logging service (Phase 3.5, updated Phase 3.0.5).

Records security-critical events (admin actions, logins, payments, device lifecycle)
with mandatory zero-secret redaction and immutability guarantees.
Now uses durable database storage via AuditEventRepository.
"""
from __future__ import annotations

import copy
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.redaction import redact_data, redact_string
from app.observability.metrics import metrics_registry
from app.security_hardening.exceptions import SecurityHardeningError
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

SUPPORTED_AUDIT_EVENT_TYPES = {
    "admin_login",
    "admin_action",
    "subscription_change",
    "payment_event",
    "credential_regeneration",
    "device_registration",
    "device_deletion",
}

# Extra regex for VLESS URI scrubbing: vless://uuid@host:port?params
_VLESS_REGEX = re.compile(r"(vless://)([^@/\s]+)(@[^?\s]+(?:\?[^\s]+)?)", re.IGNORECASE)


def _deep_scrub_secrets(obj: Any) -> Any:
    """
    Perform deep redaction of secrets, ensuring passwords, JWTs, master tokens,
    VLESS URIs, refresh tokens, and payment secrets are never stored.
    """
    if isinstance(obj, str):
        text = redact_string(obj)
        text = _VLESS_REGEX.sub(r"\1***REDACTED***\3", text)
        return text
    if isinstance(obj, dict):
        scrubbed = {}
        for k, v in obj.items():
            k_lower = str(k).lower()
            if any(w in k_lower for w in ("password", "passwd", "jwt", "token", "secret", "vless", "key", "signature", "bearer")):
                scrubbed[k] = "***REDACTED***"
            else:
                scrubbed[k] = _deep_scrub_secrets(v)
        return scrubbed
    if isinstance(obj, (list, tuple, set)):
        return type(obj)(_deep_scrub_secrets(item) for item in obj)
    return obj


@dataclass(frozen=True)
class AuditEvent:
    """Immutable representation of a security audit log record."""
    event_id: str
    timestamp: str
    event_type: str
    actor_id: str
    target_id: str
    details: dict[str, Any]
    ip_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "actor_id": self.actor_id,
            "target_id": self.target_id,
            "details": copy.deepcopy(self.details),
            "ip_hash": self.ip_hash,
        }


class AuditService:
    """
    Thread-safe, append-only immutable audit log service with durable database storage.
    Enforces strict event categorization and zero-secret data retention.
    """

    def __init__(self) -> None:
        pass  # No longer needs in-memory storage

    async def record_event(
        self,
        event_type: str,
        actor_id: str,
        target_id: str,
        details: dict[str, Any] | None = None,
        ip_hash: str | None = None,
    ) -> AuditEvent:
        """
        Record a new security audit event to durable database storage.
        All details are deeply scrubbed of credentials before persistence.
        """
        if event_type not in SUPPORTED_AUDIT_EVENT_TYPES:
            # Allow custom but log warning, or default to admin_action if unknown
            if not event_type.startswith("admin_") and not event_type.endswith("_event"):
                logger.warning("Unstandardized audit event_type: %s", event_type)

        raw_details = details or {}
        scrubbed_details = _deep_scrub_secrets(redact_data(raw_details))

        if not isinstance(scrubbed_details, dict):
            scrubbed_details = {"value": scrubbed_details}

        # Persist to database
        from app.repositories.audit_event_repository import AuditEventRepository
        
        async with AsyncSessionLocal() as session:
            repo = AuditEventRepository(session)
            db_event = await repo.create(
                event_type=event_type,
                actor_id=str(actor_id),
                target_id=str(target_id),
                details=scrubbed_details,
                ip_hash=ip_hash,
            )
            await session.commit()

        # Convert to immutable dataclass for return
        event = AuditEvent(
            event_id=db_event.event_id,
            timestamp=db_event.timestamp.isoformat(),
            event_type=db_event.event_type,
            actor_id=db_event.actor_id,
            target_id=db_event.target_id,
            details=db_event.details,
            ip_hash=db_event.ip_hash,
        )

        metrics_registry.inc_counter("audit_events_total")
        logger.info(
            "Security audit event recorded id=%s type=%s actor=%s target=%s",
            event.event_id,
            event.event_type,
            event.actor_id,
            event.target_id,
        )
        return event

    async def list_events(
        self,
        event_type: str | None = None,
        actor_id: str | None = None,
        target_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Retrieve a paginated, read-only list of audit event records from database.
        Returns events in reverse chronological order (newest first).
        """
        from app.repositories.audit_event_repository import AuditEventRepository
        
        async with AsyncSessionLocal() as session:
            repo = AuditEventRepository(session)
            db_events = await repo.list_events(
                event_type=event_type,
                actor_id=actor_id,
                target_id=target_id,
                limit=limit,
                offset=offset,
            )
        
        return [
            {
                "event_id": e.event_id,
                "timestamp": e.timestamp.isoformat(),
                "event_type": e.event_type,
                "actor_id": e.actor_id,
                "target_id": e.target_id,
                "details": e.details,
                "ip_hash": e.ip_hash,
            }
            for e in db_events
        ]

    def modify_or_delete_event(self, *args: Any, **kwargs: Any) -> None:
        """
        Prohibited operation. Audit log events are immutable.
        """
        raise SecurityHardeningError("Audit log is immutable; events cannot be modified or deleted.")

    async def get_queue_status(self) -> dict[str, Any]:
        """
        Return audit queue status and persistence statistics for admin /health inspection.
        """
        from app.repositories.audit_event_repository import AuditEventRepository
        
        async with AsyncSessionLocal() as session:
            repo = AuditEventRepository(session)
            return await repo.get_queue_status()


# Global singleton instance
audit_service = AuditService()
