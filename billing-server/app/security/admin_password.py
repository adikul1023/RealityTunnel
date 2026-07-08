"""
admin_password.py — Password hashing and verification service for administrative accounts.

SECURITY & ARCHITECTURAL DECISIONS — WHY ARGON2ID INSTEAD OF SHA-256 OR BCRYPT:
1. Unlike 256-bit high-entropy machine-generated Master Tokens (which can safely use fast single-iteration SHA-256
   because their entropy prevents brute-force), administrative passwords are human-selected strings susceptible to
   dictionary attacks, GPU/ASIC brute-forcing, and rainbow tables.
2. Argon2id is the winner of the Password Hashing Competition (PHC) and the industry gold standard for human password
   hashing. It is a memory-hard key derivation function designed to resist both GPU/ASIC parallelism (via high memory
   consumption, Argon2d) and side-channel timing attacks (Argon2i).
3. Bcrypt is an older standard limited to 72-byte passwords and lacks the tuneable memory hardness needed to defend
   against modern custom FPGA/ASIC cracking hardware.
4. SHA-256 is a fast cryptographic hash function designed for speed; using it for human passwords would allow an attacker
   to test billions of candidate passwords per second on modern GPUs.
5. Timing Attack Defense: When an administrative username does not exist, we still perform Argon2id verification against
   a precomputed dummy hash (`DUMMY_ADMIN_PASSWORD_HASH`). This ensures that the computational and memory latency of login
   attempts is identical regardless of whether the target username exists, completely preventing account enumeration via
   network response timing analysis.
"""

from __future__ import annotations

import logging
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

logger = logging.getLogger(__name__)

# Argon2id parameters shared between real password hashing and the dummy timing-defense hash below.
# Both MUST use identical parameters so that a genuine hash and the dummy hash impose identical
# computational/memory cost on `verify()`, regardless of whether the target account exists.
_ADMIN_ARGON2_PARAMS: dict[str, int] = {
    "time_cost": 3,
    "memory_cost": 65536,
    "parallelism": 4,
    "hash_len": 32,
    "salt_len": 16,
}

# SECURITY FIX (Audit Finding H1): The dummy hash used for timing-attack defense when an admin
# username does not exist MUST be a syntactically and semantically valid Argon2id hash that is
# guaranteed to run the *full* memory-hard KDF on every verification attempt.
#
# Previously this was a hand-crafted, structurally invalid PHC string. Because it could not be
# decoded by the underlying Argon2 implementation, `verify()` failed in under a millisecond
# (~0.5ms) instead of running the ~68ms memory-hard computation a real hash requires -- creating a
# ~140x timing gap that let an unauthenticated attacker enumerate valid admin usernames purely by
# measuring response latency.
#
# The fix: generate the dummy hash the same way a real hash would be generated -- by actually
# calling `PasswordHasher(**_ADMIN_ARGON2_PARAMS).hash(...)` against a high-entropy random secret.
# This guarantees the dummy hash is always a well-formed Argon2id digest, so `verify()` always runs
# the complete KDF and always fails with `VerifyMismatchError` (a mismatched digest), never with
# `VerificationError`/`InvalidHashError` (a decode failure). This is computed once, at module import
# time, so the (relatively expensive) hash generation cost is paid once at process startup rather
# than on every dummy comparison.
DUMMY_ADMIN_PASSWORD_HASH: str = PasswordHasher(**_ADMIN_ARGON2_PARAMS).hash(
    secrets.token_urlsafe(32)
)


class AdminPasswordService:
    """
    Dedicated engine for Argon2id password hashing and constant-time verification.
    Strictly zero logging of plaintext passwords or hashes.
    """

    def __init__(self) -> None:
        # Explicitly configured Argon2id parameters: memory_cost=65536 KB (64 MB), time_cost=3, parallelism=4
        # Uses the same shared parameter set as DUMMY_ADMIN_PASSWORD_HASH above, guaranteeing that
        # real and dummy verification attempts impose identical computational cost.
        self._hasher = PasswordHasher(**_ADMIN_ARGON2_PARAMS)

    def hash_password(self, password: str) -> str:
        """
        Hash a human-generated administrative password using memory-hard Argon2id.
        Returns a formatted Argon2id hash string containing algorithm parameters, salt, and digest.
        """
        if not isinstance(password, str) or not password:
            raise ValueError("Password must be a non-empty string")
        return self._hasher.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify a candidate password against an Argon2id hash string.
        Returns True if matching, False otherwise. Handles invalid hash strings without raising exceptions.
        """
        if (
            not isinstance(password, str)
            or not isinstance(password_hash, str)
            or not password
            or not password_hash
        ):
            return False
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
        except Exception:
            # Defensive catch to prevent unexpected cryptography library errors from bubbling up
            return False

    def execute_timing_defense(self, password: str) -> None:
        """
        Execute dummy verification against a static Argon2id hash to prevent timing-based username enumeration.
        """
        self.verify_password(password, DUMMY_ADMIN_PASSWORD_HASH)
