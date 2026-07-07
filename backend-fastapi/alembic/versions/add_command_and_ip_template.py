"""Add command field and new tables for command template

Revision ID: add_command_and_ip_template
Revises: 2054c5680962
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_command_and_ip_template'
down_revision = '2054c5680962'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 为 config_template 表添加 command 字段
    op.add_column('config_template', sa.Column('command', sa.Text(), nullable=True, comment='命令内容'))

    # 2. 创建 machine_selection_template 表（IP模板）
    op.create_table(
        'machine_selection_template',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('name', sa.String(64), nullable=False, unique=True, comment='模板名称'),
        sa.Column('namespace', sa.String(64), nullable=True, comment='命名空间筛选'),
        sa.Column('device_type', sa.String(20), nullable=True, comment='设备类型筛选'),
        sa.Column('ip_pattern', sa.String(64), nullable=True, comment='IP模糊匹配'),
        sa.Column('machine_ids', postgresql.JSON(astext_type=sa.Text()), nullable=True, comment='固定机器ID列表'),
        sa.Column('note', sa.Text(), nullable=True, comment='备注说明'),
        sa.Column('version', sa.String(20), nullable=False, comment='版本号'),
        sa.Column('sort', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('sys_create_datetime', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('sys_update_datetime', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('sys_creator_id', sa.String(50), nullable=True),
        sa.Column('sys_modifier_id', sa.String(50), nullable=True),
    )
    op.create_index('ix_machine_selection_template_namespace', 'machine_selection_template', ['namespace'])

    # 3. 创建 command_task 表（任务历史）
    op.create_table(
        'command_task',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('template_id', sa.String(50), nullable=True, comment='关联模板ID'),
        sa.Column('template_type', sa.String(20), nullable=False, comment='模板类型'),
        sa.Column('template_name', sa.String(64), nullable=False, comment='模板名称'),
        sa.Column('command', sa.Text(), nullable=True, comment='命令内容'),
        sa.Column('machine_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='running'),
        sa.Column('success_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('result_detail', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('finished_datetime', sa.DateTime(), nullable=True),
        sa.Column('sort', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('sys_create_datetime', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('sys_update_datetime', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('sys_creator_id', sa.String(50), nullable=True),
        sa.Column('sys_modifier_id', sa.String(50), nullable=True),
    )
    op.create_index('ix_command_task_template_type', 'command_task', ['template_type'])
    op.create_index('ix_command_task_status', 'command_task', ['status'])
    op.create_index('ix_command_task_create_datetime', 'command_task', ['sys_create_datetime'])


def downgrade() -> None:
    op.drop_table('command_task')
    op.drop_table('machine_selection_template')
    op.drop_column('config_template', 'command')
