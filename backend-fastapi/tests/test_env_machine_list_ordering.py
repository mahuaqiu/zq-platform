"""设备列表排序确定性回归测试。

历史缺陷：BaseService.get_list 仅按 (sort DESC, sys_create_datetime DESC) 排序，
两个键都不唯一。所有设备 sort 默认为 0；同一事务创建的设备（批量导入、worker
一次注册多台设备）sys_create_datetime 完全相同（now() 取事务开始时间）。排序键
完全并列时，PostgreSQL 返回顺序取决于物理行位置，任何一次 UPDATE（如保存
extra_message JSON）都会移动行版本，导致列表顺序漂移。

修复要求：
1. BaseService.get_list 的 ORDER BY 必须以唯一主键 id 兜底，构成全序；
2. 设备列表（get_list_with_filters）在时间戳并列时按
   (ip, device_type, device_sn, id) 的自然业务顺序排列。
"""

from unittest.mock import MagicMock

from sqlalchemy.dialects import postgresql

from core.env_machine.service import EnvMachineService


class _CaptureDb:
    """捕获执行的 SQL 语句并返回空结果的假会话。"""

    def __init__(self):
        self.statements = []

    async def execute(self, stmt, *args, **kwargs):
        self.statements.append(stmt)
        result = MagicMock()
        result.scalar.return_value = 0
        result.scalars.return_value.all.return_value = []
        return result


def _order_by_segment(stmt) -> str:
    """编译语句并返回 ORDER BY 之后的片段（归一化空白）。"""
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    upper = sql.upper()
    idx = upper.rindex("ORDER BY")
    segment = sql[idx + len("ORDER BY"):]
    # 去掉可能拼接在后面的 LIMIT/OFFSET
    for stop in ("LIMIT", "OFFSET"):
        stop_idx = segment.upper().find(stop)
        if stop_idx != -1:
            segment = segment[:stop_idx]
    return " ".join(segment.split())


def _order_keys(stmt) -> list[str]:
    """按顺序返回 ORDER BY 的规范化键列表（含方向）。"""
    return [key.strip().lower() for key in _order_by_segment(stmt).split(",")]


async def test_base_get_list_order_by_ends_with_unique_id() -> None:
    """get_list 的 ORDER BY 必须以唯一主键 id 兜底，否则排序键并列时顺序不稳定。"""
    db = _CaptureDb()

    await EnvMachineService.get_list(db, page=1, page_size=20)

    assert len(db.statements) == 2  # 第一次 count，第二次数据查询
    data_stmt = db.statements[-1]
    keys = _order_keys(data_stmt)
    assert keys, "数据查询缺少 ORDER BY"
    assert keys[-1] == "env_machine.id", (
        f"ORDER BY 末尾必须是唯一主键 env_machine.id 兜底，实际为: {keys}"
    )


async def test_get_list_with_filters_orders_tied_devices_by_business_identity() -> None:
    """设备列表在 sort 与创建时间并列时，按 ip/device_type/device_sn 的自然顺序排列。"""
    db = _CaptureDb()

    await EnvMachineService.get_list_with_filters(db, namespace=None, page=1, page_size=20)

    data_stmt = db.statements[-1]
    keys = _order_keys(data_stmt)
    assert keys[-4:] == [
        "env_machine.ip",
        "env_machine.device_type",
        "env_machine.device_sn",
        "env_machine.id",
    ], (
        "时间戳并列的设备应按 (ip, device_type, device_sn, id) 自然排序，实际为: {keys}"
    )
    # 自定义 sort 与创建时间的优先级保持不变
    assert keys[:2] == [
        "env_machine.sort desc",
        "env_machine.sys_create_datetime desc",
    ]
