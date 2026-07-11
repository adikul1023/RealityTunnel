"""Add totp fields to accounts

Revision ID: c9a8b7d6e5f4
Revises: bb8a897d6ba5
Create Date: 2026-07-11 12:00:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision: str = 'c9a8b7d6e5f4'
down_revision: Union[str, None] = 'bb8a897d6ba5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('accounts', sa.Column('totp_secret_encrypted', sa.Text(), nullable=True))
    op.add_column('accounts', sa.Column('totp_enabled', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('accounts', sa.Column('totp_backup_codes_json', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('accounts', 'totp_backup_codes_json')
    op.drop_column('accounts', 'totp_enabled')
    op.drop_column('accounts', 'totp_secret_encrypted')
