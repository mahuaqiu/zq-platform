"""add performance_monitor tables

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-05-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. performance_collect 表
    op.create_table(
        'performance_collect',
        sa.Column('device_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(100), nullable=True),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('interval', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('target_processes', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='running'),
        sa.Column('is_protected', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('id', sa.String(50), nullable=False),
        sa.Column('sort', sa.Integer(), server_default='0'),
        sa.Column('is_deleted', sa.Boolean(), server_default='false'),
        sa.Column('sys_create_datetime', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('sys_update_datetime', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('sys_creator_id', sa.String(50), nullable=True),
        sa.Column('sys_modifier_id', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        comment='性能采集记录表'
    )
    op.create_index('ix_performance_collect_device_id', 'performance_collect', ['device_id'])
    op.create_index('ix_performance_collect_status', 'performance_collect', ['status'])
    op.create_index('ix_performance_collect_is_deleted', 'performance_collect', ['is_deleted'])

    # 2. performance_data 表
    op.create_table(
        'performance_data',
        sa.Column('collect_id', sa.String(50), sa.ForeignKey('performance_collect.id'), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('relative_time', sa.Integer(), nullable=False),
        sa.Column('cpu_usage', sa.Float(), nullable=True),
        sa.Column('gpu_usage', sa.Float(), nullable=True),
        sa.Column('commit_memory', sa.Float(), nullable=True),
        sa.Column('memory_usage', sa.Float(), nullable=True),
        sa.Column('power', sa.Float(), nullable=True),
        sa.Column('cpu_speed', sa.Float(), nullable=True),
        sa.Column('cpu_temp', sa.Float(), nullable=True),
        sa.Column('process_handles', sa.Integer(), nullable=True),
        sa.Column('upload_speed', sa.Float(), nullable=True),
        sa.Column('download_speed', sa.Float(), nullable=True),
        sa.Column('target_processes', sa.JSON(), nullable=True),
        sa.Column('top10_cpu', sa.JSON(), nullable=True),
        sa.Column('top10_gpu', sa.JSON(), nullable=True),
        sa.Column('id', sa.String(50), nullable=False),
        sa.Column('sort', sa.Integer(), server_default='0'),
        sa.Column('is_deleted', sa.Boolean(), server_default='false'),
        sa.Column('sys_create_datetime', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('sys_update_datetime', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('sys_creator_id', sa.String(50), nullable=True),
        sa.Column('sys_modifier_id', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        comment='性能数据表'
    )
    op.create_index('ix_performance_data_collect_id', 'performance_data', ['collect_id'])
    op.create_index('ix_performance_data_is_deleted', 'performance_data', ['is_deleted'])

    # 3. performance_tag 表
    op.create_table(
        'performance_tag',
        sa.Column('collect_id', sa.String(50), sa.ForeignKey('performance_collect.id'), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('start_relative_time', sa.Integer(), nullable=False),
        sa.Column('duration', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(20), nullable=False, server_default='peak'),
        sa.Column('id', sa.String(50), nullable=False),
        sa.Column('sort', sa.Integer(), server_default='0'),
        sa.Column('is_deleted', sa.Boolean(), server_default='false'),
        sa.Column('sys_create_datetime', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('sys_update_datetime', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('sys_creator_id', sa.String(50), nullable=True),
        sa.Column('sys_modifier_id', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        comment='性能标签表'
    )
    op.create_index('ix_performance_tag_collect_id', 'performance_tag', ['collect_id'])
    op.create_index('ix_performance_tag_is_deleted', 'performance_tag', ['is_deleted'])

    # 4. performance_version 表
    op.create_table(
        'performance_version',
        sa.Column('device_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('collect_ids', sa.JSON(), nullable=False),
        sa.Column('is_protected', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('id', sa.String(50), nullable=False),
        sa.Column('sort', sa.Integer(), server_default='0'),
        sa.Column('is_deleted', sa.Boolean(), server_default='false'),
        sa.Column('sys_create_datetime', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('sys_update_datetime', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('sys_creator_id', sa.String(50), nullable=True),
        sa.Column('sys_modifier_id', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        comment='性能版本对比表'
    )
    op.create_index('ix_performance_version_device_id', 'performance_version', ['device_id'])
    op.create_index('ix_performance_version_is_deleted', 'performance_version', ['is_deleted'])


def downgrade() -> None:
    op.drop_table('performance_version')
    op.drop_table('performance_tag')
    op.drop_table('performance_data')
    op.drop_table('performance_collect')