"""
jwt_models.py — Typed Dataclasses and Constants for Access JWTs.

SECURITY & ARCHITECTURAL DECISIONS:
1. Minimal Claims:
   The JWT contains only `sub` (Account UUID), `account` (Account ID), `device` (Device GUID), and standard RFC 7519
   registered claims (`iss`, `aud`, `iat`, `nbf`, `exp`, `jti`). We explicitly omit Master Tokens, password hashes, emails,
   subscription statuses, and Marzban usernames to minimize exposure if a token is intercepted or logged by client telemetry.

2. 15-Minute Lifetime (`ACCESS_TOKEN_EXPIRE_MINUTES = 15`):
   Access tokens are stateless bearer tokens. A short 15-minute lifetime limits the window of vulnerability if a token is stolen.
   Revocation and rotation are handled via Refresh Tokens (Phase 1.3.4), keeping access verification fast and database-free.

3. Unique Token Identifier (`jti`):
   Every token includes a random 128-bit hex string (`jti`). This enables future support for replay detection, audit tracking,
   and short-term blocklisting without altering the core token schema.

4. Explicit Issuer and Audience (`iss`, `aud`):
   Enforcing strict `iss` ("RealityTunnel Billing/Auth") and `aud` ("RealityTunnel Client") claims prevents cross-service
   token substitution attacks (e.g., using a token issued for a third-party analytical tool against our API).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


# Centralized JWT Constants
ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
JWT_ISSUER: str = "RealityTunnel Billing/Auth"
JWT_AUDIENCE: str = "RealityTunnel Client"
JWT_ALGORITHM: str = "EdDSA"


@dataclass(frozen=True)
class AccessTokenClaims:
    """
    Typed representation of decoded Access Token claims.
    Ensures upper layers interact with strong types instead of raw dictionaries.
    """
    sub: str        # Account UUID string
    account: str    # RealityTunnel Account ID (RT-XXXX-XXXX-XXXX)
    device: str     # Device GUID
    iss: str        # Issuer
    aud: str        # Audience
    iat: int        # Issued At timestamp (UTC epoch seconds)
    nbf: int        # Not Before timestamp (UTC epoch seconds)
    exp: int        # Expiration timestamp (UTC epoch seconds)
    jti: str        # JWT ID (unique hex identifier)

    def to_dict(self) -> dict[str, Any]:
        """Convert typed dataclass to raw dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AccessTokenClaims:
        """Create typed dataclass from decoded payload dictionary, verifying all required claims exist."""
        required_keys = {"sub", "account", "device", "iss", "aud", "iat", "nbf", "exp", "jti"}
        missing = required_keys - data.keys()
        if missing:
            raise ValueError(f"Missing required JWT claims: {sorted(list(missing))}")
        
        return cls(
            sub=str(data["sub"]),
            account=str(data["account"]),
            device=str(data["device"]),
            iss=str(data["iss"]),
            aud=str(data["aud"]),
            iat=int(data["iat"]),
            nbf=int(data["nbf"]),
            exp=int(data["exp"]),
            jti=str(data["jti"]),
        )
