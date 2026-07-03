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
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

logger = logging.getLogger(__name__)

# Pre-computed valid Argon2id hash of a random string used exclusively for timing attack defense
# when querying non-existent usernames during authentication.
DUMMY_ADMIN_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$4Hty2D7M0b+7eD1w/w8uGg$rK3U2g1O5G7n6b5f4c3d2e1f0a9b8c7d6e5f4a3b2c1"


class AdminPasswordService:
    """
    Dedicated engine for Argon2id password hashing and constant-time verification.
    Strictly zero logging of plaintext passwords or hashes.
    """

    def __init__(self) -> None:
        # Explicitly configured Argon2id parameters: memory_cost=65536 KB (64 MB), time_cost=3, parallelism=4
        self._hasher = PasswordHasher(
            time_cost=3,
            memory_cost=65536,
            parallelism=4,
            hash_len=32,
            salt_len=16,
        )

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
        if not isinstance(password, str) or not isinstance(password_hash, str) or not password or not password_hash:
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
