"""add compare_tag table

Revision ID: 4b93d2252d21
Revises: b801c64a4547
Create Date: 2026-05-17 01:46:55.486986

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4b93d2252d21'
down_revision: Union[str, None] = 'b801c64a4547'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('performance_compare_tag',
        sa.Column('name', sa.String(length=100), nullable=False, comment='标签名称'),
        sa.Column('type', sa.String(length=20), nullable=False, comment='类型: peak(冲高) / stable(稳态)'),
        sa.Column('start_time', sa.DateTime(), nullable=False, comment='开始时间（绝对时间，UTC）'),
        sa.Column('end_time', sa.DateTime(), nullable=False, comment='结束时间（绝对时间，UTC）'),
        sa.Column('note', sa.Text(), nullable=True, comment='备注'),
        sa.Column('id', sa.String(length=50), nullable=False, comment='主键ID(NanoId)'),
        sa.Column('sort', sa.Integer(), nullable=True, comment='排序'),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, comment='是否删除'),
        sa.Column('sys_create_datetime', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='创建时间'),
        sa.Column('sys_update_datetime', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='更新时间'),
        sa.Column('sys_creator_id', sa.String(length=50), nullable=True, comment='创建人ID'),
        sa.Column('sys_modifier_id', sa.String(length=50), nullable=True, comment='修改人ID'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_performance_compare_tag_is_deleted'), 'performance_compare_tag', ['is_deleted'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_performance_compare_tag_is_deleted'), table_name='performance_compare_tag')
    op.drop_table('performance_compare_tag')
