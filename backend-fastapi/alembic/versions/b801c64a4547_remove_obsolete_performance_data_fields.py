"""remove obsolete performance data fields

Revision ID: b801c64a4547
Revises: 2cff20a46669
Create Date: 2026-05-16 19:20:24.194527

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b801c64a4547'
down_revision: Union[str, None] = '2cff20a46669'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 删除过期的系统指标字段
    op.drop_column('performance_data', 'download_speed')
    op.drop_column('performance_data', 'power')
    op.drop_column('performance_data', 'cpu_speed')
    op.drop_column('performance_data', 'cpu_temp')
    op.drop_column('performance_data', 'upload_speed')


def downgrade() -> None:
    # 恢复过期的系统指标字段（如需回滚）
    op.add_column('performance_data', sa.Column('upload_speed', sa.Float, nullable=True, comment='上传速度 MB/s'))
    op.add_column('performance_data', sa.Column('cpu_temp', sa.Float, nullable=True, comment='CPU温度 °C'))
    op.add_column('performance_data', sa.Column('cpu_speed', sa.Float, nullable=True, comment='CPU速度 GHz'))
    op.add_column('performance_data', sa.Column('power', sa.Float, nullable=True, comment='功耗 W'))
    op.add_column('performance_data', sa.Column('download_speed', sa.Float, nullable=True, comment='下载速度 MB/s'))