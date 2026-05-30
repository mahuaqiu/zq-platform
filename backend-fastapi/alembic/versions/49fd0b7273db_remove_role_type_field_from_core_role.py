"""remove role_type field from core_role

Revision ID: 49fd0b7273db
Revises: 09a1129cda0c
Create Date: 2026-05-31 01:38:47.711980

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '49fd0b7273db'
down_revision: Union[str, None] = '09a1129cda0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 删除索引
    op.drop_index('ix_core_role_role_type', table_name='core_role')
    # 删除字段
    op.drop_column('core_role', 'role_type')


def downgrade() -> None:
    # 添加字段
    op.add_column('core_role', sa.Column('role_type', sa.Integer(), nullable=True, comment='角色类型（0-系统角色, 1-自定义角色）'))
    # 创建索引
    op.create_index('ix_core_role_role_type', 'core_role', ['role_type'], unique=False)
