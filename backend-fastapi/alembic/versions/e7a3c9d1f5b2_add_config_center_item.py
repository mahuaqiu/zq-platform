"""add config_center_item table

Revision ID: e7a3c9d1f5b2
Revises: b1c2d3e4f5a6
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7a3c9d1f5b2'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('config_center_item',
    sa.Column('key', sa.String(length=64), nullable=False, comment='配置键'),
    sa.Column('value', sa.Text(), nullable=False, comment='配置值(JSON对象字符串)'),
    sa.Column('remark', sa.Text(), nullable=True, comment='备注'),
    sa.Column('id', sa.String(length=21), nullable=False, comment='主键ID(NanoId)'),
    sa.Column('sort', sa.Integer(), nullable=True, comment='排序'),
    sa.Column('is_deleted', sa.Boolean(), nullable=True, comment='是否删除'),
    sa.Column('sys_create_datetime', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='创建时间'),
    sa.Column('sys_update_datetime', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='更新时间'),
    sa.Column('sys_creator_id', sa.String(length=21), nullable=True, comment='创建人ID（逻辑外键关联core_user）'),
    sa.Column('sys_modifier_id', sa.String(length=21), nullable=True, comment='修改人ID（逻辑外键关联core_user）'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_config_center_item_is_deleted'), 'config_center_item', ['is_deleted'], unique=False)
    op.create_index('ix_config_center_item_key', 'config_center_item', ['key'], unique=False)
    op.create_index('uq_config_center_item_active_key', 'config_center_item', ['key'], unique=True,
                    postgresql_where=sa.text('is_deleted = false'))


def downgrade() -> None:
    op.drop_index('uq_config_center_item_active_key', table_name='config_center_item')
    op.drop_index(op.f('ix_config_center_item_is_deleted'), table_name='config_center_item')
    op.drop_index('ix_config_center_item_key', table_name='config_center_item')
    op.drop_table('config_center_item')
