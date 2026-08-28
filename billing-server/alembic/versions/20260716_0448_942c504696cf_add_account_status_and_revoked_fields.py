"""Add account status and revoked fields

Revision ID: 942c504696cf
Revises: a1b2c3d4e5f0
Create Date: 2026-07-16 04:48:11.968840

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '942c504696cf'
down_revision: Union[str, None] = 'a1b2c3d4e5f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Add deleted_at to accounts
    op.add_column('accounts', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_accounts_deleted_at'), 'accounts', ['deleted_at'], unique=False)
    
    # 2. Add revoked_by, revoked_at, revoke_reason to subscriptions
    op.add_column('subscriptions', sa.Column('revoked_by', sa.Uuid(as_uuid=True), nullable=True))
    op.add_column('subscriptions', sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('subscriptions', sa.Column('revoke_reason', sa.String(length=255), nullable=True))
    
    op.create_index(op.f('ix_subscriptions_revoked_by'), 'subscriptions', ['revoked_by'], unique=False)
    op.create_foreign_key('fk_subscriptions_revoked_by', 'subscriptions', 'admin_users', ['revoked_by'], ['id'], ondelete='SET NULL')

    # 3. Create account_status ENUM
    account_status_enum = postgresql.ENUM('ACTIVE', 'EXPIRED', 'SUSPENDED', 'PENDING', 'DELETED', name='account_status', create_type=False)
    account_status_enum.create(op.get_bind(), checkfirst=True)

    # 4. Convert accounts.status from subscription_status to account_status
    # We use a raw SQL ALTER TABLE because Alembic's drop/recreate on ENUMs can be tricky.
    op.execute(
        "ALTER TABLE accounts ALTER COLUMN status DROP DEFAULT;"
    )
    op.execute(
        "ALTER TABLE accounts ALTER COLUMN status TYPE account_status USING status::text::account_status;"
    )
    op.execute(
        "ALTER TABLE accounts ALTER COLUMN status SET DEFAULT 'PENDING'::account_status;"
    )

    # 5. Add REVOKED to subscription_lifecycle_status if not exists
    op.execute("ALTER TYPE subscription_lifecycle_status ADD VALUE IF NOT EXISTS 'REVOKED';")

    # 6. Add action column to provisioning_retry_queue
    provisioning_action_enum = postgresql.ENUM('PROVISION', 'TERMINATE', 'SUSPEND', name='provisioning_action', create_type=False)
    provisioning_action_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('provisioning_retry_queue', sa.Column('action', postgresql.ENUM('PROVISION', 'TERMINATE', 'SUSPEND', name='provisioning_action', create_type=False), server_default='PROVISION', nullable=False))

def downgrade() -> None:
    # Drop action column
    op.drop_column('provisioning_retry_queue', 'action')
    provisioning_action_enum = postgresql.ENUM('PROVISION', 'TERMINATE', 'SUSPEND', name='provisioning_action', create_type=False)
    provisioning_action_enum.drop(op.get_bind(), checkfirst=True)
    # In downgrade, we just switch back the column type to subscription_status.
    # We will NOT drop the REVOKED or DELETED enum values since PostgreSQL doesn't support DROP VALUE cleanly.
    op.execute(
        "ALTER TABLE accounts ALTER COLUMN status DROP DEFAULT;"
    )
    op.execute(
        "ALTER TABLE accounts ALTER COLUMN status TYPE subscription_status USING status::text::subscription_status;"
    )
    op.execute(
        "ALTER TABLE accounts ALTER COLUMN status SET DEFAULT 'PENDING'::subscription_status;"
    )
    
    # Drop columns
    op.drop_constraint('fk_subscriptions_revoked_by', 'subscriptions', type_='foreignkey')
    op.drop_index(op.f('ix_subscriptions_revoked_by'), table_name='subscriptions')
    op.drop_column('subscriptions', 'revoke_reason')
    op.drop_column('subscriptions', 'revoked_at')
    op.drop_column('subscriptions', 'revoked_by')
    
    op.drop_index(op.f('ix_accounts_deleted_at'), table_name='accounts')
    op.drop_column('accounts', 'deleted_at')
    
    # Drop account_status ENUM type
    account_status_enum = postgresql.ENUM('ACTIVE', 'EXPIRED', 'SUSPENDED', 'PENDING', 'DELETED', name='account_status', create_type=False)
    account_status_enum.drop(op.get_bind(), checkfirst=True)
