"""add_script_fields_to_config_template

Revision ID: 0e253d677dee
Revises: 5d714220f329
Create Date: 2026-04-18 16:37:07.769088

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0e253d677dee'
down_revision: Union[str, None] = '5d714220f329'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 新增 type 字段，默认值为 'config'
    op.add_column('config_template',
        sa.Column('type', sa.String(20), nullable=False, server_default='config', comment='模板类型: config/script'))

    # 新增 script_name 字段
    op.add_column('config_template',
        sa.Column('script_name', sa.String(128), nullable=True, comment='脚本名称'))


def downgrade() -> None:
    op.drop_column('config_template', 'script_name')
    op.drop_column('config_template', 'type')
