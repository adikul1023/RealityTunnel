#!/usr/bin/env python3
"""
generate_signing_keys.py — One-time production Ed25519 signing key provisioning tool.

SECURITY FIX (Docker/Deployment Audit — "no mechanism to provision production signing keys"):
`docker-compose.prod.yml` never mounted a `dev_keys/` volume into the `billing-api` container,
and `.dockerignore` correctly excludes `dev_keys/` from the Docker build context (so dev-generated
keys are never baked into an image layer). Combined with `app/core/startup_validator.py` explicitly
FORBIDDING key auto-generation in production (`ENVIRONMENT=production`), the shipped production
deployment had NO way to ever supply the Ed25519 keypairs the app requires to boot — every
production container would fail at startup with:

    RuntimeError: Production Guard Failure: Ed25519 JWT signing key PEM file(s) missing or empty
    on disk (provision under dev_keys/ before startup; there is no JWT_SECRET env var)

This script is the operator-run tool that closes that gap: it generates both required Ed25519
keypairs (customer JWT + admin JWT) directly on the HOST filesystem, in the exact directory layout
`app/security/jwt_service.py` and `app/security/admin_jwt.py` expect, and applies the same
restrictive file permissions the application's own auto-generation path would apply in development.
`docker-compose.prod.yml` bind-mounts this host directory read-only into the container at
`/app/dev_keys`, so the running (non-root, read-only-root-filesystem) container can read but never
regenerate/overwrite these keys.

Usage (run ONCE on the production host, before the very first `docker compose up`):

    python scripts/generate_signing_keys.py

Re-running this script is a NO-OP for any key that already exists on disk (it will never silently
overwrite an existing production signing key -- rotating keys is an explicit, separate operation
that invalidates every outstanding token and must be done deliberately, not accidentally via
re-running a provisioning script).
"""

from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

_KEY_PAIRS: tuple[tuple[str, Path, Path], ...] = (
    (
        "customer JWT",
        _PROJECT_ROOT / "dev_keys" / "ed25519_private.pem",
        _PROJECT_ROOT / "dev_keys" / "ed25519_public.pem",
    ),
    (
        "admin JWT",
        _PROJECT_ROOT / "dev_keys" / "admin" / "admin_ed25519_private.pem",
        _PROJECT_ROOT / "dev_keys" / "admin" / "admin_ed25519_public.pem",
    ),
)


def _apply_restrictive_permissions(
    private_key_path: Path, public_key_path: Path
) -> None:
    """
    Mirror the exact permission scheme app/security/jwt_service.py and admin_jwt.py apply when
    auto-generating keys in development: private key readable/writable by owner only (0600),
    public key readable by owner/group/other but not writable by group/other (0644).
    Best-effort on POSIX; a documented no-op on Windows (NTFS ACLs must be set out-of-band there).
    """
    if os.name != "posix":
        print(
            f"  (skipping POSIX chmod on {os.name} -- set restrictive NTFS ACLs on "
            f"{private_key_path.parent} manually before deploying to a Linux production host)"
        )
        return
    try:
        os.chmod(private_key_path, stat.S_IRUSR | stat.S_IWUSR)
        os.chmod(
            public_key_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH
        )
    except OSError as exc:
        print(f"  WARNING: failed to chmod key files: {exc}", file=sys.stderr)


def _generate_keypair(
    label: str, private_key_path: Path, public_key_path: Path, *, force: bool
) -> bool:
    if private_key_path.exists() and public_key_path.exists() and not force:
        print(
            f"[skip] {label} keypair already exists at {private_key_path.parent} -- not overwriting."
        )
        return False

    if (private_key_path.exists() or public_key_path.exists()) and not force:
        print(
            f"[error] {label}: only one of the two key files exists under {private_key_path.parent}. "
            "Refusing to proceed automatically -- resolve this manually (re-run with --force to "
            "regenerate both, understanding this invalidates every outstanding token of this type).",
            file=sys.stderr,
        )
        sys.exit(1)

    private_key_path.parent.mkdir(parents=True, exist_ok=True)

    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_key_path.write_bytes(private_pem)
    public_key_path.write_bytes(public_pem)
    _apply_restrictive_permissions(private_key_path, public_key_path)

    print(f"[ok]   {label} keypair generated at {private_key_path.parent}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Provision production Ed25519 signing keys for RealityTunnel billing-server."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Regenerate keys even if they already exist. DANGEROUS: this immediately invalidates "
            "every outstanding access/refresh/admin token signed with the old key. Only use this "
            "as part of a deliberate, planned key-rotation procedure."
        ),
    )
    args = parser.parse_args()

    if args.force:
        print(
            "!! --force specified: existing keys (if any) will be overwritten. This invalidates "
            "every outstanding token signed with the previous key(s). !!"
        )

    any_generated = False
    for label, private_path, public_path in _KEY_PAIRS:
        generated = _generate_keypair(
            label, private_path, public_path, force=args.force
        )
        any_generated = any_generated or generated

    print()
    if any_generated:
        print(
            "Done. Keys now exist under 'dev_keys/'. Ensure docker-compose.prod.yml bind-mounts "
            "this directory read-only into the billing-api container at /app/dev_keys before "
            "starting the production stack."
        )
    else:
        print("No keys were generated (all already present). Nothing to do.")


if __name__ == "__main__":
    main()
