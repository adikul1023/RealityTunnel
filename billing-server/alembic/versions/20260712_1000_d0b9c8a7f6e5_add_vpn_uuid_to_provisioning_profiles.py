"""add vpn_uuid to provisioning_profiles

Revision ID: d0b9c8a7f6e5
Revises: c9a8b7d6e5f4
Create Date: 2026-07-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0b9c8a7f6e5'
down_revision: Union[str, None] = 'c9a8b7d6e5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('provisioning_profiles', sa.Column('vpn_uuid', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_provisioning_profiles_vpn_uuid'), 'provisioning_profiles', ['vpn_uuid'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_provisioning_profiles_vpn_uuid'), table_name='provisioning_profiles')
    op.drop_column('provisioning_profiles', 'vpn_uuid')
