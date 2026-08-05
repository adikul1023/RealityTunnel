"""
Security Constants

Centralized definition of all cryptographic lengths, formatting alphabets, and prefixes
used across the RealityTunnel Billing/Auth server. Avoids magic numbers in security modules.
"""

# Master Token: 256 bits of server-generated entropy via CSPRNG
MASTER_TOKEN_BYTES: int = 32

# Device GUID: 256 bits of CSPRNG entropy generated once per installation
DEVICE_GUID_BYTES: int = 32

# SHA-256 digest output length when hexadecimal encoded (32 bytes * 2 hex chars/byte)
SHA256_HEX_LENGTH: int = 64

# Refresh Token: 256 bits of CSPRNG entropy, standard 30-day session lifetime
REFRESH_TOKEN_BYTES: int = 32
REFRESH_TOKEN_EXPIRE_DAYS: int = 30

# Account ID formatting constants
# Format: RT-XXXX-XXXX-XXXX
ACCOUNT_ID_PREFIX: str = "RT"
ACCOUNT_ID_GROUPS: int = 3
ACCOUNT_ID_GROUP_SIZE: int = 4
ACCOUNT_ID_SEPARATOR: str = "-"

# Unambiguous 31-character alphabet for Account ID generation.
# Excludes visually similar characters:
# '0' (zero), 'O' (capital o), '1' (one), 'I' (capital i), 'L' (capital l).
# This minimizes manual transcription and visual reading errors for users.
ACCOUNT_ID_ALPHABET: str = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
