"""
RealityTunnel Security & Cryptographic Utilities

Shared cryptographic functions, token generators, and constants.
Strictly independent from FastAPI, SQLAlchemy, Alembic, Repositories, and JWT.
"""

from app.security.constants import (
    MASTER_TOKEN_BYTES,
    DEVICE_GUID_BYTES,
    SHA256_HEX_LENGTH,
    ACCOUNT_ID_PREFIX,
    ACCOUNT_ID_GROUPS,
    ACCOUNT_ID_GROUP_SIZE,
    ACCOUNT_ID_SEPARATOR,
    ACCOUNT_ID_ALPHABET,
)
from app.security.crypto import hash_master_token, compare_secrets, verify_master_token
from app.security.tokens import (
    generate_master_token,
    generate_device_guid,
    generate_account_id,
)

__all__ = [
    "MASTER_TOKEN_BYTES",
    "DEVICE_GUID_BYTES",
    "SHA256_HEX_LENGTH",
    "ACCOUNT_ID_PREFIX",
    "ACCOUNT_ID_GROUPS",
    "ACCOUNT_ID_GROUP_SIZE",
    "ACCOUNT_ID_SEPARATOR",
    "ACCOUNT_ID_ALPHABET",
    "hash_master_token",
    "compare_secrets",
    "verify_master_token",
    "generate_master_token",
    "generate_device_guid",
    "generate_account_id",
]
