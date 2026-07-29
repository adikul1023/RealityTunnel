"""
app/security_hardening/__init__.py — Phase 3.5 Security Hardening & Production Defense.

Strictly orthogonal to existing authentication, billing, provisioning, and payment logic.
"""
from app.security_hardening.exceptions import (
    SecurityHardeningError,
    TLSValidationError,
    CSRFValidationError,
    InputValidationError,
    SecretRotationError,
)
from app.security_hardening.headers import SecurityHeadersMiddleware
from app.security_hardening.tls import validate_tls_url, get_secure_client_ssl_context
from app.security_hardening.rotation import secret_rotation_service, SecretRotationService, SecretGeneration
from app.security_hardening.audit import audit_service, AuditService, AuditEvent
from app.security_hardening.csrf import validate_csrf_protection, CSRFMiddleware
from app.security_hardening.validators import (
    validate_uuid_string,
    validate_payload_size,
    validate_json_content_type,
    validate_utf8_bytes,
    validate_json_payload,
    InputValidationMiddleware,
)

__all__ = [
    "SecurityHardeningError",
    "TLSValidationError",
    "CSRFValidationError",
    "InputValidationError",
    "SecretRotationError",
    "SecurityHeadersMiddleware",
    "validate_tls_url",
    "get_secure_client_ssl_context",
    "secret_rotation_service",
    "SecretRotationService",
    "SecretGeneration",
    "audit_service",
    "AuditService",
    "AuditEvent",
    "validate_csrf_protection",
    "CSRFMiddleware",
    "validate_uuid_string",
    "validate_payload_size",
    "validate_json_content_type",
    "validate_utf8_bytes",
    "validate_json_payload",
    "InputValidationMiddleware",
]
