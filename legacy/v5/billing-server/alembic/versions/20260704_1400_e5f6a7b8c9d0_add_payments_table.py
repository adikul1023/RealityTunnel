"""add payments table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-04 14:00:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'payments',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('account_id', sa.Uuid(), nullable=False),
        sa.Column('subscription_id', sa.Uuid(), nullable=True),
        sa.Column(
            'provider',
            sa.Enum('RAZORPAY', name='payment_provider_type', create_constraint=True),
            nullable=False
        ),
        sa.Column('provider_payment_id', sa.String(length=128), nullable=True),
        sa.Column('provider_order_id', sa.String(length=128), nullable=True),
        sa.Column('amount_minor_units', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column(
            'status',
            sa.Enum('CREATED', 'PENDING', 'PAID', 'FAILED', 'REFUNDED', 'CANCELLED', name='payment_status', create_constraint=True),
            nullable=False
        ),
        sa.Column('idempotency_key', sa.String(length=128), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_payments_account_id'), 'payments', ['account_id'], unique=False)
    op.create_index(op.f('ix_payments_subscription_id'), 'payments', ['subscription_id'], unique=False)
    op.create_index(op.f('ix_payments_provider'), 'payments', ['provider'], unique=False)
    op.create_index(op.f('ix_payments_provider_payment_id'), 'payments', ['provider_payment_id'], unique=False)
    op.create_index(op.f('ix_payments_provider_order_id'), 'payments', ['provider_order_id'], unique=False)
    op.create_index(op.f('ix_payments_status'), 'payments', ['status'], unique=False)
    op.create_index(op.f('ix_payments_idempotency_key'), 'payments', ['idempotency_key'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_payments_idempotency_key'), table_name='payments')
    op.drop_index(op.f('ix_payments_status'), table_name='payments')
    op.drop_index(op.f('ix_payments_provider_order_id'), table_name='payments')
    op.drop_index(op.f('ix_payments_provider_payment_id'), table_name='payments')
    op.drop_index(op.f('ix_payments_provider'), table_name='payments')
    op.drop_index(op.f('ix_payments_subscription_id'), table_name='payments')
    op.drop_index(op.f('ix_payments_account_id'), table_name='payments')
    op.drop_table('payments')

    sa.Enum('CREATED', 'PENDING', 'PAID', 'FAILED', 'REFUNDED', 'CANCELLED', name='payment_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum('RAZORPAY', name='payment_provider_type').drop(op.get_bind(), checkfirst=True)
