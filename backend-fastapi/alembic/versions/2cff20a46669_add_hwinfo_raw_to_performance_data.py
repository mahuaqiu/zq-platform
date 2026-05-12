"""add hwinfo_raw to performance_data

Revision ID: 2cff20a46669
Revises: d4e5f6g7h8i9
Create Date: 2026-05-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2cff20a46669'
down_revision: Union[str, None] = 'd4e5f6g7h8i9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 添加 performance_data.hwinfo_raw 列
    op.add_column('performance_data', sa.Column('hwinfo_raw', sa.JSON(), nullable=True, comment='HWiNFO原始传感器数据（完整）'))

    # 2. 创建 performance_metric_mapping 表（指标映射）
    op.create_table(
        'performance_metric_mapping',
        sa.Column('hwinfo_key', sa.String(length=100), nullable=False, comment='HWiNFO传感器键名'),
        sa.Column('display_name', sa.String(length=100), nullable=False, comment='中文显示名称'),
        sa.Column('category', sa.String(length=20), nullable=False, comment='指标分类'),
        sa.Column('is_primary', sa.Boolean(), nullable=False, comment='是否常用指标'),
        sa.Column('unit', sa.String(length=20), nullable=True, comment='单位'),
        sa.Column('sort', sa.Integer(), nullable=False, comment='排序'),
        sa.Column('id', sa.String(length=50), nullable=False, comment='主键ID(NanoId)'),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, comment='是否删除'),
        sa.Column('sys_create_datetime', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='创建时间'),
        sa.Column('sys_update_datetime', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='更新时间'),
        sa.Column('sys_creator_id', sa.String(length=50), nullable=True, comment='创建人ID'),
        sa.Column('sys_modifier_id', sa.String(length=50), nullable=True, comment='修改人ID'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_performance_metric_mapping_hwinfo_key', 'performance_metric_mapping', ['hwinfo_key'], unique=True)
    op.create_index('ix_performance_metric_mapping_is_deleted', 'performance_metric_mapping', ['is_deleted'], unique=False)

    # 3. 创建 performance_marker 表（标记）
    op.create_table(
        'performance_marker',
        sa.Column('collect_id', sa.String(length=21), nullable=False, comment='采集记录ID'),
        sa.Column('name', sa.String(length=50), nullable=False, comment='标记名称'),
        sa.Column('start_time', sa.Integer(), nullable=False, comment='开始时间'),
        sa.Column('end_time', sa.Integer(), nullable=True, comment='结束时间'),
        sa.Column('color', sa.String(length=10), nullable=False, comment='标记颜色'),
        sa.Column('note', sa.String(length=200), nullable=True, comment='备注信息'),
        sa.Column('id', sa.String(length=50), nullable=False, comment='主键ID(NanoId)'),
        sa.Column('sort', sa.Integer(), nullable=True, comment='排序'),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, comment='是否删除'),
        sa.Column('sys_create_datetime', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='创建时间'),
        sa.Column('sys_update_datetime', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='更新时间'),
        sa.Column('sys_creator_id', sa.String(length=50), nullable=True, comment='创建人ID'),
        sa.Column('sys_modifier_id', sa.String(length=50), nullable=True, comment='修改人ID'),
        sa.ForeignKeyConstraint(['collect_id'], ['performance_collect.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_performance_marker_collect_id', 'performance_marker', ['collect_id'], unique=False)
    op.create_index('ix_performance_marker_is_deleted', 'performance_marker', ['is_deleted'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_performance_marker_is_deleted', table_name='performance_marker')
    op.drop_index('ix_performance_marker_collect_id', table_name='performance_marker')
    op.drop_table('performance_marker')

    op.drop_index('ix_performance_metric_mapping_is_deleted', table_name='performance_metric_mapping')
    op.drop_index('ix_performance_metric_mapping_hwinfo_key', table_name='performance_metric_mapping')
    op.drop_table('performance_metric_mapping')

    op.drop_column('performance_data', 'hwinfo_raw')