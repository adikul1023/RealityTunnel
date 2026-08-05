"""
validators.py — Robust input and payload validation utilities (Phase 3.5).

Rejects malformed UUIDs, oversized payloads, invalid headers, incorrect content types,
malformed JSON, and non-UTF-8 characters.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.config import settings
from app.security_hardening.exceptions import InputValidationError

logger = logging.getLogger(__name__)


def validate_uuid_string(val: str) -> uuid.UUID:
    """
    Validate and convert a string representation to a standard UUID.

    Raises:
        InputValidationError: If string is not a valid UUID format.
    """
    if not val or not isinstance(val, str):
        raise InputValidationError("Invalid UUID format: value must be a non-empty string.")
    try:
        return uuid.UUID(val)
    except ValueError as exc:
        raise InputValidationError(f"Invalid UUID format '{val}': does not conform to UUID standard.") from exc


def validate_payload_size(request: Request, max_bytes: int | None = None) -> None:
    """
    Validate that incoming HTTP request payload does not exceed the size ceiling.
    """
    limit = max_bytes if max_bytes is not None else getattr(settings, "max_payload_size_bytes", 1048576)
    content_length_str = request.headers.get("content-length")
    if content_length_str:
        try:
            content_length = int(content_length_str)
            if content_length > limit:
                logger.warning(
                    "Oversized payload rejected path=%s size=%d limit=%d",
                    request.url.path,
                    content_length,
                    limit,
                )
                raise InputValidationError(
                    f"Payload size ({content_length} bytes) exceeds maximum allowed limit ({limit} bytes)."
                )
        except ValueError:
            raise InputValidationError("Invalid Content-Length header format.")


def validate_json_content_type(request: Request) -> None:
    """
    Ensure state-changing requests with body payloads specify application/json Content-Type.
    """
    if request.method not in ("POST", "PUT", "PATCH"):
        return
    content_length = request.headers.get("content-length", "0")
    try:
        if int(content_length) <= 0 and "transfer-encoding" not in request.headers:
            return
    except ValueError:
        pass

    content_type = request.headers.get("content-type", "")
    if not content_type.lower().startswith("application/json"):
        raise InputValidationError(
            f"Invalid Content-Type '{content_type}': expected 'application/json'."
        )


def validate_utf8_bytes(data: bytes) -> str:
    """
    Verify byte sequence is valid UTF-8.
    """
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputValidationError("Invalid UTF-8 encoding detected in payload.") from exc


def validate_json_payload(data: bytes | str) -> Any:
    """
    Validate and parse JSON payload, rejecting malformed JSON or invalid UTF-8.
    """
    if isinstance(data, bytes):
        text = validate_utf8_bytes(data)
    else:
        text = data

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputValidationError(f"Malformed JSON payload: {exc.msg} at line {exc.lineno} col {exc.colno}.") from exc


class InputValidationMiddleware(BaseHTTPMiddleware):
    """
    ASGI Middleware that rejects oversized payloads and malformed HTTP headers.
    """
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Any:
        try:
            validate_payload_size(request)
            # Check for control character injection in header values
            for name, value in request.headers.items():
                if "\x00" in name or "\x00" in value or "\r" in name or "\n" in name:
                    raise InputValidationError("Invalid HTTP header: null byte or newline injection detected.")
        except InputValidationError as exc:
            return JSONResponse(
                status_code=413 if "exceeds maximum" in exc.message else 400,
                content={"detail": exc.message, "error_type": "input_validation_error"},
            )
        return await call_next(request)
