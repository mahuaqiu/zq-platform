"""remove post module

Revision ID: remove_post_module
Revises: 8c65b4bf9f40
Create Date: 2026-04-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'remove_post_module'
down_revision: Union[str, None] = '8c65b4bf9f40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 删除 core_user 表中的 post_id 字段和索引
    op.drop_index(op.f('ix_core_user_post_id'), table_name='core_user')
    op.drop_column('core_user', 'post_id')

    # 2. 删除 core_post 表及其所有索引
    op.drop_index(op.f('ix_core_post_status'), table_name='core_post')
    op.drop_index(op.f('ix_core_post_post_type'), table_name='core_post')
    op.drop_index(op.f('ix_core_post_post_level'), table_name='core_post')
    op.drop_index(op.f('ix_core_post_name'), table_name='core_post')
    op.drop_index(op.f('ix_core_post_is_deleted'), table_name='core_post')
    op.drop_index(op.f('ix_core_post_dept_id'), table_name='core_post')
    op.drop_index(op.f('ix_core_post_code'), table_name='core_post')
    op.drop_table('core_post')


def downgrade() -> None:
    # 重新创建 core_post 表
    op.create_table('core_post',
        sa.Column('name', sa.String(length=64), nullable=False, comment='岗位名称'),
        sa.Column('code', sa.String(length=32), nullable=False, comment='岗位编码'),
        sa.Column('post_type', sa.Integer(), nullable=True, comment='岗位类型（0-管理岗, 1-技术岗, 2-业务岗, 3-职能岗, 4-其他）'),
        sa.Column('post_level', sa.Integer(), nullable=True, comment='岗位级别（0-高层, 1-中层, 2-基层, 3-一般员工）'),
        sa.Column('status', sa.Boolean(), nullable=True, comment='岗位状态（启用/禁用）'),
        sa.Column('description', sa.Text(), nullable=True, comment='岗位描述/职责'),
        sa.Column('dept_id', sa.String(length=21), nullable=True, comment='所属部门ID'),
        sa.Column('id', sa.String(length=21), nullable=False),
        sa.Column('sort', sa.Integer(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.Column('sys_create_datetime', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('sys_update_datetime', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('sys_creator_id', sa.String(length=21), nullable=True),
        sa.Column('sys_modifier_id', sa.String(length=21), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    # 创建索引
    op.create_index(op.f('ix_core_post_code'), 'core_post', ['code'], unique=True)
    op.create_index(op.f('ix_core_post_dept_id'), 'core_post', ['dept_id'], unique=False)
    op.create_index(op.f('ix_core_post_name'), 'core_post', ['name'], unique=False)
    op.create_index(op.f('ix_core_post_post_type'), 'core_post', ['post_type'], unique=False)
    op.create_index(op.f('ix_core_post_post_level'), 'core_post', ['post_level'], unique=False)
    op.create_index(op.f('ix_core_post_status'), 'core_post', ['status'], unique=False)
    op.create_index(op.f('ix_core_post_is_deleted'), 'core_post', ['is_deleted'], unique=False)

    # 重新添加 core_user 表中的 post_id 字段
    op.add_column('core_user', sa.Column('post_id', sa.String(length=21), nullable=True, comment='所属岗位ID'))
    op.create_index(op.f('ix_core_user_post_id'), 'core_user', ['post_id'], unique=False)