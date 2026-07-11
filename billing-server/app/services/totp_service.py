"""
totp_service.py — Stateless Two-Factor Authentication (TOTP + Backup Codes) Service.

Handles:
- RFC 6238 TOTP secret generation, QR PNG data-URI rendering, and verification.
- AES-256-GCM encryption/decryption of TOTP secrets using app settings.secret_key.
- Argon2 hashing and verification of one-time backup codes.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import secrets
from typing import Tuple

import argon2
import pyotp
import qrcode
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

logger = logging.getLogger(__name__)


class TOTPService:
    """Stateless service for managing TOTP secrets, verification, and backup codes."""

    def __init__(self) -> None:
        self._ph = argon2.PasswordHasher(
            time_cost=2,
            memory_cost=65536,
            parallelism=2,
            hash_len=32,
            salt_len=16,
        )

    def _get_aes_key(self) -> bytes:
        """Derive a 32-byte AESGCM key from settings.secret_key."""
        key_bytes = settings.secret_key.get_secret_value().encode("utf-8")
        if len(key_bytes) >= 32:
            return key_bytes[:32]
        return key_bytes.ljust(32, b"0")

    def encrypt_secret(self, secret: str) -> str:
        """Encrypt base32 TOTP secret using AES-256-GCM."""
        aesgcm = AESGCM(self._get_aes_key())
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, secret.encode("utf-8"), None)
        combined = nonce + ciphertext
        return base64.b64encode(combined).decode("ascii")

    def decrypt_secret(self, encrypted_b64: str) -> str:
        """Decrypt base32 TOTP secret."""
        aesgcm = AESGCM(self._get_aes_key())
        data = base64.b64decode(encrypted_b64.encode("ascii"))
        nonce = data[:12]
        ciphertext = data[12:]
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")

    def generate_setup(self, account_id: str) -> Tuple[str, str, str, list[str]]:
        """
        Generate a new TOTP secret, QR image data URI, provisioning URI, and 10 backup codes.
        Returns: (secret, qr_data_uri, uri, backup_codes)
        """
        secret = pyotp.random_base32()
        uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=account_id,
            issuer_name="Stealthy VPN",
        )

        # Generate QR code PNG data URI
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=2,
        )
        qr.add_data(uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qr_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        qr_data_uri = f"data:image/png;base64,{qr_b64}"

        # Generate 10 backup codes formatted like XXXXX-XXXXX
        backup_codes = []
        for _ in range(10):
            token = secrets.token_hex(5).upper()
            formatted = f"{token[:5]}-{token[5:]}"
            backup_codes.append(formatted)

        return secret, qr_data_uri, uri, backup_codes

    def verify_totp(self, secret: str, code: str) -> bool:
        """Verify a 6-digit TOTP code against the secret (window=1 for ±30s clock skew)."""
        clean_code = code.strip().replace(" ", "")
        if not clean_code.isdigit() or len(clean_code) != 6:
            return False
        totp = pyotp.TOTP(secret)
        return totp.verify(clean_code, valid_window=1)

    def hash_backup_codes(self, codes: list[str]) -> str:
        """Argon2 hash a list of backup codes and return JSON representation."""
        hashed = []
        for code in codes:
            clean = code.strip().upper()
            hashed.append(self._ph.hash(clean))
        return json.dumps(hashed)

    def verify_and_consume_backup_code(
        self, stored_hashes_json: str | None, candidate: str
    ) -> Tuple[bool, str | None]:
        """
        Verify candidate against stored backup code hashes.
        If valid, removes the consumed code and returns (True, updated_hashes_json).
        Otherwise returns (False, stored_hashes_json).
        """
        if not stored_hashes_json:
            return False, stored_hashes_json
        try:
            hashes: list[str] = json.loads(stored_hashes_json)
        except Exception:
            return False, stored_hashes_json

        clean = candidate.strip().upper()
        for idx, h in enumerate(hashes):
            try:
                if self._ph.verify(h, clean):
                    # Remove the consumed code
                    remaining = hashes[:idx] + hashes[idx + 1 :]
                    return True, json.dumps(remaining)
            except Exception:
                continue

        return False, stored_hashes_json
