"""
app/core/fingerprint.py — Deterministic configuration fingerprinting (Phase 3.1.7).

Computes a deterministic summary of runtime configuration:
  - Environment
  - Feature flags
  - Enabled providers
  - Version
  - Git commit hash (if available)

Strictly guarantees zero secret values are ever included.
Exposed exclusively to authenticated administrators via health endpoints.
"""
from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.core.feature_flags import FeatureFlags


def _get_git_commit() -> str:
    """Attempt to retrieve the short Git commit hash of the deployed repository."""
    env_commit = os.environ.get("GIT_COMMIT") or os.environ.get("COMMIT_SHA")
    if env_commit:
        return env_commit[:8]

    try:
        project_root = Path(__file__).resolve().parent.parent.parent
        output = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project_root,
            stderr=subprocess.DEVNULL,
            timeout=1.0,
            text=True,
        )
        return output.strip()
    except Exception:
        return "unknown"


def compute_configuration_fingerprint(
    settings: Settings | None = None,
    flags: FeatureFlags | None = None,
) -> dict[str, Any]:
    """
    Compute deterministic runtime fingerprint without sensitive secrets.
    """
    if settings is None:
        settings = get_settings()
    if flags is None:
        flags = FeatureFlags.from_env()

    enabled_providers: list[str] = []
    if flags.payments_enabled and settings.razorpay_key_id:
        enabled_providers.append("razorpay")
    if flags.provisioning_enabled and settings.marzban_base_url:
        enabled_providers.append("marzban")

    return {
        "environment": settings.environment,
        "version": settings.app_version,
        "git_commit": _get_git_commit(),
        "feature_flags": flags.to_dict(),
        "enabled_providers": sorted(enabled_providers),
        "debug_mode": settings.debug,
    }
