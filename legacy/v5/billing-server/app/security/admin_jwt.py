"""
admin_jwt.py — Independent JWT Engine for RealityTunnel Administrative Access Tokens.

SECURITY & ARCHITECTURAL DECISIONS:
1. Complete Domain Isolation:
   The administrative JWT service operates with an entirely independent Ed25519 signing keypair stored in a separate
   key directory (`dev_keys/admin/admin_ed25519_private.pem` and `admin_ed25519_public.pem`). It never reuses customer keys.
2. Separate Issuer and Audience:
   Admin tokens enforce `iss` ("RealityTunnel Admin") and `aud` ("RealityTunnel Admin Panel"). This guarantees that a customer
   access token presented to an admin route (or vice versa) fails verification immediately at the signature/issuer layer.
3. 15-Minute Lifetime (`ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES = 15`):
   Limits exposure of bearer tokens while keeping admin API requests stateless.
4. Minimal Admin Claims:
   Contains `sub` (admin UUID string), `username`, `role` ("super_admin" or "admin"), and RFC 7519 registered claims.
"""
from __future__ import annotations

import logging
import os
import secrets
import stat
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.config import settings
from app.services.exceptions import (
    InvalidAdminTokenError,
    AdminTokenExpiredError,
)

logger = logging.getLogger(__name__)

ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
ADMIN_JWT_ALGORITHM: str = "EdDSA"


@dataclass(frozen=True)
class AdminTokenClaims:
    """
    Typed representation of decoded Admin Access Token claims.
    """
    sub: str        # Admin UUID string
    username: str   # Admin username
    role: str       # Admin role ("super_admin" or "admin")
    iss: str        # Issuer
    aud: str        # Audience
    iat: int        # Issued At timestamp
    nbf: int        # Not Before timestamp
    exp: int        # Expiration timestamp
    jti: str        # Unique JWT ID

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdminTokenClaims:
        required_keys = {"sub", "username", "role", "iss", "aud", "iat", "nbf", "exp", "jti"}
        missing = required_keys - data.keys()
        if missing:
            raise ValueError(f"Missing required Admin JWT claims: {sorted(list(missing))}")
        
        return cls(
            sub=str(data["sub"]),
            username=str(data["username"]),
            role=str(data["role"]),
            iss=str(data["iss"]),
            aud=str(data["aud"]),
            iat=int(data["iat"]),
            nbf=int(data["nbf"]),
            exp=int(data["exp"]),
            jti=str(data["jti"]),
        )


class AdminJWTService:
    """
    Dedicated engine for issuing and verifying Ed25519 signed Administrative JWTs.
    Strictly isolated from customer JWTService and customer keys.
    """

    def __init__(
        self,
        keys_dir: Path | str | None = None,
        environment: str | None = None,
        issuer: str | None = None,
        audience: str | None = None,
    ) -> None:
        if environment is None:
            self.environment = settings.environment
        else:
            self.environment = environment

        self.issuer = issuer if issuer is not None else settings.admin_jwt_issuer
        self.audience = audience if audience is not None else settings.admin_jwt_audience

        if keys_dir is None:
            self.keys_dir = Path(__file__).resolve().parent.parent.parent / "dev_keys" / "admin"
        else:
            self.keys_dir = Path(keys_dir)

        self.private_key: ed25519.Ed25519PrivateKey | None = None
        self.public_key: ed25519.Ed25519PublicKey | None = None

        self._load_or_generate_keys()

    def _load_or_generate_keys(self) -> None:
        """Load Ed25519 keys from disk or auto-generate them if in development mode."""
        private_key_path = self.keys_dir / "admin_ed25519_private.pem"
        public_key_path = self.keys_dir / "admin_ed25519_public.pem"

        if private_key_path.exists() and public_key_path.exists():
            private_bytes = private_key_path.read_bytes()
            public_bytes = public_key_path.read_bytes()
            self.private_key = serialization.load_pem_private_key(private_bytes, password=None)  # type: ignore
            self.public_key = serialization.load_pem_public_key(public_bytes)  # type: ignore
            return

        if self.environment.lower() == "production":
            raise RuntimeError(
                "Production Admin Ed25519 signing keys are absent from disk! "
                "Automatic key generation is strictly prohibited in production environments."
            )

        # Development / test auto-generation
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        new_private = ed25519.Ed25519PrivateKey.generate()
        new_public = new_private.public_key()

        private_pem = new_private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_pem = new_public.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        private_key_path.write_bytes(private_pem)
        public_key_path.write_bytes(public_pem)

        try:
            os.chmod(private_key_path, stat.S_IRUSR | stat.S_IWUSR)
            os.chmod(public_key_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        except Exception:
            pass

        self.private_key = new_private
        self.public_key = new_public

    def issue_admin_token(
        self,
        admin_id: uuid.UUID | str,
        username: str,
        is_super_admin: bool,
    ) -> str:
        """
        Issue a signed Ed25519 Administrative Access Token valid for 15 minutes.
        """
        if self.private_key is None:
            raise RuntimeError("Admin private key is not initialized")

        now_dt = datetime.now(timezone.utc)
        iat = int(now_dt.timestamp())
        exp = int((now_dt + timedelta(minutes=ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp())
        jti = secrets.token_hex(16)

        role = "super_admin" if is_super_admin else "admin"

        claims = AdminTokenClaims(
            sub=str(admin_id),
            username=username,
            role=role,
            iss=self.issuer,
            aud=self.audience,
            iat=iat,
            nbf=iat,
            exp=exp,
            jti=jti,
        )

        token = jwt.encode(
            payload=claims.to_dict(),
            key=self.private_key,  # type: ignore
            algorithm=ADMIN_JWT_ALGORITHM,
        )
        return token

    def verify_admin_token(self, token: str) -> AdminTokenClaims:
        """
        Verify an Ed25519 Administrative Access Token signature, expiration, issuer, and audience.
        Returns typed AdminTokenClaims on success or raises domain security exceptions.
        """
        if self.public_key is None:
            raise RuntimeError("Admin public key is not initialized")
        if not isinstance(token, str) or not token.strip():
            raise InvalidAdminTokenError("Token cannot be empty")

        try:
            payload = jwt.decode(
                jwt=token,
                key=self.public_key,  # type: ignore
                algorithms=[ADMIN_JWT_ALGORITHM],
                audience=self.audience,
                issuer=self.issuer,
                options={
                    "require": ["sub", "username", "role", "iss", "aud", "iat", "nbf", "exp", "jti"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
            return AdminTokenClaims.from_dict(payload)
        except jwt.ExpiredSignatureError as exc:
            raise AdminTokenExpiredError("Administrative access token has expired") from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidAdminTokenError("Administrative access token signature or claims are invalid") from exc
        except ValueError as exc:
            raise InvalidAdminTokenError(f"Malformed token payload: {exc}") from exc
        except Exception as exc:
            raise InvalidAdminTokenError("Unexpected error during token verification") from exc
