"""
payment.py — Payment entity representing billing transactions and gateway order lifecycle.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, DateTime, Enum as SQLEnum, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.subscription import Subscription


class PaymentStatus(str, Enum):
    """
    Lifecycle state of a payment transaction.
    """
    CREATED = "CREATED"
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"


class PaymentProviderType(str, Enum):
    """
    Supported payment gateway providers.
    """
    RAZORPAY = "RAZORPAY"


class Payment(Base, TimestampMixin):
    """
    Payments table.
    Stores order identifiers, monetary amounts in minor units (e.g. paise/cents),
    idempotency keys, and verification status.
    Never stores credit card numbers, CVV, UPI PINs, or raw bank secrets.
    """
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider: Mapped[PaymentProviderType] = mapped_column(
        SQLEnum(
            PaymentProviderType,
            name="payment_provider_type",
            create_constraint=True,
            native_enum=True,
        ),
        nullable=False,
        default=PaymentProviderType.RAZORPAY,
        index=True,
    )
    provider_payment_id: Mapped[str | None] = mapped_column(
        String(128), index=True, nullable=True
    )
    provider_order_id: Mapped[str | None] = mapped_column(
        String(128), index=True, nullable=True
    )
    amount_minor_units: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="INR"
    )
    status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(
            PaymentStatus,
            name="payment_status",
            create_constraint=True,
            native_enum=True,
        ),
        nullable=False,
        default=PaymentStatus.CREATED,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    account: Mapped["Account"] = relationship("Account")
    subscription: Mapped["Subscription | None"] = relationship("Subscription")
