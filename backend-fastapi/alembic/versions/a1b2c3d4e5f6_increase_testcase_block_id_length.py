"""increase testcase_block_id length to 200

Revision ID: a1b2c3d4e5f6
Revises: cb76b93485bf
Create Date: 2026-04-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'cb76b93485bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 修改 test_report_detail 表的 testcase_block_id 字段长度
    op.alter_column('test_report_detail', 'testcase_block_id',
               existing_type=sa.VARCHAR(length=50),
               type_=sa.VARCHAR(length=200),
               existing_nullable=False,
               existing_comment='用例块ID')

    # 修改 test_report_upload_log 表的 testcase_block_id 字段长度
    # 先删除索引
    op.drop_index('idx_task_round_block', table_name='test_report_upload_log')

    op.alter_column('test_report_upload_log', 'testcase_block_id',
               existing_type=sa.VARCHAR(length=50),
               type_=sa.VARCHAR(length=200),
               existing_nullable=False,
               existing_comment='用例块ID')

    # 重新创建索引
    op.create_index('idx_task_round_block', 'test_report_upload_log', ['task_project_id', 'round', 'testcase_block_id'], unique=True)


def downgrade() -> None:
    # 回滚 test_report_upload_log 表
    op.drop_index('idx_task_round_block', table_name='test_report_upload_log')

    op.alter_column('test_report_upload_log', 'testcase_block_id',
               existing_type=sa.VARCHAR(length=200),
               type_=sa.VARCHAR(length=50),
               existing_nullable=False,
               existing_comment='用例块ID')

    op.create_index('idx_task_round_block', 'test_report_upload_log', ['task_project_id', 'round', 'testcase_block_id'], unique=True)

    # 回滚 test_report_detail 表
    op.alter_column('test_report_detail', 'testcase_block_id',
               existing_type=sa.VARCHAR(length=200),
               type_=sa.VARCHAR(length=50),
               existing_nullable=False,
               existing_comment='用例块ID')