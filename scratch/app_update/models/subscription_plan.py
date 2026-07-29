"""
subscription_plan.py — Immutable code-defined subscription plan registry (Phase 1.4.3).

This is NOT a database table. It is a code-defined registry serving as the single
source of truth for account limits and quotas.

NOTE ON POLICY ENFORCEMENT:
- max_devices is strictly enforced in Phase 1.4.3 during device registration.
- max_concurrent_ips is stored only. Concurrent IP enforcement belongs to the VPN layer
  (Marzban + V2IpLimit/luIP). Billing/Auth stores the policy but does not observe live
  VPN sessions and therefore cannot enforce this value directly.
- data_quota_bytes is stored only for future data traffic quota integration.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class SubscriptionPlan:
    """Immutable representation of a subscription plan and its limits."""
    plan_id: str
    display_name: str
    max_devices: int
    max_concurrent_ips: int
    data_quota_bytes: int
    price_minor_units: int = 0
    currency: str = "INR"



# ── Code-Defined Registry ────────────────────────────────────────────────────
FREE: Final[SubscriptionPlan] = SubscriptionPlan(
    plan_id="free",
    display_name="Free Plan",
    max_devices=1,
    max_concurrent_ips=1,
    data_quota_bytes=10 * 1024**3,  # 10 GB
    price_minor_units=0,
)

BASIC: Final[SubscriptionPlan] = SubscriptionPlan(
    plan_id="basic",
    display_name="Basic Plan",
    max_devices=1,
    max_concurrent_ips=1,
    data_quota_bytes=80 * 1024**3,  # 80 GB
    price_minor_units=6900,  # 69 INR
)

STANDARD: Final[SubscriptionPlan] = SubscriptionPlan(
    plan_id="standard",
    display_name="Standard Plan",
    max_devices=2,
    max_concurrent_ips=2,
    data_quota_bytes=100 * 1024**3,  # 100 GB
    price_minor_units=9900,  # 99 INR
)

QUARTERLY: Final[SubscriptionPlan] = SubscriptionPlan(
    plan_id="quarterly",
    display_name="Quarterly Plan",
    max_devices=1,
    max_concurrent_ips=1,
    data_quota_bytes=250 * 1024**3,  # 250 GB
    price_minor_units=17900,  # 179 INR
)


# Registry dictionary mapping plan_id (lowercase) to SubscriptionPlan instance
PLANS_REGISTRY: Final[dict[str, SubscriptionPlan]] = {
    FREE.plan_id: FREE,
    BASIC.plan_id: BASIC,
    STANDARD.plan_id: STANDARD,
    QUARTERLY.plan_id: QUARTERLY,
}

