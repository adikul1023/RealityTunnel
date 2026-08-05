"""Add agent node and certificate models

Revision ID: 0da549e21c01
Revises: 
Create Date: 2026-08-05 09:36:00.594499+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision: str = '0da549e21c01'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
