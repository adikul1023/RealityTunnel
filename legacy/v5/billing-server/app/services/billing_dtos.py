"""
billing_dtos.py — Dedicated Pydantic Data Transfer Objects for Customer Billing API (Phase 2.7).

SECURITY CONTRACT:
- Never exposes internal SQLAlchemy models or primary key UUIDs (account.id, payment.id, subscription.id).
- Never exposes provider secrets, raw signature payloads, or admin hashes.
- Exposes only human-readable identifiers and timestamps.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SubscriptionDTO(BaseModel):
    """
    Customer view of their subscription entitlement.
    When no subscription exists, clean default values (e.g. status='NONE') are returned.
    """

    plan: str = Field(
        description="Subscription plan identifier (e.g. 'pro', 'free', or 'none')"
    )
    lifecycle_status: str = Field(
        description="Current lifecycle status (e.g. 'ACTIVE', 'GRACE', 'EXPIRED', 'NONE')"
    )
    started_at: datetime | None = Field(
        default=None, description="Subscription start timestamp (UTC)"
    )
    expires_at: datetime | None = Field(
        default=None, description="Subscription expiry timestamp (UTC)"
    )
    grace_until: datetime | None = Field(
        default=None, description="Grace period expiry timestamp (UTC) if in GRACE"
    )
    auto_renew: bool = Field(
        default=False, description="Whether automatic renewal is enabled"
    )

    model_config = {"from_attributes": True}


class PlanDTO(BaseModel):
    """
    Customer view of an available subscription plan from the registry.
    """

    plan_id: str = Field(
        description="Unique plan identifier (e.g. 'free', 'pro', 'family')"
    )
    name: str = Field(description="Display name of the plan")
    price: int = Field(description="Price in minor units (e.g. paise or cents)")
    currency: str = Field(default="INR", description="3-letter currency code")
    max_devices: int = Field(description="Maximum registered devices allowed")

    max_concurrent_ips: int = Field(
        description="Maximum concurrent VPN connections allowed"
    )
    quota: int = Field(description="Data traffic quota in bytes")

    model_config = {"from_attributes": True}


class PaymentDTO(BaseModel):
    """
    Customer view of a payment transaction.
    payment_id is the gateway order or payment ID, never an internal database UUID.
    """

    payment_id: str = Field(description="Provider order ID or payment ID")
    provider: str = Field(description="Payment gateway provider (e.g. 'RAZORPAY')")
    amount: int = Field(description="Payment amount in minor units")
    currency: str = Field(description="3-letter currency code (e.g. 'INR')")
    status: str = Field(
        description="Payment lifecycle status (e.g. 'CREATED', 'PAID', 'FAILED')"
    )
    created_at: datetime = Field(description="Transaction creation timestamp (UTC)")

    model_config = {"from_attributes": True}


class PaymentListDTO(BaseModel):
    """
    Paginated list of payment history items.
    """

    payments: list[PaymentDTO] = Field(description="List of payment transactions")
    total: int = Field(description="Total number of payments matching the query")
    limit: int = Field(description="Maximum number of items returned")
    offset: int = Field(description="Number of items skipped")

    model_config = {"from_attributes": True}


class PurchaseRequestDTO(BaseModel):
    """
    Request payload to initiate a new subscription purchase order.

    SECURITY INVARIANT (Finding C-1): The purchase amount is NEVER accepted from the client.
    It is always derived server-side from the authoritative SubscriptionPlanService price for
    `plan_id`. Any client-supplied amount field is intentionally rejected by Pydantic's default
    `extra="forbid"`-equivalent behavior is not relied upon here; instead the field simply does
    not exist on this model, so FastAPI/Pydantic will silently ignore any extra `amount` key sent
    by a client rather than accepting it as a valid parameter.
    """

    plan_id: str = Field(default="pro", description="Plan identifier to purchase")
    idempotency_key: str = Field(
        min_length=8,
        max_length=64,
        description="Unique idempotency key to prevent duplicate orders",
    )


class PurchaseResponseDTO(BaseModel):
    """
    Response payload returned upon order creation.
    Does NOT activate subscription; activation happens exclusively via webhooks.
    """

    payment_id: str = Field(
        description="Gateway order ID required by client checkout SDK"
    )
    provider: str = Field(description="Payment gateway provider")
    amount: int = Field(description="Order amount in minor units")
    currency: str = Field(description="Currency code")
    status: str = Field(description="Order status")
    created_at: datetime = Field(description="Order creation timestamp (UTC)")

    model_config = {"from_attributes": True}
