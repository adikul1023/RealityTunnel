"""
Unit Tests for Token & Identifier Generators (app/security/tokens.py)
"""

import re
from app.security import (
    generate_master_token,
    generate_device_guid,
    generate_account_id,
    MASTER_TOKEN_BYTES,
    DEVICE_GUID_BYTES,
    ACCOUNT_ID_PREFIX,
    ACCOUNT_ID_ALPHABET,
)


def test_generate_master_token_format_and_length():
    """Verify Master Token is a 64-character hexadecimal string representing 256 bits."""
    token = generate_master_token()
    assert isinstance(token, str)
    assert len(token) == MASTER_TOKEN_BYTES * 2
    assert all(c in "0123456789abcdef" for c in token.lower())


def test_generate_master_token_uniqueness_sanity_check():
    """Verify Master Tokens generate unique values over a sample of 1,000 iterations."""
    sample_size = 1000
    tokens = {generate_master_token() for _ in range(sample_size)}
    assert len(tokens) == sample_size


def test_generate_device_guid_format_and_length():
    """Verify Device GUID is a 64-character hexadecimal string representing 256 bits."""
    guid = generate_device_guid()
    assert isinstance(guid, str)
    assert len(guid) == DEVICE_GUID_BYTES * 2
    assert all(c in "0123456789abcdef" for c in guid.lower())


def test_generate_device_guid_uniqueness_sanity_check():
    """Verify Device GUIDs generate unique values over a sample of 1,000 iterations."""
    sample_size = 1000
    guids = {generate_device_guid() for _ in range(sample_size)}
    assert len(guids) == sample_size


def test_generate_account_id_format():
    """Verify Account ID matches fixed RealityTunnel format: RT-XXXX-XXXX-XXXX."""
    account_id = generate_account_id()
    assert isinstance(account_id, str)
    assert account_id.startswith(f"{ACCOUNT_ID_PREFIX}-")
    
    # Exact pattern check: RT followed by 3 groups of 4 characters separated by hyphens
    pattern = r"^RT-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}$"
    assert re.match(pattern, account_id) is not None, f"Account ID {account_id} did not match expected format"


def test_generate_account_id_excluded_characters():
    """Verify Account ID never contains visually ambiguous characters: 0, O, 1, I, L."""
    excluded_chars = set("0O1IL")
    for _ in range(500):
        account_id = generate_account_id()
        assert not any(c in excluded_chars for c in account_id), (
            f"Account ID {account_id} contained excluded ambiguous characters"
        )
        # Verify all alphanumeric characters belong to the defined alphabet (ignoring hyphens and prefix)
        body_chars = account_id.replace("RT-", "").replace("-", "")
        assert all(c in ACCOUNT_ID_ALPHABET for c in body_chars)


def test_generate_account_id_uniqueness_sanity_check():
    """Verify Account IDs generate unique values over a sample of 1,000 iterations."""
    sample_size = 1000
    account_ids = {generate_account_id() for _ in range(sample_size)}
    assert len(account_ids) == sample_size
