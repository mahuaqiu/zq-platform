"""补齐 Windows 性能采集状态、样本序号和可靠上报字段。"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f9b0c1d2e3f4"
down_revision: Union[str, None] = "f8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("performance_collect", sa.Column("last_heartbeat_at", sa.DateTime(), nullable=True, comment="Worker 最后心跳时间"))
    op.add_column("performance_collect", sa.Column("last_sequence", sa.Integer(), nullable=True, comment="Worker 最后采样序号"))
    op.add_column("performance_collect", sa.Column("last_elapsed_ms", sa.Integer(), nullable=True, comment="Worker 最后样本相对时间（毫秒）"))
    op.add_column("performance_collect", sa.Column("failure_code", sa.String(80), nullable=True, comment="失败错误码"))
    op.add_column("performance_collect", sa.Column("failure_message", sa.String(500), nullable=True, comment="失败消息"))
    op.add_column("performance_collect", sa.Column("end_reason", sa.String(40), nullable=True, comment="结束原因"))


    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, collect_id, relative_time FROM performance_data ORDER BY collect_id, relative_time, id")).mappings().all()
    counters: dict[str, int] = {}
    for row in rows:
        sequence = counters.get(row["collect_id"], 0)
        counters[row["collect_id"]] = sequence + 1
        bind.execute(
            sa.text("UPDATE performance_data SET sequence=:sequence, elapsed_ms=:elapsed_ms, sample_key=:sample_key WHERE id=:id"),
            {
                "id": row["id"],
                "sequence": sequence,
                "elapsed_ms": int(row["relative_time"] or 0) * 1000,
                "sample_key": f"{row['collect_id']}:{sequence}",
            },
        )

    op.alter_column("performance_data", "sample_key", nullable=False)
    op.alter_column("performance_data", "sequence", nullable=False)
    op.alter_column("performance_data", "elapsed_ms", nullable=False)
    op.create_index("uq_performance_data_collect_sequence", "performance_data", ["collect_id", "sequence"], unique=True)
    op.create_index("ix_performance_data_collect_elapsed_ms", "performance_data", ["collect_id", "elapsed_ms"])


def downgrade() -> None:
    op.drop_index("ix_performance_data_collect_elapsed_ms", table_name="performance_data")
    op.drop_index("uq_performance_data_collect_sequence", table_name="performance_data")
    op.drop_column("performance_collect", "end_reason")
    op.drop_column("performance_collect", "failure_message")
    op.drop_column("performance_collect", "failure_code")
    op.drop_column("performance_collect", "last_elapsed_ms")
    op.drop_column("performance_collect", "last_sequence")
    op.drop_column("performance_collect", "last_heartbeat_at")
