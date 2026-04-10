"""add upgrade tables

Revision ID: 15eaeb5cfdfb
Revises: remove_post_module
Create Date: 2026-04-10 22:55:08.437443

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '15eaeb5cfdfb'
down_revision: Union[str, None] = 'remove_post_module'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 worker_upgrade_config 表
    op.create_table(
        'worker_upgrade_config',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('device_type', sa.String(20), nullable=False, unique=True),
        sa.Column('version', sa.String(32), nullable=False),
        sa.Column('download_url', sa.String(512), nullable=False),
        sa.Column('note', sa.Text, nullable=True),
        sa.Column('sort', sa.Integer, default=0),
        sa.Column('is_deleted', sa.Boolean, default=False),
        sa.Column('sys_create_datetime', sa.DateTime),
        sa.Column('sys_update_datetime', sa.DateTime),
        sa.Column('sys_creator_id', sa.String(36)),
        sa.Column('sys_modifier_id', sa.String(36)),
    )

    # 创建 worker_upgrade_queue 表
    op.create_table(
        'worker_upgrade_queue',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('machine_id', sa.String(36), nullable=False),
        sa.Column('target_version', sa.String(32), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='waiting'),
        sa.Column('device_type', sa.String(20), nullable=False),
        sa.Column('namespace', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('sort', sa.Integer, default=0),
        sa.Column('is_deleted', sa.Boolean, default=False),
        sa.Column('sys_create_datetime', sa.DateTime),
        sa.Column('sys_update_datetime', sa.DateTime),
        sa.Column('sys_creator_id', sa.String(36)),
        sa.Column('sys_modifier_id', sa.String(36)),
    )
    op.create_index('ix_upgrade_queue_status', 'worker_upgrade_queue', ['status'])
    op.create_index('ix_upgrade_queue_machine_id', 'worker_upgrade_queue', ['machine_id'])

    # 初始化配置数据（Windows 和 Mac 两条默认记录）
    op.execute("""
        INSERT INTO worker_upgrade_config (id, device_type, version, download_url, sort, is_deleted)
        VALUES ('windows-config-001', 'windows', '20260410150000', '', 0, False)
    """)
    op.execute("""
        INSERT INTO worker_upgrade_config (id, device_type, version, download_url, sort, is_deleted)
        VALUES ('mac-config-001', 'mac', '20260410150000', '', 0, False)
    """)


def downgrade() -> None:
    op.drop_table('worker_upgrade_queue')
    op.drop_table('worker_upgrade_config')