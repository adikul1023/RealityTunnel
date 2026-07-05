"""add concurrency partial unique indexes

Revision ID: b7c8d9e0f1a2
Revises: f3e6ac6cd9bb
Create Date: 2026-07-05 15:15:00.000000+00:00

Findings C-2, M-1, M-10: SELECT ... FOR UPDATE cannot lock rows that do not exist yet.
These partial unique indexes enforce one-active-subscription-per-account,
one-pending-retry-per-account, and complement payment idempotency_key uniqueness.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "f3e6ac6cd9bb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX uq_subscriptions_one_active_per_account
        ON subscriptions (account_id)
        WHERE status IN ('TRIAL', 'ACTIVE', 'GRACE')
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_provisioning_retry_one_pending_per_account
        ON provisioning_retry_queue (account_id)
        WHERE status = 'PENDING'
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS uq_provisioning_retry_one_pending_per_account"
    )
    op.execute(
        "DROP INDEX IF EXISTS uq_subscriptions_one_active_per_account"
    )
