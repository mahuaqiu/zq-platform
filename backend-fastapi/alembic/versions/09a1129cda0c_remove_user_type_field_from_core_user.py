"""remove user_type field from core_user

Revision ID: 09a1129cda0c
Revises: 99d94b1db380
Create Date: 2026-05-31 01:07:36.650440

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '09a1129cda0c'
down_revision: Union[str, None] = '99d94b1db380'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 删除索引
    op.drop_index('ix_core_user_user_type', table_name='core_user')
    # 删除字段
    op.drop_column('core_user', 'user_type')


def downgrade() -> None:
    # 添加字段
    op.add_column('core_user', sa.Column('user_type', sa.Integer(), nullable=True, comment='用户类型'))
    # 创建索引
    op.create_index('ix_core_user_user_type', 'core_user', ['user_type'], unique=False)
