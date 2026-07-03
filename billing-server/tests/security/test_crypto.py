"""
Unit Tests for Cryptographic Helpers (app/security/crypto.py)
"""

import pytest
from app.security import hash_master_token, compare_secrets, SHA256_HEX_LENGTH


def test_hash_master_token_deterministic():
    """Verify SHA-256 hashing is deterministic: identical inputs produce identical digests."""
    secret = "test_secret_master_token_value"
    hash1 = hash_master_token(secret)
    hash2 = hash_master_token(secret)
    assert hash1 == hash2


def test_hash_master_token_length_and_format():
    """Verify SHA-256 digest is exactly 64 hexadecimal characters."""
    secret = "another_secret_token"
    digest = hash_master_token(secret)
    assert len(digest) == SHA256_HEX_LENGTH
    # Verify valid hexadecimal string
    assert all(c in "0123456789abcdef" for c in digest.lower())


def test_hash_master_token_collision_resistance():
    """Verify different inputs produce different SHA-256 hashes."""
    secret1 = "secret_value_1"
    secret2 = "secret_value_2"
    assert hash_master_token(secret1) != hash_master_token(secret2)


def test_hash_master_token_invalid_type():
    """Verify TypeError is raised when passing non-string arguments to hash_master_token."""
    with pytest.raises(TypeError):
        hash_master_token(12345) # type: ignore


def test_compare_secrets_equal():
    """Verify compare_secrets returns True for identical secret strings and bytes."""
    val1 = "super_secret_master_token_hash_1234567890"
    val2 = "super_secret_master_token_hash_1234567890"
    assert compare_secrets(val1, val2) is True

    bytes1 = b"binary_secret_data"
    bytes2 = b"binary_secret_data"
    assert compare_secrets(bytes1, bytes2) is True


def test_compare_secrets_different():
    """Verify compare_secrets returns False for different secret strings and bytes."""
    val1 = "secret_token_a"
    val2 = "secret_token_b"
    assert compare_secrets(val1, val2) is False

    bytes1 = b"binary_secret_a"
    bytes2 = b"binary_secret_b"
    assert compare_secrets(bytes1, bytes2) is False


def test_compare_secrets_invalid_types():
    """Verify compare_secrets returns False gracefully for incompatible or non-string/bytes types."""
    assert compare_secrets("secret", None) is False # type: ignore
    assert compare_secrets(12345, 12345) is False # type: ignore
    assert compare_secrets("secret", 12345) is False # type: ignore
