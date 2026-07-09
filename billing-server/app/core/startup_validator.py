"""
app/core/startup_validator.py — Startup configuration validation & reporting (Phases 3.1.3, 3.1.5, 3.1.9).

Enforces fail-fast startup validation before FastAPI accepts HTTP requests:
  - Validates keypairs, database configuration, external gateways, secret lengths, and writable directories.
  - Enforces production guards (rejection of placeholders, debug mode, test keys, localhost callbacks).
  - Generates a structured startup Configuration Report with zero leaked secrets.
"""

from __future__ import annotations

import logging
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.core.feature_flags import FeatureFlags
from app.core.fingerprint import compute_configuration_fingerprint
from app.core.profiles import EnvironmentProfile, parse_environment_profile
from app.core.secret_registry import SecretDefinition, secret_registry

logger = logging.getLogger(__name__)

# Ed25519 PEM paths used by jwt_service.py and admin_jwt.py (not env vars — must exist on disk).
_ED25519_KEY_REL_PATHS: tuple[tuple[str, str], ...] = (
    ("customer JWT private key", "dev_keys/ed25519_private.pem"),
    ("customer JWT public key", "dev_keys/ed25519_public.pem"),
    ("admin JWT private key", "dev_keys/admin/admin_ed25519_private.pem"),
    ("admin JWT public key", "dev_keys/admin/admin_ed25519_public.pem"),
)

_PRIVATE_KEY_REL_PATHS: tuple[str, ...] = (
    "dev_keys/ed25519_private.pem",
    "dev_keys/admin/admin_ed25519_private.pem",
)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def collect_missing_ed25519_key_files(project_root: Path | None = None) -> list[str]:
    """
    Return relative paths of Ed25519 PEM files that are absent or empty on disk.
    Used by production startup validation (Finding H-1): JWT signing reads these files,
    not JWT_SECRET or any other environment variable.
    """
    root = project_root or _project_root()
    missing: list[str] = []
    for _label, rel_path in _ED25519_KEY_REL_PATHS:
        key_path = root / rel_path
        if not key_path.is_file() or key_path.stat().st_size == 0:
            missing.append(rel_path)
    return missing


def _is_secret_required(
    definition: SecretDefinition,
    profile: EnvironmentProfile,
    flags: FeatureFlags,
) -> bool:
    """Return True when a registry secret must pass validation for the current profile/flags."""
    if not profile.is_production:
        return False
    if definition.required_in_production:
        return True
    if definition.name == "marzban_api_token" and flags.provisioning_enabled:
        return True
    if (
        definition.name in ("razorpay_key_id", "razorpay_key_secret")
        and flags.payments_enabled
    ):
        return True
    if (
        definition.name == "razorpay_webhook_secret"
        and flags.payments_enabled
        and flags.webhooks_enabled
    ):
        return True
    return False


def _validate_required_secrets(
    profile: EnvironmentProfile,
    flags: FeatureFlags,
    checks: dict[str, bool],
    errors: list[str],
) -> None:
    """
    Finding C-3: iterate the central secret registry and enforce each required secret's
    validation_function. Never include secret values in error messages — names only.
    """
    if not profile.is_production:
        return
    for definition in secret_registry.get_all_definitions():
        if not _is_secret_required(definition, profile, flags):
            continue
        valid = definition.validation_function(definition.value)
        checks[f"Secret: {definition.name}"] = valid
        if not valid:
            errors.append(
                f"Production secret validation failed for '{definition.name}' "
                f"(required; value must meet security requirements)."
            )


def _check_private_key_file_permissions(
    project_root: Path | None = None,
) -> tuple[bool, list[str]]:
    """
    Finding H-6: private key PEM files must not grant group/other access (mode & 0o077 == 0).
    Returns (all_secure, list of insecure relative paths).
    """
    root = project_root or _project_root()
    insecure: list[str] = []
    for rel_path in _PRIVATE_KEY_REL_PATHS:
        key_path = root / rel_path
        if not key_path.is_file():
            continue
        if os.stat(key_path).st_mode & 0o077:
            insecure.append(rel_path)
    return len(insecure) == 0, insecure


class ConfigurationError(RuntimeError):
    """Raised when startup configuration validation fails. Halts application boot immediately."""

    pass


@dataclass
class ConfigurationReport:
    status: str
    checks: dict[str, bool] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    production_checks: dict[str, bool] = field(default_factory=dict)
    fingerprint: dict[str, Any] = field(default_factory=dict)

    def to_string(self) -> str:
        lines = [
            "\n══════════════════════════════════════════════════════════════",
            "            RealityTunnel Configuration Report                ",
            "══════════════════════════════════════════════════════════════",
            f" Status: {self.status.upper()}",
            "──────────────────────────────────────────────────────────────",
            " Configuration Status:",
        ]
        for name, ok in self.checks.items():
            mark = "✓" if ok else "✗"
            lines.append(f"   {mark} {name}")

        if self.production_checks:
            lines.append(
                "──────────────────────────────────────────────────────────────"
            )
            lines.append(" Production Guards:")
            for name, ok in self.production_checks.items():
                mark = "✓" if ok else "✗"
                lines.append(f"   {mark} {name}")

        if self.warnings:
            lines.append(
                "──────────────────────────────────────────────────────────────"
            )
            lines.append(" Warnings:")
            for warn in self.warnings:
                lines.append(f"   ! {warn}")

        lines.append("──────────────────────────────────────────────────────────────")
        lines.append(f" Environment: {self.fingerprint.get('environment', 'unknown')}")
        lines.append(f" Version:     {self.fingerprint.get('version', 'unknown')}")
        lines.append(f" Commit:      {self.fingerprint.get('git_commit', 'unknown')}")
        lines.append(
            f" Providers:   {', '.join(self.fingerprint.get('enabled_providers', [])) or 'None'}"
        )
        lines.append("══════════════════════════════════════════════════════════════\n")
        return "\n".join(lines)


def validate_startup_configuration(
    settings: Settings | None = None,
    flags: FeatureFlags | None = None,
) -> ConfigurationReport:
    """
    Perform exhaustive validation of runtime settings, secrets, and environment profiles.
    Raises ConfigurationError immediately if any required check fails.
    """
    if settings is None:
        settings = get_settings()
    if flags is None:
        flags = FeatureFlags.from_env()

    # Parse and validate explicit environment profile (no implicit production)
    try:
        profile = parse_environment_profile(settings.environment)
    except ValueError as exc:
        raise ConfigurationError(str(exc)) from exc

    # Load and register secret values
    secret_registry.load_from_settings(settings)

    checks: dict[str, bool] = {}
    warnings: list[str] = []
    prod_checks: dict[str, bool] = {}
    errors: list[str] = []

    # 1. Database Configuration Check
    db_ok = bool(
        settings.postgres_host
        and settings.postgres_user
        and settings.postgres_db
        and settings.database_url.get_secret_value()
    )
    checks["Database"] = db_ok
    if not db_ok:
        errors.append("Database URL or connection credentials incomplete.")

    # 2. JWT Keypair Check
    jwt_priv = secret_registry.get("jwt_private_key")
    jwt_pub = secret_registry.get("jwt_public_key")
    jwt_ok = bool(jwt_priv and jwt_pub and "BEGIN " in jwt_priv and "BEGIN " in jwt_pub)
    checks["JWT Keys"] = jwt_ok
    if not jwt_ok:
        if profile.is_production:
            errors.append(
                "Customer JWT Ed25519 signing keypair missing or invalid in production."
            )
        else:
            warnings.append(
                "Customer JWT keypair not found on disk; will be auto-generated in dev mode."
            )

    # 3. Admin Keypair Check
    admin_priv = secret_registry.get("admin_jwt_private_key")
    admin_pub = secret_registry.get("admin_jwt_public_key")
    admin_ok = bool(
        admin_priv and admin_pub and "BEGIN " in admin_priv and "BEGIN " in admin_pub
    )
    checks["Admin Keys"] = admin_ok
    if not admin_ok:
        if profile.is_production:
            errors.append(
                "Admin JWT Ed25519 signing keypair missing or invalid in production."
            )
        else:
            warnings.append(
                "Admin JWT keypair not found on disk; will be auto-generated in dev mode."
            )

    # 4. Marzban Provisioning Gateway Check
    if flags.provisioning_enabled:
        rpc_url = settings.marzban_rpc_url
        pub_url = settings.marzban_base_url
        marz_ok = bool(
            (rpc_url and rpc_url.startswith(("http://", "https://")))
            or (pub_url and pub_url.startswith(("http://", "https://")))
        )
        checks["Marzban Gateway"] = marz_ok
        if not marz_ok:
            if profile.is_production:
                errors.append(
                    "PROVISIONING_ENABLED is true but neither marzban_rpc_url nor marzban_base_url is properly configured in production."
                )
            else:
                warnings.append(
                    "PROVISIONING_ENABLED is true but Marzban gateways not configured in dev mode."
                )
    else:
        checks["Marzban Gateway (Disabled)"] = True

    # 5. Razorpay Payment Gateway Check
    if flags.payments_enabled:
        rzp_ok = bool(settings.razorpay_key_id and settings.razorpay_key_secret)
        checks["Razorpay Gateway"] = rzp_ok
        if not rzp_ok:
            if profile.is_production:
                errors.append(
                    "PAYMENTS_ENABLED is true but Razorpay API credentials are incomplete in production."
                )
            else:
                warnings.append(
                    "PAYMENTS_ENABLED is true but Razorpay API credentials not configured in dev mode."
                )
        if flags.webhooks_enabled:
            wh_ok = bool(settings.razorpay_webhook_secret)
            checks["Razorpay Webhooks"] = wh_ok
            if not wh_ok:
                if profile.is_production:
                    errors.append(
                        "WEBHOOKS_ENABLED is true but razorpay_webhook_secret is missing in production."
                    )
                else:
                    warnings.append(
                        "WEBHOOKS_ENABLED is true but razorpay_webhook_secret not configured in dev mode."
                    )
    else:
        checks["Razorpay Gateway (Disabled)"] = True

    # 6. Writable Directories Check
    #
    # DEPLOYMENT FIX: this check previously ALWAYS tested write access to dev_keys/, which is
    # correct in development (where missing Ed25519 keys are auto-generated on first boot) but
    # is fundamentally incompatible with the security-hardened production deployment pattern:
    # dev_keys/ MUST be mounted read-only in production (see docker-compose.prod.yml) so that a
    # compromised/malicious process running inside the container can never overwrite its own
    # signing keys. Enforcing writability there in production would force operators to choose
    # between "app can boot" and "signing keys are immutable from inside the container" -- a
    # false choice that should never exist.
    #
    # Fix: only require dev_keys/ to be writable outside production (where auto-generation is a
    # deliberate convenience feature). In every profile, verify the directories the application
    # genuinely needs to write to at runtime (backups/, brain/) are writable -- these are always
    # backed by writable volumes per docker-compose.prod.yml, independent of environment.
    writable_targets: list[Path] = [
        _project_root() / "backups",
        _project_root() / "brain",
    ]
    if not profile.is_production:
        writable_targets.append(_project_root() / "dev_keys")

    all_writable = True
    for target_dir in writable_targets:
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            test_file = target_dir / ".write_test"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink(missing_ok=True)
        except Exception as exc:
            all_writable = False
            errors.append(
                f"Directory write permission test failed for '{target_dir}': {exc}"
            )
    checks["Writable Directories"] = all_writable

    # 7. Production Guards (Strict Phase 3.1.5 enforcement)
    if profile.is_production:
        # Secret registry validation (Finding C-3 — dead validation wired up)
        _validate_required_secrets(profile, flags, checks, errors)

        # Ed25519 PEM key files on disk (Finding H-1 — replaces dead JWT_SECRET env var)
        missing_key_files = collect_missing_ed25519_key_files()
        key_files_on_disk = len(missing_key_files) == 0
        prod_checks["Ed25519 Key Files on Disk"] = key_files_on_disk
        if not key_files_on_disk:
            errors.append(
                "Production Guard Failure: Ed25519 JWT signing key PEM file(s) missing or empty "
                f"on disk (provision under dev_keys/ before startup; there is no JWT_SECRET env "
                f"var): {', '.join(missing_key_files)}"
            )

        # Debug mode check
        no_debug = not settings.debug
        prod_checks["No Debug Mode"] = no_debug
        if not no_debug:
            errors.append(
                "Production Guard Failure: debug mode must be False in production."
            )

        # Default / placeholder secret rejection
        secret_key_val = settings.secret_key.get_secret_value() if settings.secret_key else ""
        valid_secret_key = (
            secret_key_val != "CHANGE_ME_BEFORE_PRODUCTION"
            and len(secret_key_val) >= 32
            and "placeholder" not in secret_key_val.lower()
            and "default" not in secret_key_val.lower()
            and "example" not in secret_key_val.lower()
            and "test" not in secret_key_val.lower()
        )
        prod_checks["Strong Secret Key"] = valid_secret_key
        if not valid_secret_key:
            errors.append(
                "Production Guard Failure: secret_key is default, short (<32 chars), or placeholder."
            )

        # Test payment & webhook keys rejection
        rzp_id = (settings.razorpay_key_id or "").lower()
        rzp_sec = (settings.razorpay_key_secret.get_secret_value() if settings.razorpay_key_secret else "").lower()
        rzp_wh = (settings.razorpay_webhook_secret.get_secret_value() if settings.razorpay_webhook_secret else "").lower()
        no_test_keys = not any(
            val.startswith("rzp_test") or "test_" in val or "placeholder" in val
            for val in (rzp_id, rzp_sec, rzp_wh)
            if val
        )
        prod_checks["No Test Payment/Webhook Keys"] = no_test_keys
        if not no_test_keys:
            errors.append(
                "Production Guard Failure: test payment or webhook keys detected in production."
            )

        # HTTPS / Localhost callback URL check
        if flags.provisioning_enabled:
            # 1. Validate Public URL (Must be HTTPS and not localhost)
            pub_url = (settings.marzban_base_url or "").lower()
            if pub_url:
                no_localhost_pub = "localhost" not in pub_url and "127.0.0.1" not in pub_url
                https_pub = pub_url.startswith("https://")
                prod_checks["Marzban Public URL (HTTPS)"] = bool(no_localhost_pub and https_pub)
                if not (no_localhost_pub and https_pub):
                    errors.append(
                        "Production Guard Failure: marzban_base_url must be a valid public HTTPS URL and not localhost."
                    )

            # 2. Validate RPC URL (Must be HTTP/HTTPS and internal)
            rpc_url = (settings.marzban_rpc_url or "").lower()
            if rpc_url:
                # We expect the RPC URL to be an internal Docker name or localhost/IP in some topologies, 
                # so we don't strictly ban localhost, but we DO enforce it's not a generic public HTTP.
                # Actually, to be generic, we just ensure it's provided. 
                is_http = rpc_url.startswith(("http://", "https://"))
                prod_checks["Marzban RPC URL Valid"] = is_http
                if not is_http:
                    errors.append(
                        "Production Guard Failure: marzban_rpc_url must be a valid HTTP/HTTPS internal URL."
                    )
        else:
            prod_checks["HTTPS / No Localhost Gateways"] = True

        # Key file permissions check on POSIX (Finding H-6)
        if os.name == "posix":
            perm_ok, insecure_key_paths = _check_private_key_file_permissions()
            prod_checks["Secure Key Permissions"] = perm_ok
            if not perm_ok:
                errors.append(
                    "Production Guard Failure: insecure private key file permissions "
                    f"(mode must not grant group/other access): {', '.join(insecure_key_paths)}"
                )

        # Rate limit backend check (Finding H-3): in-memory rate limiting is process-local,
        # resets on every restart, and does not enforce limits consistently across
        # horizontally-scaled replicas. Production must use the Redis-backed store.
        rate_limit_backend_val = (
            (getattr(settings, "rate_limit_backend", "memory") or "memory")
            .strip()
            .lower()
        )
        rate_limit_backend_ok = (
            not settings.rate_limit_enabled or rate_limit_backend_val == "redis"
        )
        prod_checks["Redis Rate Limit Backend"] = rate_limit_backend_ok
        if not rate_limit_backend_ok:
            errors.append(
                "Production Guard Failure: rate_limit_backend must be 'redis' in production "
                "(in-memory rate limiting does not work across replicas or survive restarts)."
            )

    fingerprint = compute_configuration_fingerprint(settings, flags)
    status = "error" if errors else "ok"
    report = ConfigurationReport(
        status=status,
        checks=checks,
        warnings=warnings,
        production_checks=prod_checks,
        fingerprint=fingerprint,
    )

    if errors:
        error_msg = f"Startup Configuration Validation Failed:\n" + "\n".join(
            f"  ✗ {e}" for e in errors
        )
        logger.error("%s\n%s", error_msg, report.to_string())
        raise ConfigurationError(error_msg)

    logger.info("Startup Configuration Validated Successfully.\n%s", report.to_string())
    return report
