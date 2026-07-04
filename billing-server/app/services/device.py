"""
device.py — Core domain service managing client device lifecycle and registration.
Strictly independent of HTTP layer, FastAPI routers, JWT tokens, and middleware.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app.exceptions import (
    DuplicateEntityError,
    RepositoryError,
)
from app.models import Device
from app.repositories import AccountRepository, DeviceRepository
from app.services.exceptions import (
    DeviceLimitExceededError,
    DeviceNotFoundError,
    DeviceOwnershipError,
    DeviceServiceError,
    InactiveDeviceError,
)
from app.services.subscription_plan import SubscriptionPlanService

logger = logging.getLogger(__name__)


class DeviceService:
    """
    Domain service responsible for the lifecycle of registered client devices.
    Enforces device ownership invariants, status checks, and timestamp tracking.
    """

    def __init__(
        self,
        device_repository: DeviceRepository,
        account_repository: AccountRepository,
        plan_service: SubscriptionPlanService | None = None,
    ) -> None:
        self.device_repo = device_repository
        self.account_repo = account_repository
        self.plan_service = plan_service or SubscriptionPlanService()

    def _validate_friendly_name(self, name: str | None) -> str | None:
        """
        Validate friendly name formatting.
        Rejects empty strings, whitespace-only strings, and excessively long names (>100 chars).
        """
        if name is None:
            return None
        if not isinstance(name, str):
            raise DeviceServiceError("Device friendly name must be a string")
        name_clean = name.strip()
        if not name_clean:
            raise DeviceServiceError("Device friendly name cannot be empty or whitespace")
        if len(name_clean) > 100:
            raise DeviceServiceError("Device friendly name exceeds maximum length of 100 characters")
        return name_clean

    def _normalize_device_timestamps(self, device: Device) -> Device:
        """
        Defensively ensure UTC timezone normalization on device timestamps.
        Guards against drivers or migrations leaving tzinfo=None.
        """
        if device.first_seen_at and device.first_seen_at.tzinfo is None:
            device.first_seen_at = device.first_seen_at.replace(tzinfo=timezone.utc)
        if device.last_seen_at and device.last_seen_at.tzinfo is None:
            device.last_seen_at = device.last_seen_at.replace(tzinfo=timezone.utc)
        return device

    async def _get_and_verify_ownership(
        self, account_id: uuid.UUID, device_guid: str, *, for_update: bool = False
    ) -> Device:
        """
        Helper to fetch a device by GUID and verify ownership against account_id.
        Raises DeviceNotFoundError if missing, DeviceOwnershipError if owned by someone else.
        """
        try:
            device = await self.device_repo.get_by_guid(device_guid, for_update=for_update)
        except RepositoryError as exc:
            logger.error("Repository error while querying device by GUID")
            raise DeviceServiceError("Database error during device lookup") from exc

        if device is None:
            raise DeviceNotFoundError("Device not found")

        if device.account_id != account_id:
            logger.warning("Ownership violation: account attempted access to device owned by another account")
            raise DeviceOwnershipError("Device is registered to another account")

        return self._normalize_device_timestamps(device)

    async def register_device(
        self,
        account_id: uuid.UUID,
        device_guid: str,
        friendly_name: str | None = None,
    ) -> Device:
        """
        Register a new device or update an existing device for the same account.

        Invariants:
        - A device GUID may belong to exactly one account. Never multiple.
        - If device already belongs to same account: update last_seen_at (and friendly_name if supplied).
        - If device belongs to different account: raise DeviceOwnershipError.
        """
        clean_name = self._validate_friendly_name(friendly_name)

        try:
            device = await self.device_repo.get_by_guid(device_guid, for_update=True)
        except RepositoryError as exc:
            logger.error("Repository error querying device in register_device")
            raise DeviceServiceError("Database error checking device existence") from exc

        now = datetime.now(timezone.utc)

        if device is not None:
            if device.account_id != account_id:
                logger.warning("Ownership violation during device registration attempt")
                raise DeviceOwnershipError("Device is registered to another account")

            if not device.is_active:
                logger.info("Attempted registration/update on deactivated device")
                raise InactiveDeviceError("Device is deactivated")

            device = self._normalize_device_timestamps(device)
            device.last_seen_at = now
            if clean_name is not None:
                device.friendly_name = clean_name

            try:
                updated = await self.device_repo.update(device)
                return self._normalize_device_timestamps(updated)
            except RepositoryError as exc:
                logger.error("Repository error updating existing device in register_device")
                raise DeviceServiceError("Database error updating device registration") from exc

        # Device does not exist; verify account exists before creating (with row lock to prevent TOCTOU races)
        try:
            account = await self.account_repo.get_by_id(account_id, for_update=True)
        except RepositoryError as exc:
            logger.error("Repository error querying account in register_device")
            raise DeviceServiceError("Database error checking account existence") from exc

        if account is None:
            raise DeviceServiceError("Account not found")

        # Evaluate subscription plan policy and check device limits (Phase 1.4.3).
        # Note on Downgrade Policy:
        # If an account already owns more active devices than the new plan allows:
        # - Existing devices remain untouched in the database.
        # - Existing active devices continue functioning normally (updating timestamps when they check in above).
        # - New device registrations are rejected until the user deactivates/removes devices below the limit.
        # - Never automatically delete devices or silently deactivate them.
        try:
            active_count = await self.device_repo.count_active_devices_for_account(account_id)
        except RepositoryError as exc:
            logger.error("Repository error counting active devices in register_device")
            raise DeviceServiceError("Database error checking device limit") from exc

        if self.plan_service.device_limit_reached(account, active_count):
            logger.info("Device registration rejected due to subscription policy.")
            max_devices = self.plan_service.get_max_devices(account)
            raise DeviceLimitExceededError(active_count, max_devices, account.plan_id)

        try:
            new_device = await self.device_repo.create(
                account_id=account_id,
                device_guid=device_guid,
                friendly_name=clean_name,
                is_active=True,
                first_seen_at=now,
                last_seen_at=now,
            )
            return self._normalize_device_timestamps(new_device)
        except DuplicateEntityError as exc:
            # Race condition: another transaction created the device after our read
            logger.warning("Concurrent device registration detected")
            try:
                existing = await self.device_repo.get_by_guid(device_guid, for_update=True)
            except RepositoryError as lookup_exc:
                raise DeviceServiceError("Database error recovering from registration race") from lookup_exc

            if existing is not None:
                if existing.account_id != account_id:
                    raise DeviceOwnershipError("Device is registered to another account") from exc
                existing = self._normalize_device_timestamps(existing)
                existing.last_seen_at = now
                if clean_name is not None:
                    existing.friendly_name = clean_name
                try:
                    updated = await self.device_repo.update(existing)
                    return self._normalize_device_timestamps(updated)
                except RepositoryError as update_exc:
                    raise DeviceServiceError("Database error updating device after race") from update_exc

            raise DeviceServiceError("Failed to register device due to duplicate constraint") from exc
        except RepositoryError as exc:
            logger.error("Repository error creating device in register_device")
            raise DeviceServiceError("Database error creating device") from exc

    async def touch_device(self, account_id: uuid.UUID, device_guid: str) -> Device:
        """
        Update only last_seen_at timestamp for an active device. Nothing else.
        Verifies ownership against account_id.
        Raises DeviceNotFoundError if missing, InactiveDeviceError if deactivated.
        """
        device = await self._get_and_verify_ownership(account_id, device_guid, for_update=True)

        if not device.is_active:
            logger.info("Attempted touch on deactivated device")
            raise InactiveDeviceError("Device is deactivated")

        device.last_seen_at = datetime.now(timezone.utc)
        try:
            updated = await self.device_repo.update(device)
            return self._normalize_device_timestamps(updated)
        except RepositoryError as exc:
            logger.error("Repository error updating device timestamp in touch_device")
            raise DeviceServiceError("Database error updating device timestamp") from exc

    async def rename_device(
        self, account_id: uuid.UUID, device_guid: str, friendly_name: str
    ) -> Device:
        """
        Rename friendly_name of a device.
        Must verify ownership. Return updated entity.
        Does NOT update last_seen_at.
        """
        clean_name = self._validate_friendly_name(friendly_name)
        if clean_name is None:
            raise DeviceServiceError("Device friendly name cannot be None")

        device = await self._get_and_verify_ownership(account_id, device_guid, for_update=True)

        if not device.is_active:
            logger.info("Attempted rename on deactivated device")
            raise InactiveDeviceError("Device is deactivated")

        device.friendly_name = clean_name
        try:
            updated = await self.device_repo.update(device)
            return self._normalize_device_timestamps(updated)
        except RepositoryError as exc:
            logger.error("Repository error renaming device")
            raise DeviceServiceError("Database error renaming device") from exc

    async def deactivate_device(
        self, account_id: uuid.UUID, device_guid: str
    ) -> Device:
        """
        Soft deactivate device. Do NOT delete. Set is_active=False.
        Must verify ownership.
        If already deactivated -> raise InactiveDeviceError.
        """
        device = await self._get_and_verify_ownership(account_id, device_guid, for_update=True)

        if not device.is_active:
            logger.info("Attempted deactivation on already deactivated device")
            raise InactiveDeviceError("Device is already deactivated")

        device.is_active = False
        try:
            updated = await self.device_repo.update(device)
            return self._normalize_device_timestamps(updated)
        except RepositoryError as exc:
            logger.error("Repository error deactivating device")
            raise DeviceServiceError("Database error deactivating device") from exc

    async def reactivate_device(
        self, account_id: uuid.UUID, device_guid: str
    ) -> Device:
        """
        Reactivate a deactivated device.
        Must verify ownership and enforce subscription plan device limit.
        If already active -> raise InactiveDeviceError.
        """
        device = await self._get_and_verify_ownership(account_id, device_guid, for_update=True)

        if device.is_active:
            logger.info("Attempted reactivation on already active device")
            raise InactiveDeviceError("Device is already active")

        try:
            account = await self.account_repo.get_by_id(account_id, for_update=True)
            if account is None:
                raise DeviceServiceError("Account not found")
            active_count = await self.device_repo.count_active_devices_for_account(account_id)
        except RepositoryError as exc:
            logger.error("Repository error checking active devices in reactivate_device")
            raise DeviceServiceError("Database error checking device limit") from exc

        if self.plan_service.device_limit_reached(account, active_count):
            logger.info("Device reactivation rejected due to subscription policy.")
            max_devices = self.plan_service.get_max_devices(account)
            raise DeviceLimitExceededError(active_count, max_devices, account.plan_id)

        device.is_active = True
        try:
            updated = await self.device_repo.update(device)
            return self._normalize_device_timestamps(updated)
        except RepositoryError as exc:
            logger.error("Repository error reactivating device")
            raise DeviceServiceError("Database error reactivating device") from exc

    async def get_device(
        self, account_id: uuid.UUID, device_guid: str
    ) -> Device:
        """
        Retrieve a device by GUID.
        Must verify ownership.
        """
        return await self._get_and_verify_ownership(account_id, device_guid)

    async def get_devices_for_account(
        self, account_id: uuid.UUID
    ) -> list[Device]:
        """
        List all devices registered to an account, ordered by most recently seen first.
        Raises DeviceServiceError if the account does not exist.
        """
        try:
            account = await self.account_repo.get_by_id(account_id)
        except RepositoryError as exc:
            logger.error("Repository error checking account in get_devices_for_account")
            raise DeviceServiceError("Database error checking account existence") from exc

        if account is None:
            raise DeviceServiceError("Account not found")

        try:
            devices = await self.device_repo.get_devices_for_account(account_id)
            return [self._normalize_device_timestamps(d) for d in devices]
        except RepositoryError as exc:
            logger.error("Repository error querying devices for account")
            raise DeviceServiceError("Database error querying devices for account") from exc
