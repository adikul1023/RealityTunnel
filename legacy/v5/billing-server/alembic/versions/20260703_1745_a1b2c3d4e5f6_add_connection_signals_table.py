"""add connection_signals table

Revision ID: a1b2c3d4e5f6
Revises: f942c8c3d8fe
Create Date: 2026-07-03 17:45:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f942c8c3d8fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'connection_signals',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('account_id', sa.Uuid(), nullable=True),
        sa.Column('device_guid', sa.String(length=64), nullable=True),
        sa.Column(
            'event_type',
            sa.Enum(
                'LOGIN',
                'REFRESH',
                'LOGOUT',
                'LOGOUT_ALL',
                'DEVICE_REGISTER',
                'DEVICE_RENAME',
                'DEVICE_DEACTIVATE',
                'DEVICE_REACTIVATE',
                name='connection_event_type',
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column('source_ip', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=512), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('success', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_connection_signals_account_id'), 'connection_signals', ['account_id'], unique=False)
    op.create_index(op.f('ix_connection_signals_device_guid'), 'connection_signals', ['device_guid'], unique=False)
    op.create_index(op.f('ix_connection_signals_event_type'), 'connection_signals', ['event_type'], unique=False)
    op.create_index(op.f('ix_connection_signals_occurred_at'), 'connection_signals', ['occurred_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_connection_signals_occurred_at'), table_name='connection_signals')
    op.drop_index(op.f('ix_connection_signals_event_type'), table_name='connection_signals')
    op.drop_index(op.f('ix_connection_signals_device_guid'), table_name='connection_signals')
    op.drop_index(op.f('ix_connection_signals_account_id'), table_name='connection_signals')
    op.drop_table('connection_signals')
    sa.Enum(name='connection_event_type').drop(op.get_bind(), checkfirst=True)
