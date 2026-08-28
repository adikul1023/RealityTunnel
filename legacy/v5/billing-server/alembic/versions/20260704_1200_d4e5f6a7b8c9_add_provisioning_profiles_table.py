"""add provisioning profiles table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-04 12:00:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'provisioning_profiles',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('account_id', sa.Uuid(), nullable=False),
        sa.Column('remote_user_id', sa.String(length=128), nullable=False),
        sa.Column(
            'provisioning_state',
            sa.Enum('PENDING', 'ACTIVE', 'SUSPENDED', 'TERMINATED', 'FAILED', 'SYNCHRONIZED', name='provisioning_state', create_constraint=True),
            nullable=False
        ),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_provisioning_profiles_account_id'), 'provisioning_profiles', ['account_id'], unique=True)
    op.create_index(op.f('ix_provisioning_profiles_remote_user_id'), 'provisioning_profiles', ['remote_user_id'], unique=True)
    op.create_index(op.f('ix_provisioning_profiles_provisioning_state'), 'provisioning_profiles', ['provisioning_state'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_provisioning_profiles_provisioning_state'), table_name='provisioning_profiles')
    op.drop_index(op.f('ix_provisioning_profiles_remote_user_id'), table_name='provisioning_profiles')
    op.drop_index(op.f('ix_provisioning_profiles_account_id'), table_name='provisioning_profiles')
    op.drop_table('provisioning_profiles')

    sa.Enum('PENDING', 'ACTIVE', 'SUSPENDED', 'TERMINATED', 'FAILED', 'SYNCHRONIZED', name='provisioning_state').drop(op.get_bind(), checkfirst=True)
