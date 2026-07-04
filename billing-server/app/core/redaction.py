"""
app/core/redaction.py — Centralized secret redaction utility (Phase 3.1.6).

Guarantees that anything resembling:
  - token
  - secret
  - key
  - password
  - jwt
  - signature
  - authorization
  - bearer
is automatically redacted before appearing in logs, reports, or exception outputs.
"""
from __future__ import annotations

import logging
import re
from typing import Any

REDACTED_STR = "***REDACTED***"

# Keywords that trigger redaction when matched in keys or attribute names
SENSITIVE_KEYWORDS = {
    "token",
    "secret",
    "key",
    "password",
    "passwd",
    "pwd",
    "jwt",
    "signature",
    "authorization",
    "bearer",
    "auth",
    "credential",
    "private_key",
    "public_key",
    "cookie_key",
    "encryption_key",
    "api_token",
    "webhook_secret",
}

# Regex patterns for redacting common token/password formats within arbitrary text/logs
_URL_PASSWORD_REGEX = re.compile(r"(://[^:@/\s]+:)([^@/\s]+)(@)")
_BEARER_REGEX = re.compile(r"(bearer\s+)([a-zA-Z0-9_\-\.]+)", re.IGNORECASE)
_JWT_REGEX = re.compile(r"(ey[a-zA-Z0-9_-]{10,}\.ey[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]+)")
_KEY_VAL_REGEX = re.compile(
    r"([a-zA-Z0-9_-]*(?:" + "|".join(re.escape(k) for k in SENSITIVE_KEYWORDS) + r")[a-zA-Z0-9_-]*\s*[=:]\s*)(['\"]?[^'\",\s\]\}]+['\"]?)",
    re.IGNORECASE,
)


def is_sensitive_key(key: str) -> bool:
    """Check if a key or variable name resembles a secret or sensitive credential."""
    key_lower = key.lower()
    return any(keyword in key_lower for keyword in SENSITIVE_KEYWORDS)


def redact_data(obj: Any) -> Any:
    """
    Recursively traverse dictionaries, lists, and tuples, replacing values of
    sensitive keys with REDACTED_STR.
    """
    if isinstance(obj, dict):
        return {
            k: REDACTED_STR if isinstance(k, str) and is_sensitive_key(k) else redact_data(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [redact_data(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(redact_data(item) for item in obj)
    if isinstance(obj, str):
        return redact_string(obj)
    return obj


def redact_string(text: str) -> str:
    """
    Redact secrets embedded inside a string (e.g., database URLs, Bearer tokens,
    JWT strings, key=val assignments).
    """
    if not isinstance(text, str):
        return str(text)
    
    # Redact URLs: postgresql://user:password@host
    text = _URL_PASSWORD_REGEX.sub(rf"\1{REDACTED_STR}\3", text)
    # Redact Bearer tokens
    text = _BEARER_REGEX.sub(rf"\1{REDACTED_STR}", text)
    # Redact raw JWT strings
    text = _JWT_REGEX.sub(REDACTED_STR, text)
    # Redact key=val / key: val assignments in text
    text = _KEY_VAL_REGEX.sub(rf"\1{REDACTED_STR}", text)
    
    return text


class RedactingFormatter(logging.Formatter):
    """
    Custom logging formatter that filters output through redact_string to prevent
    accidental credential leakage in console and file logs.
    """
    def format(self, record: logging.LogRecord) -> str:
        original_msg = super().format(record)
        return redact_string(original_msg)
