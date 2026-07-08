"""
provider.py — Abstract interface and DTOs for payment gateway providers (Phase 2.3).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PaymentOrderDTO:
    """
    Data Transfer Object representing an order created on the payment gateway.
    """
    provider_order_id: str
    amount_minor_units: int
    currency: str
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaymentVerificationDTO:
    """
    Data Transfer Object representing verification status of a remote payment.
    """
    is_valid: bool
    provider_order_id: str
    provider_payment_id: str
    status: str
    amount_minor_units: int | None = None
    currency: str | None = None
    amount_refunded_minor_units: int = 0
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaymentWebhookDTO:
    """
    Data Transfer Object representing parsed and verified webhook payload.
    """
    event_type: str
    status: str
    provider_order_id: str | None = None
    provider_payment_id: str | None = None
    amount_minor_units: int | None = None
    currency: str | None = None
    signature: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaymentRefundDTO:
    """
    Data Transfer Object representing a refund issued through the payment gateway.
    """
    provider_refund_id: str
    provider_payment_id: str
    amount_minor_units: int
    status: str
    raw_data: dict[str, Any] = field(default_factory=dict)


class PaymentProvider(ABC):
    """
    Abstract base class defining the contract for payment gateway integrations.
    All implementations must translate provider-specific HTTP/API errors into domain exceptions.
    Must never communicate with SubscriptionService or ProvisioningService directly.
    """

    @abstractmethod
    async def create_order(
        self,
        amount_minor_units: int,
        currency: str,
        receipt: str,
        notes: dict[str, str] | None = None,
    ) -> PaymentOrderDTO:
        """
        Create a new payment order on the gateway.
        """
        pass

    @abstractmethod
    async def verify_webhook(
        self,
        payload: bytes | str,
        signature: str,
        secret: str | None = None,
    ) -> PaymentWebhookDTO:
        """
        Cryptographically verify and parse an incoming webhook payload.
        Raises PaymentVerificationError if the signature is invalid.
        """
        pass

    @abstractmethod
    async def fetch_payment(
        self,
        provider_payment_id: str,
    ) -> PaymentVerificationDTO:
        """
        Fetch the current status and details of a payment from the gateway.
        """
        pass

    @abstractmethod
    async def refund_payment(
        self,
        provider_payment_id: str,
        amount_minor_units: int | None = None,
        notes: dict[str, str] | None = None,
    ) -> PaymentRefundDTO:
        """
        Issue a full or partial refund for a captured payment.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check connectivity and authentication status with the payment gateway.
        Returns True if reachable and functional, False otherwise.
        """
        pass
