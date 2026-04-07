"""test report optimization: add upload log, rename fields, add execute_total

Revision ID: 96da0848eb60
Revises: d8f91258f2b0
Create Date: 2026-04-08 00:34:58.756309

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '96da0848eb60'
down_revision: Union[str, None] = 'd8f91258f2b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 创建 test_report_upload_log 表
    op.create_table('test_report_upload_log',
    sa.Column('task_project_id', sa.String(length=21), nullable=False, comment='任务项目ID'),
    sa.Column('round', sa.Integer(), nullable=False, comment='执行轮次'),
    sa.Column('testcase_block_id', sa.String(length=50), nullable=False, comment='用例块ID'),
    sa.Column('file_name', sa.String(length=100), nullable=False, comment='文件名'),
    sa.Column('file_url', sa.String(length=500), nullable=False, comment='文件访问URL'),
    sa.Column('upload_time', sa.DateTime(), server_default=sa.text('now()'), nullable=False, comment='上传时间'),
    sa.Column('id', sa.String(length=21), nullable=False, comment='主键ID(NanoId)'),
    sa.Column('sort', sa.Integer(), nullable=True, comment='排序'),
    sa.Column('is_deleted', sa.Boolean(), nullable=True, comment='是否删除'),
    sa.Column('sys_create_datetime', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='创建时间'),
    sa.Column('sys_update_datetime', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='更新时间'),
    sa.Column('sys_creator_id', sa.String(length=21), nullable=True, comment='创建人ID（逻辑外键关联core_user）'),
    sa.Column('sys_modifier_id', sa.String(length=21), nullable=True, comment='修改人ID（逻辑外键关联core_user）'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_task_round_block', 'test_report_upload_log', ['task_project_id', 'round', 'testcase_block_id'], unique=True)
    op.create_index(op.f('ix_test_report_upload_log_is_deleted'), 'test_report_upload_log', ['is_deleted'], unique=False)
    op.create_index(op.f('ix_test_report_upload_log_task_project_id'), 'test_report_upload_log', ['task_project_id'], unique=False)

    # 2. 处理 test_report_detail 表的字段迁移
    # 2.1 添加新列（先允许为空，便于数据迁移）
    op.add_column('test_report_detail', sa.Column('task_project_id', sa.String(length=21), nullable=True, comment='任务项目ID'))
    op.add_column('test_report_detail', sa.Column('round', sa.Integer(), nullable=True, comment='执行轮次'))
    op.add_column('test_report_detail', sa.Column('testcase_block_id', sa.String(length=50), nullable=True, comment='用例块ID'))

    # 2.2 数据迁移：复制旧数据到新列
    op.execute(text("""
        UPDATE test_report_detail
        SET task_project_id = task_id,
            round = case_round
    """))

    # 2.3 删除旧索引
    op.drop_index('ix_test_report_detail_task_id', table_name='test_report_detail')
    op.drop_index('idx_task_case_round', table_name='test_report_detail')

    # 2.4 删除旧列
    op.drop_column('test_report_detail', 'total_cases')
    op.drop_column('test_report_detail', 'task_id')
    op.drop_column('test_report_detail', 'case_round')

    # 2.5 设置新列为 NOT NULL
    op.alter_column('test_report_detail', 'task_project_id', nullable=False)
    op.alter_column('test_report_detail', 'round', nullable=False)

    # 2.6 创建新索引
    op.create_index('idx_task_case_round', 'test_report_detail', ['task_project_id', 'case_name', 'round'], unique=False)
    op.create_index(op.f('ix_test_report_detail_task_project_id'), 'test_report_detail', ['task_project_id'], unique=False)

    # 3. 处理 test_report_summary 表的字段迁移
    # 3.1 添加新列
    op.add_column('test_report_summary', sa.Column('task_project_id', sa.String(length=21), nullable=True, comment='任务项目ID'))
    op.add_column('test_report_summary', sa.Column('execute_total', sa.Integer(), nullable=True, default=0, comment='执行总数'))
    op.add_column('test_report_summary', sa.Column('task_project_ids', sa.JSON(), nullable=True, comment='子任务ID列表，仅聚合任务有值'))

    # 3.2 数据迁移：复制旧数据到新列
    op.execute(text("""
        UPDATE test_report_summary
        SET task_project_id = task_id,
            execute_total = 0
    """))

    # 3.3 修改 total_cases 注释
    op.alter_column('test_report_summary', 'total_cases',
               existing_type=sa.INTEGER(),
               comment='用例总数（从UploadLog统计）',
               existing_comment='用例总数',
               existing_nullable=False)

    # 3.4 删除旧约束和索引
    op.drop_index('idx_last_report_time', table_name='test_report_summary')
    op.drop_index('idx_task_base_name', table_name='test_report_summary')
    op.drop_constraint('test_report_summary_task_id_key', 'test_report_summary', type_='unique')

    # 3.5 删除旧列
    op.drop_column('test_report_summary', 'task_id')

    # 3.6 设置新列为 NOT NULL
    op.alter_column('test_report_summary', 'task_project_id', nullable=False)
    op.alter_column('test_report_summary', 'execute_total', nullable=False)

    # 3.7 创建新约束
    op.create_unique_constraint('test_report_summary_task_project_id_key', 'test_report_summary', ['task_project_id'])

    # 4. 为历史 Detail 添加默认 testcase_block_id
    op.execute(text("""
        UPDATE test_report_detail
        SET testcase_block_id = CONCAT('legacy_', id)
        WHERE testcase_block_id IS NULL
    """))


def downgrade() -> None:
    # 反向迁移：恢复 test_report_summary 表
    op.add_column('test_report_summary', sa.Column('task_id', sa.VARCHAR(length=21), autoincrement=False, nullable=True, comment='任务执行ID'))

    # 复制数据回旧列
    op.execute(text("""
        UPDATE test_report_summary
        SET task_id = task_project_id
    """))

    op.drop_constraint('test_report_summary_task_project_id_key', 'test_report_summary', type_='unique')
    op.create_unique_constraint('test_report_summary_task_id_key', 'test_report_summary', ['task_id'])
    op.create_index('idx_task_base_name', 'test_report_summary', ['task_base_name'], unique=False)
    op.create_index('idx_last_report_time', 'test_report_summary', ['last_report_time'], unique=False)
    op.alter_column('test_report_summary', 'total_cases',
               existing_type=sa.INTEGER(),
               comment='用例总数',
               existing_comment='用例总数（从UploadLog统计）',
               existing_nullable=False)
    op.alter_column('test_report_summary', 'task_id', nullable=False)
    op.drop_column('test_report_summary', 'task_project_ids')
    op.drop_column('test_report_summary', 'execute_total')
    op.drop_column('test_report_summary', 'task_project_id')

    # 反向迁移：恢复 test_report_detail 表
    op.add_column('test_report_detail', sa.Column('case_round', sa.INTEGER(), autoincrement=False, nullable=True, comment='失败轮次'))
    op.add_column('test_report_detail', sa.Column('task_id', sa.VARCHAR(length=21), autoincrement=False, nullable=True, comment='任务执行ID'))
    op.add_column('test_report_detail', sa.Column('total_cases', sa.INTEGER(), autoincrement=False, nullable=False, comment='用例总数', server_default='0'))

    # 复制数据回旧列
    op.execute(text("""
        UPDATE test_report_detail
        SET task_id = task_project_id,
            case_round = round
    """))

    op.drop_index(op.f('ix_test_report_detail_task_project_id'), table_name='test_report_detail')
    op.drop_index('idx_task_case_round', table_name='test_report_detail')
    op.create_index('idx_task_case_round', 'test_report_detail', ['task_id', 'case_name', 'case_round'], unique=False)
    op.create_index('ix_test_report_detail_task_id', 'test_report_detail', ['task_id'], unique=False)
    op.alter_column('test_report_detail', 'task_id', nullable=False)
    op.alter_column('test_report_detail', 'case_round', nullable=False)
    op.drop_column('test_report_detail', 'testcase_block_id')
    op.drop_column('test_report_detail', 'round')
    op.drop_column('test_report_detail', 'task_project_id')

    # 删除 test_report_upload_log 表
    op.drop_index(op.f('ix_test_report_upload_log_task_project_id'), table_name='test_report_upload_log')
    op.drop_index(op.f('ix_test_report_upload_log_is_deleted'), table_name='test_report_upload_log')
    op.drop_index('idx_task_round_block', table_name='test_report_upload_log')
    op.drop_table('test_report_upload_log')
