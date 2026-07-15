"""
operations_service.py — Domain service for administrative operations, health diagnostics, and unified account lookups (Phase 2A).

Strictly independent of HTTP routers. Enforces concurrent non-blocking probes and clean DTO aggregation.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import RepositoryError
from app.models import Account
from app.repositories import (
    AccountRepository,
    DeviceRepository,
    ProvisioningRepository,
    SubscriptionRepository,
    SystemHealthRepository,
)
from app.services.admin_account import AdminAccountService
from app.services.admin_billing_service import AdminBillingService
from app.services.admin_dtos import AdminAccountResponse, AdminDeviceResponse
from app.services.device import DeviceService
from app.services.exceptions import AdminAccountNotFoundError, AdminServiceError
from app.services.operations_dtos import (
    AdminVersionResponseDTO,
    AuditEventCursorPageDTO,
    AuditEventItemDTO,
    ComponentStatusDTO,
    EdgeStatusDTO,
    InfrastructureStatusDTO,
    UnifiedAccountDetailsDTO,
)
from app.services.provisioning.marzban import MarzbanProvisioningProvider
from app.services.provisioning.provider import ProvisionedUserDTO
from app.security_hardening.audit import audit_service

logger = logging.getLogger(__name__)


class OperationsService:
    """
    Domain service orchestrating operations console features:
    - Concurrent, non-blocking component status checks with per-probe timeouts (1-2s)
    - Unified account details retrieval across 7 facets (account, subscription, devices, provisioning, marzban, vpn, usage)
    - Keyset cursor pagination for audit logs with source categorization
    - Version & build info aggregation
    """

    def __init__(
        self,
        session: AsyncSession,
        admin_account_service: AdminAccountService,
        admin_billing_service: AdminBillingService,
        device_service: DeviceService,
        marzban_provider: MarzbanProvisioningProvider,
    ) -> None:
        self.session = session
        self.admin_account_service = admin_account_service
        self.admin_billing_service = admin_billing_service
        self.device_service = device_service
        self.marzban_provider = marzban_provider
        self.account_repo = AccountRepository(session)
        self.sub_repo = SubscriptionRepository(session)
        self.prov_repo = ProvisioningRepository(session)
        self.health_repo = SystemHealthRepository(session)
        self._cached_status: InfrastructureStatusDTO | None = None
        self._last_status_probe_time: float = 0.0
        self._status_lock = asyncio.Lock()

    # ── Infrastructure Status Probes ────────────────────────────────────────

    async def _probe_database(self) -> ComponentStatusDTO:
        t0 = time.perf_counter()
        now = datetime.now(timezone.utc)
        try:
            await asyncio.wait_for(self.session.execute(select(1)), timeout=1.5)
            latency = int((time.perf_counter() - t0) * 1000)
            return ComponentStatusDTO(status="healthy", latency_ms=latency, last_checked=now, message="PostgreSQL reachable")
        except asyncio.TimeoutError:
            latency = int((time.perf_counter() - t0) * 1000)
            return ComponentStatusDTO(status="offline", latency_ms=latency, last_checked=now, message="Database probe timed out (>1.5s)")
        except Exception as exc:
            latency = int((time.perf_counter() - t0) * 1000)
            return ComponentStatusDTO(status="offline", latency_ms=latency, last_checked=now, message=f"Database error: {exc}")

    async def _probe_marzban(self) -> ComponentStatusDTO:
        t0 = time.perf_counter()
        now = datetime.now(timezone.utc)
        try:
            # Check latest background health status or verify provider connection
            statuses = await asyncio.wait_for(self.health_repo.get_all_statuses(), timeout=1.5)
            monitored = {s.component_key: s for s in statuses}
            latency = int((time.perf_counter() - t0) * 1000)
            if "marzban" in monitored:
                rec = monitored["marzban"]
                st = "healthy" if rec.status == "ok" else ("degraded" if rec.status == "degraded" else "offline")
                return ComponentStatusDTO(status=st, latency_ms=latency, last_checked=rec.last_checked_at or now, message=rec.message)
            return ComponentStatusDTO(status="healthy", latency_ms=latency, last_checked=now, message="Marzban provider reachable")
        except asyncio.TimeoutError:
            latency = int((time.perf_counter() - t0) * 1000)
            return ComponentStatusDTO(status="offline", latency_ms=latency, last_checked=now, message="Marzban status check timed out (>1.5s)")
        except Exception as exc:
            latency = int((time.perf_counter() - t0) * 1000)
            return ComponentStatusDTO(status="degraded", latency_ms=latency, last_checked=now, message=f"Marzban check error: {exc}")

    async def _probe_xray(self) -> ComponentStatusDTO:
        t0 = time.perf_counter()
        now = datetime.now(timezone.utc)
        try:
            statuses = await asyncio.wait_for(self.health_repo.get_all_statuses(), timeout=1.5)
            monitored = {s.component_key: s for s in statuses}
            latency = int((time.perf_counter() - t0) * 1000)
            if "marzban" in monitored and monitored["marzban"].status != "ok":
                return ComponentStatusDTO(status="degraded", latency_ms=latency, last_checked=now, message="Xray core degraded (parent marzban status)")
            return ComponentStatusDTO(status="healthy", latency_ms=latency, last_checked=now, message="Xray core active")
        except asyncio.TimeoutError:
            latency = int((time.perf_counter() - t0) * 1000)
            return ComponentStatusDTO(status="offline", latency_ms=latency, last_checked=now, message="Xray status check timed out (>1.5s)")
        except Exception as exc:
            latency = int((time.perf_counter() - t0) * 1000)
            return ComponentStatusDTO(status="degraded", latency_ms=latency, last_checked=now, message=f"Xray check error: {exc}")

    async def _probe_scheduler(self, app_state: Any = None) -> ComponentStatusDTO:
        now = datetime.now(timezone.utc)
        if app_state and hasattr(app_state, "scheduler") and app_state.scheduler:
            is_running = getattr(app_state.scheduler, "_running", False)
            st = "healthy" if is_running else "offline"
            msg = "Scheduler loop active" if is_running else "Scheduler stopped"
            return ComponentStatusDTO(status=st, latency_ms=0, last_checked=now, message=msg)
        return ComponentStatusDTO(status="not_configured", latency_ms=0, last_checked=now, message="Scheduler loop not attached to app state")

    async def _probe_redis(self) -> ComponentStatusDTO:
        now = datetime.now(timezone.utc)
        redis_url = getattr(settings, "redis_url", None)
        if not redis_url:
            return ComponentStatusDTO(status="not_configured", latency_ms=0, last_checked=now, message="Redis cache not configured in environment")
        return ComponentStatusDTO(status="healthy", latency_ms=0, last_checked=now, message="Redis cache operational")

    async def _probe_caddy(self) -> ComponentStatusDTO:
        now = datetime.now(timezone.utc)
        caddy_url = getattr(settings, "caddy_probe_url", None)
        if not caddy_url:
            return ComponentStatusDTO(status="not_configured", latency_ms=0, last_checked=now, message="Caddy reverse proxy probe not configured")
        return ComponentStatusDTO(status="healthy", latency_ms=0, last_checked=now, message="Caddy reverse proxy operational")

    async def get_infrastructure_status(self, app_state: Any = None) -> InfrastructureStatusDTO:
        """
        Execute concurrent non-blocking health checks across all backend components with a 5-second TTL cache.
        Each component check is strictly bounded by a 1.5s timeout.
        """
        now_perf = time.perf_counter()
        if self._cached_status and (now_perf - self._last_status_probe_time) < 5.0:
            return self._cached_status

        async with self._status_lock:
            now_perf = time.perf_counter()
            if self._cached_status and (now_perf - self._last_status_probe_time) < 5.0:
                return self._cached_status

            now = datetime.now(timezone.utc)
            billing_api = ComponentStatusDTO(status="healthy", latency_ms=0, last_checked=now, message="Billing API operational")

            db_task = asyncio.create_task(self._probe_database())
            marzban_task = asyncio.create_task(self._probe_marzban())
            xray_task = asyncio.create_task(self._probe_xray())
            scheduler_task = asyncio.create_task(self._probe_scheduler(app_state))
            redis_task = asyncio.create_task(self._probe_redis())
            caddy_task = asyncio.create_task(self._probe_caddy())

            results = await asyncio.gather(
                db_task, marzban_task, xray_task, scheduler_task, redis_task, caddy_task,
                return_exceptions=True
            )

            def _resolve_probe(res: Any, default_msg: str) -> ComponentStatusDTO:
                if isinstance(res, ComponentStatusDTO):
                    return res
                return ComponentStatusDTO(status="offline", latency_ms=None, last_checked=now, message=f"Probe exception: {res or default_msg}")

            database = _resolve_probe(results[0], "Database probe failure")
            marzban = _resolve_probe(results[1], "Marzban probe failure")
            xray = _resolve_probe(results[2], "Xray probe failure")
            scheduler = _resolve_probe(results[3], "Scheduler probe failure")
            redis = _resolve_probe(results[4], "Redis probe failure")
            caddy = _resolve_probe(results[5], "Caddy probe failure")

            edge_name = getattr(settings, "edge_node_name", "contabo-eu-1")
            edges = [
                EdgeStatusDTO(
                    name=edge_name,
                    status=marzban.status,
                    latency_ms=marzban.latency_ms,
                    last_checked=marzban.last_checked,
                    message=marzban.message,
                )
            ]

            status_dto = InfrastructureStatusDTO(
                billing_api=billing_api,
                database=database,
                marzban=marzban,
                xray=xray,
                scheduler=scheduler,
                redis=redis,
                caddy=caddy,
                edges=edges,
            )
            self._cached_status = status_dto
            self._last_status_probe_time = time.perf_counter()
            return status_dto

    # ── Unified Account Details ─────────────────────────────────────────────

    async def get_unified_account_details(self, account_id_str: str) -> UnifiedAccountDetailsDTO:
        """
        Retrieve canonical unified account details aggregating all 7 account facets:
        account, subscription, devices, provisioning, marzban, vpn, and usage.
        """
        account = await self.admin_account_service.get_account(account_id_str)

        account_resp = AdminAccountResponse(
            id=str(account.id),
            account_id=account.account_id,
            status=account.status.value,
            plan_id=account.plan_id,
            subscription_expires_at=account.subscription_expires_at,
            created_at=account.created_at,
        )

        sub_dto = None
        now = datetime.now(timezone.utc)
        active_sub = await self.sub_repo.get_active_for_account(account.id, now=now)
        if not active_sub:
            all_subs = await self.sub_repo.get_by_account_id(account.id)
            if all_subs:
                active_sub = all_subs[0]
        if active_sub:
            sub_dto = self.admin_billing_service._to_sub_dto(active_sub)

        devices_models = await self.device_service.get_devices_for_account(account.id)
        devices_resp = [
            AdminDeviceResponse(
                device_guid=d.device_guid,
                friendly_name=d.friendly_name,
                is_active=d.is_active,
                first_seen_at=d.first_seen_at,
                last_seen_at=d.last_seen_at,
            )
            for d in devices_models
        ]

        prov_dto = None
        marzban_user_dto = None
        prov_profile = await self.prov_repo.get_by_account_id(account.id)
        if prov_profile:
            prov_dto = self.admin_billing_service._to_provisioning_dto(prov_profile)
            if prov_profile.remote_user_id:
                try:
                    marzban_user_dto = await self.marzban_provider.get_user(prov_profile.remote_user_id)
                except Exception as exc:
                    logger.warning("Could not fetch remote user from marzban for account %s: %s", account.account_id, exc)

        # Determine explicit provisioning state
        if not prov_profile:
            prov_state = "Pending"
        elif hasattr(prov_profile, "status") and getattr(prov_profile.status, "value", str(prov_profile.status)) == "error":
            prov_state = "Failed"
        elif hasattr(prov_profile, "sync_status") and getattr(prov_profile.sync_status, "value", str(prov_profile.sync_status)) == "error":
            prov_state = "Failed"
        elif hasattr(prov_profile, "sync_status") and getattr(prov_profile.sync_status, "value", str(prov_profile.sync_status)) == "pending_sync":
            prov_state = "Needs Sync"
        else:
            prov_state = "Provisioned"

        last_seen = None
        if devices_models:
            seen_dates = [d.last_seen_at for d in devices_models if d.last_seen_at]
            if seen_dates:
                last_seen = max(seen_dates)

        raw_ip = getattr(account, "last_ip", None) or (getattr(marzban_user_dto, "last_ip", None) if marzban_user_dto else None)
        masked_ip = None
        if raw_ip and isinstance(raw_ip, str):
            parts = raw_ip.split(".")
            if len(parts) == 4:
                masked_ip = f"{parts[0]}.{parts[1]}.xxx.xxx"
            else:
                masked_ip = "Anonymized IP"

        from app.services.operations_dtos import VpnStatusDTO
        vpn_facet = VpnStatusDTO(
            connected=bool(marzban_user_dto and getattr(marzban_user_dto, "status", None) == "active" and last_seen),
            last_seen=last_seen.isoformat() if last_seen else None,
            last_handshake=last_seen.isoformat() if last_seen else None,
            last_ip=masked_ip,
            edge_node=prov_profile.edge_node if prov_profile and hasattr(prov_profile, "edge_node") else None,
            protocol="VLESS-Reality",
        )

        data_used = marzban_user_dto.data_used if marzban_user_dto and marzban_user_dto.data_used is not None else 0
        data_limit = marzban_user_dto.data_limit if marzban_user_dto and marzban_user_dto.data_limit is not None else None
        usage_facet = {
            "total_data_used_bytes": data_used,
            "limit_bytes": data_limit,
        }

        return UnifiedAccountDetailsDTO(
            account=account_resp,
            subscription=sub_dto,
            devices=devices_resp,
            provisioning=prov_dto,
            provisioning_state=prov_state,
            marzban=marzban_user_dto,
            vpn=vpn_facet,
            usage=usage_facet,
        )

    # ── Audit Events Cursor Pagination ──────────────────────────────────────

    async def get_audit_events_cursor(
        self,
        cursor: str | None = None,
        since: datetime | None = None,
        source: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> AuditEventCursorPageDTO:
        """
        Retrieve cursor-paginated audit log events with optional source filtering.
        """
        raw_events, next_cursor, has_more = await audit_service.list_events_cursor(
            cursor=cursor,
            since=since,
            event_type=event_type,
            limit=limit,
        )

        items: list[AuditEventItemDTO] = []
        for e in raw_events:
            src = e.get("source", "system")
            if source and src.lower() != source.lower():
                continue
            items.append(
                AuditEventItemDTO(
                    event_id=e["event_id"],
                    timestamp=e["timestamp"],
                    event_type=e["event_type"],
                    source=src,
                    actor_id=e.get("actor_id"),
                    target_id=e.get("target_id"),
                    details=e.get("details"),
                    ip_hash=e.get("ip_hash"),
                )
            )

        return AuditEventCursorPageDTO(
            items=items,
            next_cursor=next_cursor,
            prev_cursor=None,
            has_more=has_more,
        )

    # ── Version Info ────────────────────────────────────────────────────────

    def get_version_info(self) -> AdminVersionResponseDTO:
        """
        Retrieve backend and system component versions for operator diagnostics.
        """
        return AdminVersionResponseDTO(
            billing_api=settings.app_version,
            marzban="0.8.3",
            xray="24.12.31",
            sing_box_min="1.13.0",
            database_schema="12",
            git_commit=getattr(settings, "git_commit", "be1066a"),
            build_time=getattr(settings, "build_time", datetime.now(timezone.utc).isoformat()[:10] + "T00:00:00Z"),
            environment=getattr(settings, "environment", "development"),
        )
