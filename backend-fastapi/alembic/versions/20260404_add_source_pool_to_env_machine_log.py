"""add source_pool to env_machine_log

Revision ID: 20260404_source_pool
Revises: a1b2c3d4e5f6
Create Date: 2026-04-04

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260404_source_pool'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'env_machine_log',
        sa.Column('source_pool', sa.String(64), nullable=True, comment='机器来源池')
    )


def downgrade() -> None:
    op.drop_column('env_machine_log', 'source_pool')