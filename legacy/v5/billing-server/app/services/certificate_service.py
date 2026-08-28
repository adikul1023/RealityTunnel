"""
certificate_service.py - Service for validating and extracting metadata from PFX certificates.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Dict, Any, Tuple

from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives.asymmetric import rsa, ec
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import NameOID
from cryptography import x509

from app.exceptions import InvalidCertificateError

class CertificateService:
    """Service for parsing and validating PKCS#12 (PFX) certificates."""
    
    def validate_and_extract(self, pfx_data: bytes, password: bytes | None = None) -> Dict[str, Any]:
        """
        Parses a PFX blob and validates its strength and expiration.
        Returns a dictionary of metadata (fingerprint, common_name, algorithm, expires_at).
        """
        try:
            # We expect passwordless PFX as per VPNHood protocol if generated correctly, or whatever password was set.
            result = pkcs12.load_pkcs12(pfx_data, password)
        except Exception as e:
            raise InvalidCertificateError(f"Failed to parse PFX: {str(e)}")

        if hasattr(result, 'key'):
            private_key = result.key
            certificate = result.cert.certificate if hasattr(result.cert, 'certificate') else result.cert
        else:
            private_key, certificate, additional_certificates = result

        if not certificate:
            raise InvalidCertificateError("PFX does not contain a certificate.")
            
        if not private_key:
            raise InvalidCertificateError("PFX does not contain a private key.")

        # 1. Validate Expiration
        now = datetime.utcnow()
        if certificate.not_valid_before > now:
            raise InvalidCertificateError("Certificate is not yet valid (Not Before).")
        
        if certificate.not_valid_after < now:
            raise InvalidCertificateError("Certificate has expired (Not After).")

        # 2. Validate Key Strength
        public_key = certificate.public_key()
        algorithm = "Unknown"
        if isinstance(public_key, rsa.RSAPublicKey):
            if public_key.key_size < 2048:
                raise InvalidCertificateError("RSA key size must be at least 2048 bits.")
            algorithm = f"RSA {public_key.key_size}"
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            if public_key.key_size < 256:
                raise InvalidCertificateError("ECC key size must be at least 256 bits.")
            algorithm = f"ECC {public_key.curve.name}"
        else:
            raise InvalidCertificateError("Unsupported key algorithm. Must be RSA or ECC.")

        # 3. Extract Metadata
        common_name = None
        for attr in certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME):
            common_name = attr.value
            break

        # Extract Subject Alternative Name (SAN)
        san_list = []
        try:
            san_ext = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName)
            san_list = [name.value for name in san_ext.value]
        except x509.ExtensionNotFound:
            pass
            
        # 4. Validate SAN (Crucial for identity verification)
        if not san_list:
            raise InvalidCertificateError("Certificate must contain at least one Subject Alternative Name (SAN).")
            
        for san in san_ext.value:
            if not isinstance(san, (x509.DNSName, x509.IPAddress)):
                raise InvalidCertificateError("SAN must contain only DNS names or IP addresses.")
            # Check for wildcards
            if isinstance(san, x509.DNSName) and san.value.startswith("*"):
                raise InvalidCertificateError("Wildcard SANs are not permitted for agent nodes.")
                
        fingerprint = certificate.fingerprint(hashes.SHA256()).hex()

        return {
            "fingerprint": fingerprint,
            "common_name": common_name,
            "subject_alternative_names": san_list,
            "algorithm": algorithm,
            "expires_at": certificate.not_valid_after,
        }

certificate_service = CertificateService()
