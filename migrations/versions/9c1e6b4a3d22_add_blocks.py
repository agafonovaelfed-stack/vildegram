"""add blocks
Revision ID: 9c1e6b4a3d22
Revises: 7f8ca4471cff
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='9c1e6b4a3d22'; down_revision='7f8ca4471cff'; branch_labels=None; depends_on=None

def upgrade() -> None:
    op.create_table('blocks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('blocker_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('blocked_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['blocker_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['blocked_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('blocker_id','blocked_id',name='uq_block_pair'))
    op.create_index('ix_blocks_blocker_id','blocks',['blocker_id'])
    op.create_index('ix_blocks_blocked_id','blocks',['blocked_id'])

def downgrade() -> None:
    op.drop_index('ix_blocks_blocked_id', table_name='blocks'); op.drop_index('ix_blocks_blocker_id', table_name='blocks'); op.drop_table('blocks')
