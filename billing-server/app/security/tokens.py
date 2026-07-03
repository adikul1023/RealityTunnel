"""
Token & Identifier Generation

Pure functions for generating cryptographically secure Master Tokens, Device GUIDs,
and unambiguous human-readable Account IDs using Python's `secrets` module.
Strictly zero logging of generated tokens or identifiers.
"""

import secrets
from app.security.constants import (
    MASTER_TOKEN_BYTES,
    DEVICE_GUID_BYTES,
    ACCOUNT_ID_PREFIX,
    ACCOUNT_ID_GROUPS,
    ACCOUNT_ID_GROUP_SIZE,
    ACCOUNT_ID_SEPARATOR,
    ACCOUNT_ID_ALPHABET,
)


def generate_master_token() -> str:
    """
    Generate a cryptographically secure 256-bit Master Token formatted as a 64-character hexadecimal string.

    CRYPTOGRAPHIC REASONING — WHY SECRETS INSTEAD OF RANDOM / UUID:
    1. Python's standard `random` module uses the Mersenne Twister algorithm, which is completely
       deterministic and non-cryptographic. Observing 624 outputs allows an attacker to predict
       all future random values, compromising token security.
    2. `secrets.token_hex()` uses the operating system's Cryptographically Secure Pseudorandom
       Number Generator (CSPRNG, e.g., getrandom()/urandom on Linux, BCryptGenRandom on Windows).
    3. Generating 32 bytes (256 bits) of entropy produces a URL-safe, 64-character hex string
       with deterministic length, ideal for high-entropy machine-to-machine authentication.
    """
    return secrets.token_hex(MASTER_TOKEN_BYTES)


def generate_device_guid() -> str:
    """
    Generate a cryptographically secure 256-bit Device GUID formatted as a 64-character hexadecimal string.

    CRYPTOGRAPHIC REASONING — WHY RANDOM GUIDS INSTEAD OF HARDWARE FINGERPRINTING:
    1. Hardware fingerprinting (MAC addresses, CPU IDs, motherboard serials) is unreliable across
       virtual machines, containerized environments, and hardware upgrades (e.g., swapping a network card).
    2. Hardware IDs can be trivially spoofed or cloned by malicious actors, making them insecure as an
       identity proof.
    3. Harvesting physical hardware serial numbers introduces significant user privacy and tracking concerns.
    4. By generating a random 256-bit CSPRNG GUID once at installation time and storing it securely on
       the client device, we ensure high uniqueness, zero privacy invasion, and robust resilience against
       environment changes.
    """
    return secrets.token_hex(DEVICE_GUID_BYTES)


def generate_account_id() -> str:
    """
    Generate a formatted Account ID in the RealityTunnel format: RT-XXXX-XXXX-XXXX.

    DESIGN REASONING — WHY ACCOUNT IDS ARE IDENTIFIERS AND NOT SECRETS:
    1. Account IDs serve purely as public/semi-public human-readable references for billing support,
       account lookup, and user identification. They are NEVER used alone to authenticate requests or
       grant authorization (which requires possession of the Master Token or valid session tokens).
    2. To make transcription and manual entry error-free for end users, the alphabet is restricted to 31
       unambiguous uppercase characters (`ABCDEFGHJKMNPQRSTUVWXYZ23456789`), explicitly excluding visually
       confusing characters: '0' (zero), 'O' (capital o), '1' (one), 'I' (capital i), and 'L' (capital l).
    3. `secrets.choice()` is used to ensure uniform, unbiased distribution across the alphabet.
    """
    groups = []
    for _ in range(ACCOUNT_ID_GROUPS):
        group = "".join(secrets.choice(ACCOUNT_ID_ALPHABET) for _ in range(ACCOUNT_ID_GROUP_SIZE))
        groups.append(group)
    return f"{ACCOUNT_ID_PREFIX}{ACCOUNT_ID_SEPARATOR}{ACCOUNT_ID_SEPARATOR.join(groups)}"
