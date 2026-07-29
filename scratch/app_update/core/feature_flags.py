"""
app/core/feature_flags.py — Strongly typed feature flags (Phase 3.1.8).

Replaces magic strings with explicit boolean flags for major subsystem activation:
  - PAYMENTS_ENABLED
  - PROVISIONING_ENABLED
  - WEBHOOKS_ENABLED
  - ADMIN_API_ENABLED
  - BACKGROUND_JOBS_ENABLED
  - METRICS_ENABLED
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Mapping


def _parse_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    val_str = str(value).strip().lower()
    if val_str in ("1", "true", "yes", "on", "enable", "enabled"):
        return True
    if val_str in ("0", "false", "no", "off", "disable", "disabled"):
        return False
    return default


@dataclass(frozen=True)
class FeatureFlags:
    payments_enabled: bool = True
    provisioning_enabled: bool = True
    webhooks_enabled: bool = True
    admin_api_enabled: bool = True
    background_jobs_enabled: bool = True
    metrics_enabled: bool = True

    @classmethod
    def from_env(cls, env: Mapping[str, Any] | None = None) -> "FeatureFlags":
        """Load feature flags from environment mapping (or os.environ by default)."""
        source = env if env is not None else os.environ
        return cls(
            payments_enabled=_parse_bool(source.get("PAYMENTS_ENABLED", True)),
            provisioning_enabled=_parse_bool(source.get("PROVISIONING_ENABLED", True)),
            webhooks_enabled=_parse_bool(source.get("WEBHOOKS_ENABLED", True)),
            admin_api_enabled=_parse_bool(source.get("ADMIN_API_ENABLED", True)),
            background_jobs_enabled=_parse_bool(source.get("BACKGROUND_JOBS_ENABLED", True)),
            metrics_enabled=_parse_bool(source.get("METRICS_ENABLED", True)),
        )

    def to_dict(self) -> dict[str, bool]:
        """Export as dictionary for startup reporting and fingerprinting."""
        return {
            "PAYMENTS_ENABLED": self.payments_enabled,
            "PROVISIONING_ENABLED": self.provisioning_enabled,
            "WEBHOOKS_ENABLED": self.webhooks_enabled,
            "ADMIN_API_ENABLED": self.admin_api_enabled,
            "BACKGROUND_JOBS_ENABLED": self.background_jobs_enabled,
            "METRICS_ENABLED": self.metrics_enabled,
        }
