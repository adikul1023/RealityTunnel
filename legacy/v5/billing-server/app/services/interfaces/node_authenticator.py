"""
node_authenticator.py - Abstract interface for node authentication and bootstrapping.
"""
from abc import ABC, abstractmethod
from typing import Tuple

class NodeAuthenticator(ABC):
    """
    Interface for authenticating VPNHood nodes.
    """
    
    @abstractmethod
    def verify_bootstrap_token(self, token: str) -> bool:
        """
        Verifies a one-time bootstrap token.
        """
        pass

    @abstractmethod
    def exchange_bootstrap_for_agent_secret(self, token: str) -> Tuple[str, str]:
        """
        Exchanges a bootstrap token for a long-term agent secret.
        Returns (node_id, agent_secret).
        """
        pass

    @abstractmethod
    def verify_agent_secret(self, node_id: str, secret: str) -> bool:
        """
        Verifies a long-term agent secret.
        """
        pass
