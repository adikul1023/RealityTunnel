"""
admin_dtos.py — Dedicated Data Transfer Objects for Administrative API and domain service responses.

SECURITY CONTRACT:
- These DTOs are completely separate from customer-facing DTOs (auth_models.py, device_models.py).
- They NEVER expose: master_token_hash, password_hash, marzban_username, JWTs, refresh tokens,
  internal refresh token hashes, or any raw cryptographic material.
- The admin API exposes account internal UUIDs (id field) for operator tooling convenience,
  but never exposes credential fields.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Account DTOs ─────────────────────────────────────────────────────────────


class AdminAccountResponse(BaseModel):
    """
    Administrative view of a customer account.

    Security: Never includes master_token_hash, password_hash, marzban_username,
    or any refresh token data.
    """
    id: str = Field(description="Internal account UUID (for operator tooling only)")
    account_id: str = Field(description="Human-readable account identifier (e.g. RT-XXXX-XXXX)")
    status: str = Field(description="Current subscription status")
    plan_id: str = Field(description="Subscription plan identifier")
    subscription_expires_at: Optional[datetime] = Field(
        default=None,
        description="Subscription expiry timestamp (UTC), or null if no expiry set"
    )
    created_at: datetime = Field(description="Account creation timestamp (UTC)")

    model_config = {"from_attributes": True}


class AdminAccountListResponse(BaseModel):
    """Paginated list of administrative account views."""
    accounts: list[AdminAccountResponse] = Field(description="List of accounts")
    total: int = Field(description="Total number of accounts returned in this page")

    model_config = {"from_attributes": True}


# ── Device DTOs ──────────────────────────────────────────────────────────────


class AdminDeviceResponse(BaseModel):
    """
    Administrative view of a registered client device.
    Read-only. Device editing remains a customer-only operation.
    """
    device_guid: str = Field(description="Unique hardware or installation identifier")
    friendly_name: Optional[str] = Field(default=None, description="User-assigned friendly name")
    is_active: bool = Field(description="Whether the device is active or soft-deactivated")
    first_seen_at: datetime = Field(description="Initial registration timestamp (UTC)")
    last_seen_at: datetime = Field(description="Most recent activity timestamp (UTC)")

    model_config = {"from_attributes": True}


class AdminDeviceListResponse(BaseModel):
    """List of administrative device views for an account."""
    devices: list[AdminDeviceResponse] = Field(description="List of registered devices")

    model_config = {"from_attributes": True}


# ── Signal DTOs ──────────────────────────────────────────────────────────────


class AdminSignalResponse(BaseModel):
    """
    Administrative view of a connection security signal event.
    Read-only. Source IP and user-agent are included for operator security review.
    """
    id: str = Field(description="Signal event UUID")
    event_type: str = Field(description="Security event type (e.g. LOGIN, DEVICE_REGISTER)")
    source_ip: Optional[str] = Field(default=None, description="Client IP address at event time")
    user_agent: Optional[str] = Field(default=None, description="Client user-agent string")
    occurred_at: datetime = Field(description="Event timestamp (UTC)")
    success: bool = Field(description="Whether the event represented a successful operation")

    model_config = {"from_attributes": True}


class AdminSignalListResponse(BaseModel):
    """Paginated list of connection security signal events for an account."""
    signals: list[AdminSignalResponse] = Field(description="List of signal events")
    total: int = Field(description="Total number of signals returned in this page")

    model_config = {"from_attributes": True}


# ── Operation DTOs ───────────────────────────────────────────────────────────


class AdminLogoutAllResponse(BaseModel):
    """Result of a forced logout-all operation."""
    revoked_count: int = Field(description="Number of refresh token sessions revoked")

    model_config = {"from_attributes": True}


class ExtendSubscriptionRequest(BaseModel):
    """Request payload for PATCH /api/admin/accounts/{account_id}/extend-subscription."""
    days: int = Field(
        ge=1,
        le=3650,
        description="Number of days to extend the subscription from its current expiry (or now)",
    )


class AdminGrantSubscriptionRequest(BaseModel):
    """Request payload for POST /api/admin/accounts/{account_id}/grant-subscription."""
    plan_id: str = Field(description="Subscription plan identifier (e.g. standard, pro)")
    duration_days: int = Field(ge=1, le=3650, description="Duration in days")
    data_quota_gb: Optional[int] = Field(default=None, description="[DEPRECATED] Override data quota in GB")
    device_limit: Optional[int] = Field(default=None, description="[DEPRECATED] Override device limit")
    payment_method: Optional[str] = Field(default=None, description="Payment method used (e.g. manual_qr)")
    payment_reference: Optional[str] = Field(default=None, description="Payment reference/UTR")
    notes: Optional[str] = Field(default=None, description="Operator notes")


class AdminGrantSubscriptionResponse(BaseModel):
    """Response payload for POST /api/admin/accounts/{account_id}/grant-subscription."""
    success: bool = Field(description="Whether the DB grant was successful")
    plan: str = Field(description="The granted plan ID")
    expires_at: Optional[datetime] = Field(description="The new subscription expiry timestamp")
    provisioning_state: str = Field(description="Current state of the VPN provisioning (e.g. PROVISIONED or NEEDS_SYNC)")
    sync_status: str = Field(description="Status of the post-commit Marzban sync (e.g. success, queued_for_retry)")

    model_config = {"from_attributes": True}
