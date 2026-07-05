"""
rotation.py — Cryptographic secret rotation service with overlap period support (Phase 3.5).

Manages multi-generation lifecycle for JWT keys, Admin keys, Marzban tokens, payment secrets,
webhook secrets, and master signing keys. Old secrets remain valid during configurable overlap windows.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import settings
from app.observability.metrics import metrics_registry
from app.security_hardening.exceptions import SecretRotationError

logger = logging.getLogger(__name__)

SUPPORTED_SECRET_TYPES = {
    "jwt_key",
    "admin_jwt_key",
    "marzban_token",
    "payment_secret",
    "webhook_secret",
    "master_signing_key",
}


@dataclass
class SecretGeneration:
    """Represents a single versioned generation of a cryptographic secret or token."""
    generation_id: int
    secret_value: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None  # None means actively issuing/signing

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) >= self.expires_at


class SecretRotationService:
    """
    Centralized rotation service for cryptographic secrets and credentials.
    Guarantees seamless key transitions without downtime by supporting overlap periods.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._secrets: dict[str, list[SecretGeneration]] = {}
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        with self._lock:
            now = datetime.now(timezone.utc)
            self._secrets["jwt_key"] = [
                SecretGeneration(1, getattr(settings, "secret_key", "default_jwt_secret"), now)
            ]
            self._secrets["admin_jwt_key"] = [
                SecretGeneration(1, getattr(settings, "admin_jwt_secret", getattr(settings, "secret_key", "default_admin_secret")), now)
            ]
            self._secrets["marzban_token"] = [
                SecretGeneration(1, getattr(settings, "marzban_webhook_secret", "default_marzban_secret"), now)
            ]
            self._secrets["payment_secret"] = [
                SecretGeneration(1, getattr(settings, "razorpay_key_secret", "default_razorpay_secret"), now)
            ]
            self._secrets["webhook_secret"] = [
                SecretGeneration(1, getattr(settings, "razorpay_webhook_secret", "default_webhook_secret"), now)
            ]
            self._secrets["master_signing_key"] = [
                SecretGeneration(1, getattr(settings, "secret_key", "default_master_key"), now)
            ]

    def rotate_secret(self, secret_type: str, new_secret_value: str, overlap_seconds: int = 3600) -> int:
        """
        Rotate a specific secret type to a new value while keeping the previous value valid
        for verification/decryption for `overlap_seconds`.

        Returns:
            The newly created generation ID.
        """
        if secret_type not in SUPPORTED_SECRET_TYPES:
            raise SecretRotationError(f"Unsupported secret type for rotation: {secret_type}")
        if not new_secret_value or not new_secret_value.strip():
            raise SecretRotationError("New secret value must not be empty.")

        with self._lock:
            generations = self._secrets.setdefault(secret_type, [])
            now = datetime.now(timezone.utc)

            # Mark current active generation to expire after overlap window
            if generations:
                current = generations[-1]
                if current.expires_at is None:
                    current.expires_at = now + timedelta(seconds=overlap_seconds)
                new_gen_id = current.generation_id + 1
            else:
                new_gen_id = 1

            new_gen = SecretGeneration(
                generation_id=new_gen_id,
                secret_value=new_secret_value,
                created_at=now,
                expires_at=None,
            )
            generations.append(new_gen)

            # Prune ancient expired generations to prevent memory buildup
            self._secrets[secret_type] = [g for g in generations if not g.is_expired or g.generation_id == new_gen_id]

        metrics_registry.inc_counter("secret_rotations_total")
        logger.info(
            "Secret rotated successfully type=%s new_generation=%d overlap_s=%d",
            secret_type,
            new_gen_id,
            overlap_seconds,
        )
        return new_gen_id

    def get_active_secret(self, secret_type: str) -> str:
        """
        Retrieve the current active secret generation used for signing or outbound issuance.
        """
        if secret_type not in SUPPORTED_SECRET_TYPES:
            raise SecretRotationError(f"Unsupported secret type: {secret_type}")

        with self._lock:
            generations = self._secrets.get(secret_type, [])
            if not generations:
                raise SecretRotationError(f"No secret initialized for type: {secret_type}")
            return generations[-1].secret_value

    def get_valid_secrets(self, secret_type: str) -> list[str]:
        """
        Retrieve all valid secret values (active and overlapping unexpired) for incoming verification.
        """
        if secret_type not in SUPPORTED_SECRET_TYPES:
            raise SecretRotationError(f"Unsupported secret type: {secret_type}")

        with self._lock:
            generations = self._secrets.get(secret_type, [])
            valid = [g.secret_value for g in generations if not g.is_expired]
            if not valid and generations:
                # Fallback to latest even if timestamp expired to prevent total lockout
                valid = [generations[-1].secret_value]
            return valid

    def get_rotation_status(self) -> dict[str, Any]:
        """
        Export non-secret rotation status and generation tracking for admin /health inspection.
        """
        with self._lock:
            active_generations: dict[str, int] = {}
            for stype, gens in self._secrets.items():
                active_generations[stype] = gens[-1].generation_id if gens else 0

            master_gen = active_generations.get("master_signing_key", 1)

            return {
                "current_signing_key_generation": master_gen,
                "active_secret_generations": active_generations,
                "rotation_status": "ok",
                "supported_types": sorted(list(SUPPORTED_SECRET_TYPES)),
            }


# Global singleton instance
secret_rotation_service = SecretRotationService()
