"""
storage_provider.py - Abstract interface for secure certificate storage.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any

class StorageProvider(ABC):
    """
    Interface for securely storing and retrieving encrypted blobs.
    """
    
    @abstractmethod
    def store(self, node_id: str, data: bytes) -> Dict[str, Any]:
        """
        Encrypts and stores the data.
        Returns metadata about the storage (e.g., nonce, tag, version).
        """
        pass

    @abstractmethod
    def retrieve(self, node_id: str, version: int) -> bytes:
        """
        Retrieves and decrypts the data for a given node and version.
        """
        pass
