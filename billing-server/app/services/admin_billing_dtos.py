"""
admin_billing_dtos.py — Dedicated Data Transfer Objects for Administrative Billing & Operations API (Phase 2.8).

Enforces strict separation between SQLAlchemy models and HTTP APIs.
Ensures ZERO leak of credentials, VLESS URIs, REALITY keys, JWTs, or raw provider secrets.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class AdminDashboardDTO(BaseModel):
    """Aggregated operational and billing metrics for admin dashboard."""
    total_accounts: int
    active_subscriptions: int
    grace_subscriptions: int
    expired_subscriptions: int
    today_payments: int
    today_revenue_minor_units: int
    provisioning_failures: int
    retry_queue_size: int
    active_admins: int


class AdminSubscriptionDTO(BaseModel):
    """Administrative representation of a customer subscription contract."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    plan_id: str
    status: str
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    grace_expires_at: datetime | None = None
    auto_renew: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AdminSubscriptionListDTO(BaseModel):
    """Paginated list of customer subscriptions."""
    total: int
    limit: int
    offset: int
    subscriptions: list[AdminSubscriptionDTO]


class AdminSubscriptionRenewRequest(BaseModel):
    """Request payload for administrative subscription renewal override."""
    new_expires_at: datetime = Field(..., description="New UTC expiration timestamp for the subscription.")


class AdminSubscriptionGraceRequest(BaseModel):
    """Request payload for putting subscription into grace period."""
    grace_duration_days: int = Field(default=7, ge=1, le=30, description="Duration of grace period in days.")


class AdminPaymentDTO(BaseModel):
    """
    Administrative view of a payment transaction.
    Omits signatures, webhook HMACs, and raw gateway credentials.
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    subscription_id: str | None = None
    provider: str
    provider_order_id: str | None = None
    provider_payment_id: str | None = None
    amount_minor_units: int
    currency: str
    status: str
    idempotency_key: str
    paid_at: datetime | None = None
    created_at: datetime | None = None


class AdminPaymentListDTO(BaseModel):
    """Paginated list of payment transactions."""
    total: int
    limit: int
    offset: int
    payments: list[AdminPaymentDTO]


class AdminPaymentResolveRequest(BaseModel):
    """Request payload for manually resolving a failed payment."""
    reason: str = Field(default="Manually resolved by administrator", min_length=3, max_length=255)


class AdminProvisioningDTO(BaseModel):
    """
    Administrative view of a VPN provisioning profile.
    Strictly omits VLESS URIs, REALITY keys, and connection secrets.
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    remote_user_id: str
    provisioning_state: str
    last_sync_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AdminProvisioningListDTO(BaseModel):
    """Paginated list of VPN provisioning profiles."""
    total: int
    limit: int
    offset: int
    profiles: list[AdminProvisioningDTO]


class AdminRetryItemDTO(BaseModel):
    """Representation of a deferred or failed provisioning attempt."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    plan_id: str
    attempt_count: int
    next_retry_at: datetime
    last_error: str | None = None
    status: str
    created_at: datetime | None = None


class AdminRetryQueueDTO(BaseModel):
    """Aggregated status of the provisioning retry queue."""
    pending_count: int
    permanent_failure_count: int
    items: list[AdminRetryItemDTO]


class AdminComponentHealthDTO(BaseModel):
    """Health status of an individual system component."""
    component: str
    status: str  # "ok", "degraded", or "down"
    last_checked_at: datetime | None = None
    last_failure_reason: str | None = None


class AdminSystemHealthDTO(BaseModel):
    """Aggregated health status across all billing and provisioning dependencies."""
    status: str  # "ok", "degraded", or "down"
    components: list[AdminComponentHealthDTO]
    fingerprint: dict[str, Any] | None = None
