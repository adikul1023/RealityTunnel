"""
app/core/secret_registry.py — Central secret registry (Phase 3.1.2).

Provides a single authoritative registry for all application secrets.
Every secret declares:
  - name
  - description
  - required in production
  - rotation recommendation
  - validation function
Eliminates duplicated secret loading and enables systematic startup audits.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

from app.config import Settings, get_settings


@dataclass
class SecretDefinition:
    name: str
    description: str
    required_in_production: bool
    rotation_recommendation: str
    validation_function: Callable[[str | None], bool]
    value: str | None = None


class SecretRegistry:
    """Singleton central registry managing application secrets."""
    def __init__(self) -> None:
        self._secrets: dict[str, SecretDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        required_in_production: bool,
        rotation_recommendation: str,
        validation_function: Callable[[str | None], bool],
    ) -> None:
        self._secrets[name] = SecretDefinition(
            name=name,
            description=description,
            required_in_production=required_in_production,
            rotation_recommendation=rotation_recommendation,
            validation_function=validation_function,
        )

    def get(self, name: str) -> str | None:
        def_obj = self._secrets.get(name)
        return def_obj.value if def_obj else None

    def get_definition(self, name: str) -> SecretDefinition | None:
        return self._secrets.get(name)

    def get_all_definitions(self) -> list[SecretDefinition]:
        return list(self._secrets.values())

    def load_from_settings(self, settings: Settings | None = None) -> None:
        """Load all secret values once from application settings and disk."""
        if settings is None:
            settings = get_settings()

        # Database password
        if "postgres_password" in self._secrets:
            self._secrets["postgres_password"].value = settings.postgres_password

        # Secret key / cookie signing key / encryption key
        if "secret_key" in self._secrets:
            self._secrets["secret_key"].value = settings.secret_key
        if "cookie_signing_key" in self._secrets:
            self._secrets["cookie_signing_key"].value = settings.secret_key
        if "encryption_key" in self._secrets:
            self._secrets["encryption_key"].value = settings.secret_key

        # Marzban API token
        if "marzban_api_token" in self._secrets:
            self._secrets["marzban_api_token"].value = settings.marzban_api_token

        # Razorpay keys
        if "razorpay_key_id" in self._secrets:
            self._secrets["razorpay_key_id"].value = settings.razorpay_key_id
        if "razorpay_key_secret" in self._secrets:
            self._secrets["razorpay_key_secret"].value = settings.razorpay_key_secret
        if "razorpay_webhook_secret" in self._secrets:
            self._secrets["razorpay_webhook_secret"].value = settings.razorpay_webhook_secret

        # Check disk/environment for PEM keys
        project_root = Path(__file__).resolve().parent.parent.parent
        dev_keys_dir = project_root / "dev_keys"
        admin_keys_dir = dev_keys_dir / "admin"

        if "jwt_private_key" in self._secrets:
            priv_path = dev_keys_dir / "ed25519_private.pem"
            if priv_path.exists():
                self._secrets["jwt_private_key"].value = priv_path.read_text(encoding="utf-8")
        if "jwt_public_key" in self._secrets:
            pub_path = dev_keys_dir / "ed25519_public.pem"
            if pub_path.exists():
                self._secrets["jwt_public_key"].value = pub_path.read_text(encoding="utf-8")
        if "admin_jwt_private_key" in self._secrets:
            admin_priv_path = admin_keys_dir / "admin_ed25519_private.pem"
            if admin_priv_path.exists():
                self._secrets["admin_jwt_private_key"].value = admin_priv_path.read_text(encoding="utf-8")
        if "admin_jwt_public_key" in self._secrets:
            admin_pub_path = admin_keys_dir / "admin_ed25519_public.pem"
            if admin_pub_path.exists():
                self._secrets["admin_jwt_public_key"].value = admin_pub_path.read_text(encoding="utf-8")


# ── Default Validation Functions ─────────────────────────────────────────────

def _validate_non_empty_secret(val: str | None) -> bool:
    return bool(val and len(val.strip()) > 0)


def _validate_strong_secret(val: str | None) -> bool:
    if not val or len(val.strip()) < 16:
        return False
    lower = val.lower()
    if any(placeholder in lower for placeholder in ("change_me", "default", "example", "secret", "password", "test", "dev-only")):
        return False
    return True


def _validate_pem_key(val: str | None) -> bool:
    if not val:
        return False
    return "BEGIN " in val and "END " in val


# ── Global Singleton Registry Initialization ─────────────────────────────────

secret_registry = SecretRegistry()

secret_registry.register(
    name="jwt_private_key",
    description="Ed25519 private signing key for customer JWT tokens.",
    required_in_production=True,
    rotation_recommendation="Annual rotation or immediately upon suspected compromise.",
    validation_function=_validate_pem_key,
)
secret_registry.register(
    name="jwt_public_key",
    description="Ed25519 public verification key for customer JWT tokens.",
    required_in_production=True,
    rotation_recommendation="Synchronized with private key rotation.",
    validation_function=_validate_pem_key,
)
secret_registry.register(
    name="admin_jwt_private_key",
    description="Ed25519 private signing key for administrator JWT tokens.",
    required_in_production=True,
    rotation_recommendation="Annual rotation or immediately upon suspected compromise.",
    validation_function=_validate_pem_key,
)
secret_registry.register(
    name="admin_jwt_public_key",
    description="Ed25519 public verification key for administrator JWT tokens.",
    required_in_production=True,
    rotation_recommendation="Synchronized with private key rotation.",
    validation_function=_validate_pem_key,
)
secret_registry.register(
    name="postgres_password",
    description="Database authentication secret for PostgreSQL.",
    required_in_production=True,
    rotation_recommendation="Quarterly rotation via automated credentials management.",
    validation_function=_validate_non_empty_secret,
)
secret_registry.register(
    name="secret_key",
    description="Master secret key for general cryptographic HMAC and token operations.",
    required_in_production=True,
    rotation_recommendation="Annual rotation.",
    validation_function=_validate_strong_secret,
)
secret_registry.register(
    name="cookie_signing_key",
    description="HMAC key used for signing session and state cookies.",
    required_in_production=True,
    rotation_recommendation="Annual rotation.",
    validation_function=_validate_strong_secret,
)
secret_registry.register(
    name="encryption_key",
    description="Symmetric encryption key for sensitive data at rest.",
    required_in_production=True,
    rotation_recommendation="Annual rotation with key wrapping.",
    validation_function=_validate_strong_secret,
)
secret_registry.register(
    name="marzban_api_token",
    description="Bearer access token for communicating with the Marzban VPN provisioning node.",
    required_in_production=False,  # Conditional on PROVISIONING_ENABLED
    rotation_recommendation="Quarterly rotation.",
    validation_function=_validate_non_empty_secret,
)
secret_registry.register(
    name="razorpay_key_id",
    description="Public API key identifier for Razorpay payment gateway.",
    required_in_production=False,  # Conditional on PAYMENTS_ENABLED
    rotation_recommendation="Annual rotation.",
    validation_function=_validate_non_empty_secret,
)
secret_registry.register(
    name="razorpay_key_secret",
    description="Secret API key for Razorpay payment gateway order signing.",
    required_in_production=False,  # Conditional on PAYMENTS_ENABLED
    rotation_recommendation="Annual rotation.",
    validation_function=_validate_strong_secret,
)
secret_registry.register(
    name="razorpay_webhook_secret",
    description="HMAC secret for verifying Razorpay webhook payload signatures.",
    required_in_production=False,  # Conditional on PAYMENTS_ENABLED and WEBHOOKS_ENABLED
    rotation_recommendation="Annual rotation.",
    validation_function=_validate_strong_secret,
)
