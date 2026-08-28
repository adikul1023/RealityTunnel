"""cleanup_legacy_inactive_devices

Revision ID: a1b2c3d4e5f0
Revises: fef6d30f8d78
Create Date: 2026-07-13 18:45:00.000000+00:00

Architecture Change Note:
-------------------------
Before Phase 10.3C:
  Remove Device -> sets is_active = false

After Phase 10.3C:
  Remove Device -> DELETE row (hard delete)
  Suspend Device -> sets is_active = false

This data migration ensures that any legacy inactive device records created under
the old "Remove = Soft Deactivate" semantics are permanently removed so they do not
block re-registration or login of the same device GUID under the new semantics.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision: str = 'a1b2c3d4e5f0'
down_revision: Union[str, None] = 'fef6d30f8d78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Permanently delete legacy soft-deactivated device records
    op.execute("DELETE FROM devices WHERE is_active = false;")


def downgrade() -> None:
    # Data deletion is irreversible; no-op on downgrade
    pass
