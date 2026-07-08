"""
app/rate_limit/limiter.py — Core rate limiting engine and abuse protection logging (Phase 3.3).
Handles limit resolution, key generation, backend querying, fail-open resilience, zero-secret abuse logging, and metrics hooks.
"""
from __future__ import annotations

import hashlib
import ipaddress
import logging
import time
from functools import lru_cache
from typing import Any

from fastapi import Depends, Request

from app.config import settings
from app.observability.metrics import metrics_registry
from app.rate_limit.backend import RateLimitBackend
from app.rate_limit.exceptions import RateLimitExceeded
from app.rate_limit.models import KeyType, RateLimitResult, RateLimitRule
from app.rate_limit.storage import get_rate_limit_backend

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Core Rate Limiting & Abuse Protection engine.
    Orchestrates rule lookup, key formatting, exemption evaluation, and backend increments.
    """

    def __init__(self, backend: RateLimitBackend | None = None) -> None:
        self._backend = backend

    @property
    def backend(self) -> RateLimitBackend:
        if self._backend is None:
            self._backend = get_rate_limit_backend()
        return self._backend

    def _is_exempt(self, request: Request, rule_name: str) -> bool:
        if not getattr(settings, "rate_limit_enabled", True):
            return True

        if rule_name in ("webhook", "health") or getattr(settings, f"rate_limit_{rule_name}", "") == "unlimited":
            return True

        path = request.url.path
        if getattr(settings, "rate_limit_allow_healthchecks", True) and path in ("/", "/health", "/version", "/metrics"):
            return True

        ip_str = getattr(request.state, "client_ip", None) or (request.client.host if request.client else "127.0.0.1")

        if getattr(settings, "rate_limit_allow_localhost", False) and ip_str in ("127.0.0.1", "::1", "localhost", "testclient"):
            return True

        if getattr(settings, "rate_limit_allow_internal_ips", False):
            try:
                ip_obj = ipaddress.ip_address(ip_str)
                if ip_obj.is_private or ip_obj.is_loopback:
                    return True
            except ValueError:
                pass

        return False

    def _resolve_rule_str(self, rule_name: str) -> str:
        val = getattr(settings, f"rate_limit_{rule_name}", None)
        if val is not None:
            return str(val)
        if "/" in rule_name or rule_name.lower() == "unlimited":
            return rule_name
        return str(getattr(settings, "rate_limit_anonymous", "100/minute"))

    def _resolve_key(
        self,
        request: Request,
        rule_name: str,
        key_type: KeyType | str = KeyType.IP,
        key_override: str | None = None,
    ) -> str:
        if key_override:
            return f"{key_type}:{key_override}:{rule_name}"

        ip_str = getattr(request.state, "client_ip", None) or (request.client.host if request.client else "127.0.0.1")

        if key_type == KeyType.IP or key_type == "ip":
            return f"ip:{ip_str}:{rule_name}"
        elif key_type == KeyType.ACCOUNT or key_type == "account":
            acc_id = getattr(request.state, "account_id", None) or "unknown"
            return f"account:{acc_id}:{rule_name}"
        elif key_type == KeyType.DEVICE or key_type == "device":
            dev_id = getattr(request.state, "device_guid", None) or "unknown"
            return f"device:{dev_id}:{rule_name}"
        elif key_type == KeyType.ADMIN or key_type == "admin":
            adm_id = getattr(request.state, "admin_id", None) or "unknown"
            return f"admin:{adm_id}:{rule_name}"
        elif key_type == KeyType.ENDPOINT or key_type == "endpoint":
            return f"endpoint:{request.url.path}:ip:{ip_str}"
        return f"ip:{ip_str}:{rule_name}"

    def _log_abuse_attempt(self, request: Request, rule: RateLimitRule, key: str) -> None:
        """
        Log abuse attempt strictly following Zero-Secret rules:
        Log ONLY endpoint, ip hash, request id, limit exceeded, timestamp.
        Never log password, JWT, refresh token, VLESS URI, device GUID, master token, payment data.
        """
        ip_str = getattr(request.state, "client_ip", None) or (request.client.host if request.client else "unknown")
        ip_hash = hashlib.sha256(ip_str.encode("utf-8")).hexdigest()[:16]
        req_id = getattr(request.state, "request_id", "N/A")
        now_ts = int(time.time())

        logger.warning(
            "Abuse protection rate limit exceeded: endpoint=%s, ip_hash=%s, request_id=%s, limit_exceeded=%s, timestamp=%s",
            request.url.path,
            ip_hash,
            req_id,
            rule.limit_str,
            now_ts,
        )

    async def check(
        self,
        request: Request,
        rule_name: str,
        key_type: KeyType | str = KeyType.IP,
        key_override: str | None = None,
    ) -> RateLimitResult:
        """
        Evaluate rate limit against the active backend.
        Fails OPEN on backend errors to protect legitimate traffic from DOS during outages.
        """
        if self._is_exempt(request, rule_name):
            res = RateLimitResult.unlimited()
            self._attach_state(request, res)
            return res

        rule_str = self._resolve_rule_str(rule_name)
        try:
            rule = RateLimitRule.parse(rule_str)
        except ValueError as exc:
            logger.error("Invalid rate limit rule '%s' for '%s': %s", rule_str, rule_name, exc)
            return RateLimitResult.unlimited()

        if rule.unlimited:
            res = RateLimitResult.unlimited()
            self._attach_state(request, res)
            return res

        key = self._resolve_key(request, rule_name, key_type, key_override)
        endpoint = request.url.path
        metrics_registry.inc_counter("rate_limit_hits_total", labels={"endpoint": endpoint, "rule": rule_name})

        try:
            res = await self.backend.increment(key, rule.window_seconds, rule.max_requests)
            try:
                count = await self.backend.get_active_key_count()
                metrics_registry.set_gauge("rate_limit_active_keys", float(count))
            except Exception:
                pass
        except Exception as exc:
            logger.error("RateLimitBackend error during increment for key %s: %s", key, exc)
            metrics_registry.inc_counter("rate_limit_backend_errors", labels={"operation": "increment"})
            if rule_name in ("login", "admin_login", "refresh"):
                logger.error("Rate limiter failing CLOSED due to backend error for critical rule: %s", rule_name)
                metrics_registry.inc_counter("rate_limit_failed_closed", labels={"endpoint": endpoint, "rule": rule_name})
                res = RateLimitResult(
                    allowed=False,
                    limit=rule.max_requests,
                    remaining=0,
                    reset=int(time.time()) + rule.window_seconds,
                    retry_after=rule.window_seconds
                )
                self._attach_state(request, res)
                return res

            # FAIL-OPEN RULE: Do not DOS legitimate users if storage backend fails
            res = RateLimitResult.unlimited()
            self._attach_state(request, res)
            return res

        self._attach_state(request, res)
        if not res.allowed:
            metrics_registry.inc_counter("rate_limit_denied_total", labels={"endpoint": endpoint, "rule": rule_name})
            self._log_abuse_attempt(request, rule, key)

        return res

    async def is_allowed(
        self,
        request: Request,
        rule_name: str,
        key_type: KeyType | str = KeyType.IP,
        key_override: str | None = None,
    ) -> bool:
        """Convenience method returning True if request is permitted, False if rate limited."""
        res = await self.check(request, rule_name, key_type, key_override)
        return res.allowed

    async def enforce(
        self,
        request: Request,
        rule_name: str,
        key_type: KeyType | str = KeyType.IP,
        key_override: str | None = None,
    ) -> RateLimitResult:
        """Check rate limit and raise RateLimitExceeded (HTTP 429) if denied."""
        res = await self.check(request, rule_name, key_type, key_override)
        if not res.allowed:
            raise RateLimitExceeded(
                retry_after=res.retry_after,
                limit=res.limit,
                remaining=res.remaining,
                reset=res.reset,
            )
        return res

    def _attach_state(self, request: Request, res: RateLimitResult) -> None:
        request.state.rate_limit_result = res
        headers = {
            "X-RateLimit-Limit": str(res.limit),
            "X-RateLimit-Remaining": str(res.remaining),
            "X-RateLimit-Reset": str(res.reset),
        }
        if not res.allowed:
            headers["Retry-After"] = str(res.retry_after)
        request.state.rate_limit_headers = headers


@lru_cache
def get_rate_limiter() -> RateLimiter:
    return RateLimiter()


def require_rate_limit(rule_name: str, key_type: KeyType | str = KeyType.IP):
    """FastAPI dependency for declarative rate limit enforcement on routes."""
    async def dependency(request: Request, limiter: RateLimiter = Depends(get_rate_limiter)) -> RateLimitResult:
        return await limiter.enforce(request, rule_name, key_type)
    return dependency
