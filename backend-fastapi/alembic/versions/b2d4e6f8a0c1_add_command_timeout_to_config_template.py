"""add command_timeout to config_template and command_task

Revision ID: b2d4e6f8a0c1
Revises: e7a3c9d1f5b2
Create Date: 2026-09-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2d4e6f8a0c1'
down_revision: Union[str, None] = 'e7a3c9d1f5b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 命令超时时间(秒)，存量模板回填默认 120
    op.add_column(
        'config_template',
        sa.Column(
            'command_timeout',
            sa.Integer(),
            nullable=False,
            server_default='120',
            comment='命令超时时间(秒)',
        ),
    )
    # 命令任务历史记录使用的超时，便于排查长任务
    op.add_column(
        'command_task',
        sa.Column(
            'command_timeout',
            sa.Integer(),
            nullable=False,
            server_default='120',
            comment='命令超时时间(秒)',
        ),
    )


def downgrade() -> None:
    op.drop_column('command_task', 'command_timeout')
    op.drop_column('config_template', 'command_timeout')
