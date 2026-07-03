"""
Cryptographic Helpers

Pure cryptographic functions for hashing secrets and performing constant-time comparisons.
Strictly decoupled from frameworks, databases, and authentication state. Zero logging of secrets or hashes.
"""

import hashlib
import hmac
from typing import AnyStr


def hash_master_token(token: str) -> str:
    """
    Hash a 256-bit Master Token using SHA-256, returning a 64-character hexadecimal digest.

    CRYPTOGRAPHIC REASONING — WHY SHA-256 INSTEAD OF ARGON2ID:
    1. Master Tokens are generated directly by the server using a cryptographically secure
       pseudorandom number generator (CSPRNG via Python's `secrets` module).
    2. They contain 256 bits of true entropy, making them fundamentally different from
       human-chosen passwords.
    3. Because of this high entropy (2^256 possible values), they are completely immune to
       offline dictionary attacks, rainbow tables, and brute-force guessing.
    4. Memory-hard Key Derivation Functions (KDFs) like Argon2id are specifically designed to
       protect low-entropy human passwords by making verification computationally and memory expensive.
    5. Using Argon2id for high-entropy machine tokens would only impose severe CPU and memory
       cost on our backend server under high authentication load without improving cryptographic security.
    Therefore, SHA-256 provides optimal speed, standard cryptographic collision resistance, and complete
    protection for high-entropy machine secrets.
    """
    if not isinstance(token, str):
        raise TypeError("Master token must be a string")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def compare_secrets(val1: AnyStr, val2: AnyStr) -> bool:
    """
    Securely compare two secret strings or bytes in constant time.

    CRYPTOGRAPHIC REASONING — WHY HMAC.COMPARE_DIGEST():
    Standard equality operators (`==`) in Python terminate comparison early as soon as the first
    mismatched byte is encountered. An attacker can exploit this short-circuiting behavior by
    measuring microscopic differences in execution time (timing attacks) to guess characters of a
    secret one byte at a time.
    `hmac.compare_digest()` ensures the comparison takes a constant amount of time proportional only
    to the length of the strings, completely preventing timing side-channel attacks.
    """
    if not isinstance(val1, (str, bytes)) or not isinstance(val2, (str, bytes)):
        return False
    return hmac.compare_digest(val1, val2)
