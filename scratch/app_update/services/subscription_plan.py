"""
subscription_plan.py — Domain service for resolving subscription plans and checking limits (Phase 1.4.3).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.models.subscription_plan import PLANS_REGISTRY, SubscriptionPlan
from app.services.exceptions import UnknownPlanError

if TYPE_CHECKING:
    from app.models.account import Account

logger = logging.getLogger(__name__)


class SubscriptionPlanService:
    """
    Pure domain service responsible for policy lookup and limit evaluation.
    Does not interact with FastAPI or HTTP layers.
    """

    def get_plan(self, plan_id: str) -> SubscriptionPlan:
        """
        Resolve a SubscriptionPlan by its plan_id.
        Rejects unknown plan IDs by raising UnknownPlanError.
        """
        if not plan_id:
            raise UnknownPlanError("Plan ID cannot be empty.")

        clean_id = plan_id.strip().lower()
        plan = PLANS_REGISTRY.get(clean_id)
        if not plan:
            logger.warning("Attempted to resolve unknown subscription plan ID: %s", clean_id)
            raise UnknownPlanError(f"Unknown subscription plan ID: '{clean_id}'")
        return plan

    def list_plans(self) -> list[SubscriptionPlan]:
        """Return all registered subscription plans."""
        return list(PLANS_REGISTRY.values())


    def get_max_devices(self, account: Account) -> int:
        """Return the maximum allowed registered devices for the given account's plan."""
        plan = self.get_plan(account.plan_id)
        return plan.max_devices

    def get_max_concurrent_ips(self, account: Account) -> int:
        """
        Return the configured max_concurrent_ips for the given account's plan.
        NOTE: This value is stored only in Billing/Auth. Concurrent IP enforcement belongs
        to the VPN layer (Marzban + V2IpLimit/luIP).
        """
        plan = self.get_plan(account.plan_id)
        return plan.max_concurrent_ips

    def device_limit_reached(self, account: Account, current_count: int) -> bool:
        """
        Check if the account has reached or exceeded its device registration limit.
        """
        max_devices = self.get_max_devices(account)
        return current_count >= max_devices
