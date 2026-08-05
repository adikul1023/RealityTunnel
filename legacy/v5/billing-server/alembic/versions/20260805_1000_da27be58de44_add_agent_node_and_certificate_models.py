"""Add agent node and certificate models

Revision ID: da27be58de44
Revises: 0da549e21c01
Create Date: 2026-08-05 10:00:11.907694+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision: str = 'da27be58de44'
down_revision: Union[str, None] = '0da549e21c01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Agent Nodes Table
    op.create_table('agent_nodes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('node_name', sa.String(), nullable=False),
    sa.Column('public_ip', sa.String(), nullable=True),
    sa.Column('region', sa.String(), nullable=True),
    sa.Column('agent_secret_hash', sa.String(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('last_heartbeat_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('node_name')
    )

    # Agent Bootstrap Tokens Table
    op.create_table('agent_bootstrap_tokens',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.String(), nullable=False),
    sa.Column('purpose', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )

    # Agent Certificates Table
    op.create_table('agent_certificates',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('node_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(), server_default='pending', nullable=False),
    sa.Column('encrypted_pfx', sa.Text(), nullable=False),
    sa.Column('encryption_nonce', sa.String(), nullable=False),
    sa.Column('encryption_tag', sa.String(), nullable=False),
    sa.Column('common_name', sa.String(), nullable=False),
    sa.Column('thumbprint_sha256', sa.String(), nullable=False),
    sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False),
    sa.Column('valid_until', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['node_id'], ['agent_nodes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('thumbprint_sha256')
    )


def downgrade() -> None:
    op.drop_table('agent_certificates')
    op.drop_table('agent_bootstrap_tokens')
    op.drop_table('agent_nodes')
