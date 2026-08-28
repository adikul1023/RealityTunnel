"""add_partially_refunded_status

Revision ID: 16a49510ad7c
Revises: 942c504696cf
Create Date: 2026-07-19 05:46:36.824010+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision: str = '16a49510ad7c'
down_revision: Union[str, None] = '942c504696cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE payment_status ADD VALUE IF NOT EXISTS 'PARTIALLY_REFUNDED'")


def downgrade() -> None:
    pass
