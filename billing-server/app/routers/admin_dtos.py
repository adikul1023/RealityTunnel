"""
admin_dtos.py — Re-exports administrative DTOs from app.services.admin_dtos for backward compatibility.
"""
from app.services.admin_dtos import (
    AdminAccountResponse,
    AdminAccountListResponse,
    AdminDeviceResponse,
    AdminDeviceListResponse,
    AdminSignalResponse,
    AdminSignalListResponse,
    AdminLogoutAllResponse,
    ExtendSubscriptionRequest,
)

__all__ = [
    "AdminAccountResponse",
    "AdminAccountListResponse",
    "AdminDeviceResponse",
    "AdminDeviceListResponse",
    "AdminSignalResponse",
    "AdminSignalListResponse",
    "AdminLogoutAllResponse",
    "ExtendSubscriptionRequest",
]
