"""
crypto_service.py - Service for encrypting and decrypting sensitive data using AES-256-GCM.
"""
from __future__ import annotations

import base64
import os
from typing import Dict, Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

class CryptoService:
    """Service for managing AES-256-GCM encryption/decryption of node certificates."""

    def __init__(self) -> None:
        pass

    def _get_aes_key(self) -> bytes:
        """Derive a 32-byte AESGCM key from settings.secret_key (or dedicated encryption_key)."""
        # In a real system, we'd use settings.encryption_key if available, but secret_key is guaranteed.
        key_bytes = settings.secret_key.get_secret_value().encode("utf-8")
        if len(key_bytes) >= 32:
            return key_bytes[:32]
        return key_bytes.ljust(32, b"0")

    def encrypt_blob(self, data: bytes) -> Dict[str, Any]:
        """
        Encrypts raw bytes using AES-256-GCM.
        Returns a dictionary with key_version, nonce, tag, and ciphertext.
        """
        aesgcm = AESGCM(self._get_aes_key())
        nonce = os.urandom(12)
        
        # AESGCM.encrypt returns ciphertext + tag appended
        encrypted = aesgcm.encrypt(nonce, data, None)
        
        # In AESGCM, the auth tag is the last 16 bytes.
        ciphertext = encrypted[:-16]
        tag = encrypted[-16:]

        return {
            "key_version": 1, # Default version 1 for now
            "crypto_nonce": base64.b64encode(nonce).decode("ascii"),
            "crypto_tag": base64.b64encode(tag).decode("ascii"),
            "encrypted_blob": base64.b64encode(ciphertext).decode("ascii"),
        }

    def decrypt_blob(self, key_version: int, crypto_nonce: str, crypto_tag: str, encrypted_blob: str) -> bytes:
        """
        Decrypts an encrypted blob with the specified nonce and tag.
        """
        aesgcm = AESGCM(self._get_aes_key())
        nonce = base64.b64decode(crypto_nonce.encode("ascii"))
        tag = base64.b64decode(crypto_tag.encode("ascii"))
        ciphertext = base64.b64decode(encrypted_blob.encode("ascii"))
        
        # Re-append tag for cryptography's AESGCM.decrypt
        return aesgcm.decrypt(nonce, ciphertext + tag, None)

crypto_service = CryptoService()
