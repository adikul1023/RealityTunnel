"""
certificate_provider.py - Abstract interface for certificate issuance and validation.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any

class CertificateProvider(ABC):
    """
    Interface for certificate management.
    Implementations could include SelfSignedProvider, LetsEncryptProvider, etc.
    """
    
    @abstractmethod
    def validate(self, certificate_data: bytes) -> Dict[str, Any]:
        """
        Validates the certificate data and extracts metadata.
        Returns a dictionary of metadata (e.g., fingerprint, common_name, expires_at).
        Raises InvalidCertificateError if invalid.
        """
        pass
