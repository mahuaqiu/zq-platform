"""restore_scheduler_tables

Revision ID: 50c157c4ae43
Revises: 58e19bd042d2
Create Date: 2026-04-03 20:50:06.121809

恢复定时任务相关表
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '50c157c4ae43'
down_revision: Union[str, None] = '58e19bd042d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建定时任务表
    op.create_table('core_scheduler_job',
    sa.Column('name', sa.String(length=128), nullable=False, comment='任务名称'),
    sa.Column('code', sa.String(length=128), nullable=False, comment='任务编码'),
    sa.Column('description', sa.Text(), nullable=True, comment='任务描述'),
    sa.Column('group', sa.String(length=64), nullable=True, comment='任务分组'),
    sa.Column('trigger_type', sa.String(length=20), nullable=True, comment='触发器类型'),
    sa.Column('cron_expression', sa.String(length=128), nullable=True, comment='Cron表达式'),
    sa.Column('interval_seconds', sa.Integer(), nullable=True, comment='间隔时间（秒）'),
    sa.Column('run_date', sa.DateTime(), nullable=True, comment='指定执行时间'),
    sa.Column('task_func', sa.String(length=256), nullable=False, comment='任务函数路径'),
    sa.Column('task_args', sa.Text(), nullable=True, comment='任务位置参数（JSON数组格式）'),
    sa.Column('task_kwargs', sa.Text(), nullable=True, comment='任务关键字参数（JSON对象格式）'),
    sa.Column('status', sa.Integer(), nullable=True, comment='任务状态（0-禁用，1-启用，2-暂停）'),
    sa.Column('priority', sa.Integer(), nullable=True, comment='任务优先级'),
    sa.Column('max_instances', sa.Integer(), nullable=True, comment='最大实例数'),
    sa.Column('max_retries', sa.Integer(), nullable=True, comment='错误重试次数'),
    sa.Column('timeout', sa.Integer(), nullable=True, comment='超时时间（秒）'),
    sa.Column('coalesce', sa.Boolean(), nullable=True, comment='是否合并执行'),
    sa.Column('allow_concurrent', sa.Boolean(), nullable=True, comment='是否允许并发执行'),
    sa.Column('total_run_count', sa.Integer(), nullable=True, comment='总执行次数'),
    sa.Column('success_count', sa.Integer(), nullable=True, comment='成功次数'),
    sa.Column('failure_count', sa.Integer(), nullable=True, comment='失败次数'),
    sa.Column('last_run_time', sa.DateTime(), nullable=True, comment='最后执行时间'),
    sa.Column('next_run_time', sa.DateTime(), nullable=True, comment='下次执行时间'),
    sa.Column('last_run_status', sa.String(length=20), nullable=True, comment='最后执行状态'),
    sa.Column('last_run_result', sa.Text(), nullable=True, comment='最后执行结果'),
    sa.Column('remark', sa.Text(), nullable=True, comment='备注信息'),
    sa.Column('id', sa.String(length=21), nullable=False, comment='主键ID(NanoId)'),
    sa.Column('sort', sa.Integer(), nullable=True, comment='排序'),
    sa.Column('is_deleted', sa.Boolean(), nullable=True, comment='是否删除'),
    sa.Column('sys_create_datetime', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='创建时间'),
    sa.Column('sys_update_datetime', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='更新时间'),
    sa.Column('sys_creator_id', sa.String(length=21), nullable=True, comment='创建人ID（逻辑外键关联core_user）'),
    sa.Column('sys_modifier_id', sa.String(length=21), nullable=True, comment='修改人ID（逻辑外键关联core_user）'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_core_scheduler_job_code'), 'core_scheduler_job', ['code'], unique=True)
    op.create_index(op.f('ix_core_scheduler_job_group'), 'core_scheduler_job', ['group'], unique=False)
    op.create_index(op.f('ix_core_scheduler_job_is_deleted'), 'core_scheduler_job', ['is_deleted'], unique=False)
    op.create_index(op.f('ix_core_scheduler_job_name'), 'core_scheduler_job', ['name'], unique=False)
    op.create_index(op.f('ix_core_scheduler_job_priority'), 'core_scheduler_job', ['priority'], unique=False)
    op.create_index(op.f('ix_core_scheduler_job_status'), 'core_scheduler_job', ['status'], unique=False)
    op.create_index(op.f('ix_core_scheduler_job_trigger_type'), 'core_scheduler_job', ['trigger_type'], unique=False)
    op.create_index('ix_scheduler_job_group_status', 'core_scheduler_job', ['group', 'status'], unique=False)
    op.create_index('ix_scheduler_job_next_run_status', 'core_scheduler_job', ['next_run_time', 'status'], unique=False)
    op.create_index('ix_scheduler_job_priority_status', 'core_scheduler_job', ['priority', 'status'], unique=False)
    op.create_index('ix_scheduler_job_status_trigger', 'core_scheduler_job', ['status', 'trigger_type'], unique=False)

    # 创建定时任务日志表
    op.create_table('core_scheduler_log',
    sa.Column('job_id', sa.String(length=36), nullable=False, comment='任务ID'),
    sa.Column('job_name', sa.String(length=128), nullable=False, comment='任务名称'),
    sa.Column('job_code', sa.String(length=128), nullable=False, comment='任务编码'),
    sa.Column('status', sa.String(length=20), nullable=True, comment='执行状态'),
    sa.Column('start_time', sa.DateTime(), nullable=False, comment='开始时间'),
    sa.Column('end_time', sa.DateTime(), nullable=True, comment='结束时间'),
    sa.Column('duration', sa.Float(), nullable=True, comment='执行耗时（秒）'),
    sa.Column('result', sa.Text(), nullable=True, comment='执行结果'),
    sa.Column('exception', sa.Text(), nullable=True, comment='异常信息'),
    sa.Column('traceback', sa.Text(), nullable=True, comment='异常堆栈'),
    sa.Column('hostname', sa.String(length=128), nullable=True, comment='执行主机'),
    sa.Column('process_id', sa.Integer(), nullable=True, comment='进程ID'),
    sa.Column('retry_count', sa.Integer(), nullable=True, comment='重试次数'),
    sa.Column('id', sa.String(length=21), nullable=False, comment='主键ID(NanoId)'),
    sa.Column('sort', sa.Integer(), nullable=True, comment='排序'),
    sa.Column('is_deleted', sa.Boolean(), nullable=True, comment='是否删除'),
    sa.Column('sys_create_datetime', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='创建时间'),
    sa.Column('sys_update_datetime', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='更新时间'),
    sa.Column('sys_creator_id', sa.String(length=21), nullable=True, comment='创建人ID（逻辑外键关联core_user）'),
    sa.Column('sys_modifier_id', sa.String(length=21), nullable=True, comment='修改人ID（逻辑外键关联core_user）'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_core_scheduler_log_is_deleted'), 'core_scheduler_log', ['is_deleted'], unique=False)
    op.create_index(op.f('ix_core_scheduler_log_job_code'), 'core_scheduler_log', ['job_code'], unique=False)
    op.create_index(op.f('ix_core_scheduler_log_job_id'), 'core_scheduler_log', ['job_id'], unique=False)
    op.create_index(op.f('ix_core_scheduler_log_job_name'), 'core_scheduler_log', ['job_name'], unique=False)
    op.create_index(op.f('ix_core_scheduler_log_start_time'), 'core_scheduler_log', ['start_time'], unique=False)
    op.create_index(op.f('ix_core_scheduler_log_status'), 'core_scheduler_log', ['status'], unique=False)
    op.create_index('ix_scheduler_log_code_start', 'core_scheduler_log', ['job_code', 'start_time'], unique=False)
    op.create_index('ix_scheduler_log_job_status', 'core_scheduler_log', ['job_id', 'status'], unique=False)
    op.create_index('ix_scheduler_log_status_start', 'core_scheduler_log', ['status', 'start_time'], unique=False)


def downgrade() -> None:
    # 删除定时任务日志表索引
    op.drop_index('ix_scheduler_log_status_start', table_name='core_scheduler_log')
    op.drop_index('ix_scheduler_log_job_status', table_name='core_scheduler_log')
    op.drop_index('ix_scheduler_log_code_start', table_name='core_scheduler_log')
    op.drop_index(op.f('ix_core_scheduler_log_status'), table_name='core_scheduler_log')
    op.drop_index(op.f('ix_core_scheduler_log_start_time'), table_name='core_scheduler_log')
    op.drop_index(op.f('ix_core_scheduler_log_job_name'), table_name='core_scheduler_log')
    op.drop_index(op.f('ix_core_scheduler_log_job_id'), table_name='core_scheduler_log')
    op.drop_index(op.f('ix_core_scheduler_log_job_code'), table_name='core_scheduler_log')
    op.drop_index(op.f('ix_core_scheduler_log_is_deleted'), table_name='core_scheduler_log')
    op.drop_table('core_scheduler_log')

    # 删除定时任务表索引
    op.drop_index('ix_scheduler_job_status_trigger', table_name='core_scheduler_job')
    op.drop_index('ix_scheduler_job_priority_status', table_name='core_scheduler_job')
    op.drop_index('ix_scheduler_job_next_run_status', table_name='core_scheduler_job')
    op.drop_index('ix_scheduler_job_group_status', table_name='core_scheduler_job')
    op.drop_index(op.f('ix_core_scheduler_job_trigger_type'), table_name='core_scheduler_job')
    op.drop_index(op.f('ix_core_scheduler_job_status'), table_name='core_scheduler_job')
    op.drop_index(op.f('ix_core_scheduler_job_priority'), table_name='core_scheduler_job')
    op.drop_index(op.f('ix_core_scheduler_job_name'), table_name='core_scheduler_job')
    op.drop_index(op.f('ix_core_scheduler_job_is_deleted'), table_name='core_scheduler_job')
    op.drop_index(op.f('ix_core_scheduler_job_group'), table_name='core_scheduler_job')
    op.drop_index(op.f('ix_core_scheduler_job_code'), table_name='core_scheduler_job')
    op.drop_table('core_scheduler_job')