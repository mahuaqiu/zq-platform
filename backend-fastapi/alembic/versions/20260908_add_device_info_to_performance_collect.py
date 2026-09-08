"""add device info to performance_collect

性能采集记录冗余设备信息（类型/IP/SN）与鸿蒙匹配模式，
历史记录与版本对比展示用，不受设备后续修改/删除影响。

Revision ID: b1c2d3e4f5a6
Revises: 20260807_target_device_sn
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b1c2d3e4f5a6"
down_revision = "20260807_target_device_sn"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "performance_collect",
        sa.Column("device_type", sa.String(30), nullable=True, comment="设备类型快照"),
    )
    op.add_column(
        "performance_collect",
        sa.Column("device_ip", sa.String(64), nullable=True, comment="设备IP快照"),
    )
    op.add_column(
        "performance_collect",
        sa.Column("device_sn", sa.String(64), nullable=True, comment="设备SN快照（鸿蒙为HDC UDID）"),
    )
    op.add_column(
        "performance_collect",
        sa.Column("match_mode", sa.String(10), nullable=True, comment="鸿蒙匹配模式：fuzzy/exact"),
    )


def downgrade():
    op.drop_column("performance_collect", "match_mode")
    op.drop_column("performance_collect", "device_sn")
    op.drop_column("performance_collect", "device_ip")
    op.drop_column("performance_collect", "device_type")
