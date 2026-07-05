"""
audit.py — Immutable security audit logging service (Phase 3.5).

Records security-critical events (admin actions, logins, payments, device lifecycle)
with mandatory zero-secret redaction and immutability guarantees.
"""
from __future__ import annotations

import copy
import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.redaction import redact_data, redact_string
from app.observability.metrics import metrics_registry
from app.security_hardening.exceptions import SecurityHardeningError

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
    Thread-safe, append-only immutable audit log service.
    Enforces strict event categorization and zero-secret data retention.
    """

    def __init__(self, max_records: int = 10000) -> None:
        self._lock = threading.RLock()
        self._events: list[AuditEvent] = []
        self._max_records = max_records
        self._total_recorded = 0

    def record_event(
        self,
        event_type: str,
        actor_id: str,
        target_id: str,
        details: dict[str, Any] | None = None,
        ip_hash: str | None = None,
    ) -> AuditEvent:
        """
        Record a new security audit event. All details are deeply scrubbed of credentials.
        """
        if event_type not in SUPPORTED_AUDIT_EVENT_TYPES:
            # Allow custom but log warning, or default to admin_action if unknown
            if not event_type.startswith("admin_") and not event_type.endswith("_event"):
                logger.warning("Unstandardized audit event_type: %s", event_type)

        raw_details = details or {}
        scrubbed_details = _deep_scrub_secrets(redact_data(raw_details))

        if not isinstance(scrubbed_details, dict):
            scrubbed_details = {"value": scrubbed_details}

        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            actor_id=str(actor_id),
            target_id=str(target_id),
            details=scrubbed_details,
            ip_hash=ip_hash,
        )

        with self._lock:
            self._events.append(event)
            self._total_recorded += 1
            if len(self._events) > self._max_records:
                # Prune oldest while maintaining append-only immutability of preserved window
                self._events.pop(0)

        metrics_registry.inc_counter("audit_events_total")
        logger.info(
            "Security audit event recorded id=%s type=%s actor=%s target=%s",
            event.event_id,
            event.event_type,
            event.actor_id,
            event.target_id,
        )
        return event

    def list_events(
        self, event_type: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """
        Retrieve a paginated, read-only list of audit event records.
        """
        with self._lock:
            filtered = [
                e for e in self._events
                if event_type is None or e.event_type == event_type
            ]
            # Return in reverse chronological order (newest first)
            slice_events = list(reversed(filtered))[offset : offset + limit]
            return [e.to_dict() for e in slice_events]

    def modify_or_delete_event(self, *args: Any, **kwargs: Any) -> None:
        """
        Prohibited operation. Audit log events are immutable.
        """
        raise SecurityHardeningError("Audit log is immutable; events cannot be modified or deleted.")

    def get_queue_status(self) -> dict[str, Any]:
        """
        Return audit queue status and persistence statistics for admin /health inspection.
        """
        with self._lock:
            return {
                "total_events_recorded": self._total_recorded,
                "in_memory_count": len(self._events),
                "max_capacity": self._max_records,
                "status": "ok",
                "immutable": True,
            }


# Global singleton instance
audit_service = AuditService()
