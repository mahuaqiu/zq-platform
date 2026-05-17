"""add time_ranges to performance_version

Revision ID: e5f6g7h8i9j0
Revises: 4b93d2252d21
Create Date: 2026-05-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6g7h8i9j0'
down_revision: Union[str, None] = '4b93d2252d21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 添加 time_ranges 字段到 performance_version 表
    op.add_column(
        'performance_version',
        sa.Column('time_ranges', sa.JSON(), nullable=True, comment='时间范围映射: {collect_id: {start, end}}')
    )


def downgrade() -> None:
    op.drop_column('performance_version', 'time_ranges')