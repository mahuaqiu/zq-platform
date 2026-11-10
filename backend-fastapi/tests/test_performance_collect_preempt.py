"""性能采集 start 抢占语义回归测试（MagicMock db，不依赖真实数据库）。

场景：上一用例的采集未结束（running/stopping）时再发起 start，
旧记录应标记 interrupted 让位，而不是抛 ValueError 导致接口 409。
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.performance_monitor.schema import CollectStartRequest
from core.performance_monitor.service import PerformanceCollectService


def _db_with_active_collects(collects):
    """构造 db.execute 侧返回：第一次查询（reconcile）无结果，第二次返回旧任务。"""
    db = MagicMock()
    db.commit = AsyncMock()
    # 模拟数据库为新增记录生成主键
    db.refresh = AsyncMock(side_effect=lambda collect: setattr(collect, "id", "new-collect"))
    db.add = MagicMock()
    empty = MagicMock()
    empty.scalars.return_value.all.return_value = []
    active = MagicMock()
    active.scalars.return_value.all.return_value = collects
    db.execute = AsyncMock(side_effect=[empty, active])
    return db


@pytest.mark.asyncio
async def test_start_collect_marks_active_collect_interrupted():
    """设备上仍有 running 旧任务时，start 不再 409，旧任务标记 interrupted。"""
    old = MagicMock()
    old.status = "running"
    old.failure_code = None
    old.failure_message = None
    db = _db_with_active_collects([old])

    request = CollectStartRequest(device_id="dev-1", interval=5)
    collect_id = await PerformanceCollectService.start_collect(db, request, device=MagicMock())

    assert collect_id == "new-collect"
    assert old.status == "interrupted"
    assert old.end_reason == "superseded_by_new_collect"
    assert old.failure_code == "SUPERSEDED"
    db.add.assert_called_once()
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_start_collect_marks_stopping_collect_interrupted():
    """stopping 状态同样让位标记 interrupted（沿用原有语义）。"""
    old = MagicMock()
    old.status = "stopping"
    old.failure_code = None
    old.failure_message = None
    db = _db_with_active_collects([old])

    request = CollectStartRequest(device_id="dev-1", interval=5)
    await PerformanceCollectService.start_collect(db, request, device=MagicMock())

    assert old.status == "interrupted"
    assert old.end_reason == "superseded_by_new_collect"


@pytest.mark.asyncio
async def test_start_collect_without_active_creates_record_directly():
    """无活跃旧任务时直接创建新记录，不触发标记。"""
    db = _db_with_active_collects([])

    request = CollectStartRequest(device_id="dev-1", interval=5)
    collect_id = await PerformanceCollectService.start_collect(db, request, device=MagicMock())

    assert collect_id == "new-collect"
    db.add.assert_called_once()
