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
    max_devices=2,
    max_concurrent_ips=2,
    data_quota_bytes=10 * 1024**3,  # 10 GB
    price_minor_units=0,
)

PRO: Final[SubscriptionPlan] = SubscriptionPlan(
    plan_id="pro",
    display_name="Pro Plan",
    max_devices=5,
    max_concurrent_ips=5,
    data_quota_bytes=100 * 1024**3,  # 100 GB
    price_minor_units=49900,  # 499 INR
)

STANDARD: Final[SubscriptionPlan] = SubscriptionPlan(
    plan_id="standard",
    display_name="Standard Plan",
    max_devices=2,
    max_concurrent_ips=2,
    data_quota_bytes=50 * 1024**3,  # 50 GB
    price_minor_units=19900,  # 199 INR
)

FAMILY: Final[SubscriptionPlan] = SubscriptionPlan(
    plan_id="family",
    display_name="Family Plan",
    max_devices=15,
    max_concurrent_ips=15,
    data_quota_bytes=500 * 1024**3,  # 500 GB
    price_minor_units=99900,  # 999 INR
)


# Registry dictionary mapping plan_id (lowercase) to SubscriptionPlan instance
PLANS_REGISTRY: Final[dict[str, SubscriptionPlan]] = {
    FREE.plan_id: FREE,
    STANDARD.plan_id: STANDARD,
    PRO.plan_id: PRO,
    FAMILY.plan_id: FAMILY,
}
