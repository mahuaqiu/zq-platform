"""keepusing 最长连续使用时长限制单测。"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from fastapi import Request

from core.env_machine.api import keepusing_env_machines
from core.env_machine.model import EnvMachine
from core.env_machine.schema import EnvMachineIdItem


def _fake_request(forwarded_ip: str = "10.1.1.100") -> Request:
    """构造带 X-Forwarded-For 的最小 Request 对象。"""
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/keepusing",
        "headers": [(b"x-forwarded-for", forwarded_ip.encode())],
        "query_string": b"",
        "client": ("172.17.0.1", 50000),
    }
    return Request(scope)


def _machine(machine_id: str = "m1", status: str = "using") -> EnvMachine:
    return EnvMachine(
        id=machine_id,
        namespace="meeting_gamma",
        ip="10.0.0.10",
        port="8088",
        device_type="windows",
        status=status,
    )


def _patch_env(monkeypatch, machines_by_id, apply_log_by_id):
    """替换 get_by_id 与 get_latest_apply_log 为内存字典实现。"""
    async def fake_get_by_id(db, machine_id):
        return machines_by_id.get(machine_id)

    async def fake_latest_apply_log(db, machine_id):
        return apply_log_by_id.get(machine_id)

    monkeypatch.setattr(
        "core.env_machine.api.EnvMachineService.get_by_id", fake_get_by_id
    )
    monkeypatch.setattr(
        "core.env_machine.api.EnvMachineLogService.get_latest_apply_log",
        fake_latest_apply_log,
    )


def _items(*ids: str):
    return [EnvMachineIdItem(id=i) for i in ids]


async def test_keepusing_rejected_after_max_hours(monkeypatch):
    """超过最长使用时长的设备，keepusing 被拒绝且不更新任何机器。"""
    now = datetime.now()
    machine = _machine()
    _patch_env(
        monkeypatch,
        {"m1": machine},
        {"m1": type("Log", (), {"apply_time": now - timedelta(hours=4)})()},
    )
    db = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    response = await keepusing_env_machines(
        _fake_request(), _items("m1"), db
    )

    assert response.status == "fail"
    assert "超过3.0小时" in response.result
    assert "10.0.0.10" in response.result
    # 被拒绝时不能续期，否则超时释放任务永远收不回设备
    assert machine.last_keepusing_time is None
    db.rollback.assert_awaited()
    db.commit.assert_not_awaited()


async def test_keepusing_allowed_within_max_hours(monkeypatch):
    """未超过最长使用时长的设备正常保持。"""
    now = datetime.now()
    machine = _machine()
    _patch_env(
        monkeypatch,
        {"m1": machine},
        {"m1": type("Log", (), {"apply_time": now - timedelta(hours=1)})()},
    )
    db = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    response = await keepusing_env_machines(
        _fake_request(), _items("m1"), db
    )

    assert response.status == "success"
    assert machine.last_keepusing_time is not None
    db.commit.assert_awaited()


async def test_keepusing_without_apply_log_not_limited(monkeypatch):
    """没有申请记录的机器（如手工占用）不做时长限制。"""
    machine = _machine()
    _patch_env(monkeypatch, {"m1": machine}, {"m1": None})
    db = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    response = await keepusing_env_machines(
        _fake_request(), _items("m1"), db
    )

    assert response.status == "success"
    assert machine.last_keepusing_time is not None


async def test_keepusing_rejection_is_all_or_nothing(monkeypatch):
    """请求中任一设备超时，整个请求被拒绝，其余设备也不续期。"""
    now = datetime.now()
    fresh = _machine("m1")
    stale = _machine("m2")
    _patch_env(
        monkeypatch,
        {"m1": fresh, "m2": stale},
        {
            "m1": type("Log", (), {"apply_time": now - timedelta(minutes=10)})(),
            "m2": type("Log", (), {"apply_time": now - timedelta(hours=5)})(),
        },
    )
    db = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    response = await keepusing_env_machines(
        _fake_request(), _items("m1", "m2"), db
    )

    assert response.status == "fail"
    assert "m2" in response.result or "10.0.0.10" in response.result
    assert fresh.last_keepusing_time is None
    assert stale.last_keepusing_time is None
