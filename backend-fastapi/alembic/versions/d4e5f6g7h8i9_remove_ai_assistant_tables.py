"""remove ai_assistant tables

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-05-10

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6g7h8i9'
down_revision: Union[str, None] = 'c3d4e5f6g7h8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 删除AI助手相关菜单数据
    op.execute("""
        DELETE FROM core_menu WHERE id LIKE 'ai-assistant%';
    """)

    # 2. 删除AI助手相关表
    # 注意：删除顺序很重要，先删除关联表和外键约束的表

    op.drop_table('ai_assistant_message')
    op.drop_table('ai_assistant_session')
    op.drop_table('ai_group_role')
    op.drop_table('ai_assistant_group')
    op.drop_table('ai_assistant_role')


def downgrade() -> None:
    # AI助手模块已完全移除，不支持回退恢复
    pass