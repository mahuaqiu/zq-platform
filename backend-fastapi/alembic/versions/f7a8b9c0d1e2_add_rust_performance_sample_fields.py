"""add Rust performance sample fields

Revision ID: f7a8b9c0d1e2
Revises: e5f6g7h8i9j0
Create Date: 2026-07-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e5f6g7h8i9j0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("performance_data", sa.Column("sample_key", sa.String(128), nullable=True, comment="采样幂等键"))
    op.add_column("performance_data", sa.Column("sequence", sa.Integer(), nullable=True, comment="采样序号"))
    op.add_column("performance_data", sa.Column("elapsed_ms", sa.Integer(), nullable=True, comment="相对采集开始时间，毫秒"))
    op.add_column("performance_data", sa.Column("system_metrics", sa.JSON(), nullable=True, comment="Rust 系统 CPU/GPU 指标"))
    op.create_index("ix_performance_data_sample_key", "performance_data", ["sample_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_performance_data_sample_key", table_name="performance_data")
    op.drop_column("performance_data", "system_metrics")
    op.drop_column("performance_data", "elapsed_ms")
    op.drop_column("performance_data", "sequence")
    op.drop_column("performance_data", "sample_key")