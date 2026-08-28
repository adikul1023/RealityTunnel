"""refine device schema for phase 1.4.1 lifecycle

Revision ID: 47f3ed1f7c48
Revises: de60c540a56e
Create Date: 2026-07-03 10:14:35.127116+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision: str = '47f3ed1f7c48'
down_revision: Union[str, None] = 'de60c540a56e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('devices', 'name', new_column_name='friendly_name', existing_type=sa.String(length=100), existing_nullable=True)
    op.alter_column('devices', 'registered_at', new_column_name='first_seen_at', existing_type=sa.DateTime(timezone=True), existing_nullable=False)
    op.add_column('devices', sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    op.drop_constraint('uq_account_device_guid', 'devices', type_='unique')
    op.drop_index(op.f('ix_devices_device_guid'), table_name='devices')
    op.create_index(op.f('ix_devices_device_guid'), 'devices', ['device_guid'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_devices_device_guid'), table_name='devices')
    op.create_index(op.f('ix_devices_device_guid'), 'devices', ['device_guid'], unique=False)
    op.create_unique_constraint('uq_account_device_guid', 'devices', ['account_id', 'device_guid'])
    op.drop_column('devices', 'is_active')
    op.alter_column('devices', 'first_seen_at', new_column_name='registered_at', existing_type=sa.DateTime(timezone=True), existing_nullable=False)
    op.alter_column('devices', 'friendly_name', new_column_name='name', existing_type=sa.String(length=100), existing_nullable=True)

