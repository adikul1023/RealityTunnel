"""
app/core/profiles.py — Explicit environment profiles (Phase 3.1.4).

Supports explicit profiles: development, testing, staging, production.
Enforces that no environment profile is implicitly inferred as production.
"""
from __future__ import annotations

from enum import Enum


class EnvironmentProfile(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"

    @property
    def is_production(self) -> bool:
        return self == EnvironmentProfile.PRODUCTION

    @property
    def is_testing(self) -> bool:
        return self == EnvironmentProfile.TESTING

    @property
    def is_development(self) -> bool:
        return self == EnvironmentProfile.DEVELOPMENT

    @property
    def is_staging(self) -> bool:
        return self == EnvironmentProfile.STAGING


def parse_environment_profile(value: str | None) -> EnvironmentProfile:
    """
    Parse and validate an explicit environment profile string.
    Never implicitly infers or defaults to production.
    Raises ValueError if the profile is unrecognized or empty.
    """
    if not value:
        raise ValueError(
            "Environment profile must be explicitly set (development, testing, staging, production). "
            "Empty or missing environment configuration is prohibited."
        )

    clean_val = value.strip().lower()
    try:
        return EnvironmentProfile(clean_val)
    except ValueError as exc:
        valid_profiles = ", ".join(p.value for p in EnvironmentProfile)
        raise ValueError(
            f"Invalid environment profile '{value}'. Allowed profiles: {valid_profiles}. "
            f"No implicit profile inference is permitted."
        ) from exc
