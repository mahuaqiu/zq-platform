"""机器状态唯一写入口回归测试。"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.env_machine.state_service import (
    MachineStateService,
    TransitionResult,
    validate_transition,
)


def _machine(status="online"):
    m = MagicMock()
    m.id = "m-1"
    m.status = status
    m.available = True
    m.namespace = "meeting"
    return m


@pytest.fixture
def sync_spy(monkeypatch):
    spy = AsyncMock()
    monkeypatch.setattr(
        "core.env_machine.state_service.EnvPoolManager.sync_machine_to_cache", spy
    )
    return spy


def test_validate_transition_table():
    assert validate_transition("online", "using")
    assert validate_transition("using", "upgrading")   # 释放后延迟升级
    assert validate_transition("using", "online")      # 释放/超时释放
    assert validate_transition("upgrading", "offline")
    assert validate_transition("offline", "online")    # 心跳恢复
    assert not validate_transition("upgrading", "using")
    assert not validate_transition("unknown", "online")


def test_same_state_is_idempotent():
    assert validate_transition("online", "online")
    assert validate_transition("offline", "offline")


@pytest.mark.asyncio
async def test_transition_success_writes_and_syncs(sync_spy):
    db = MagicMock()
    machine = _machine("online")
    result = await MachineStateService.transition(db, machine, "using", source="allocate")
    assert isinstance(result, TransitionResult) and result.ok
    assert machine.status == "using"
    sync_spy.assert_awaited_once_with(machine)


@pytest.mark.asyncio
async def test_transition_same_state_still_syncs(sync_spy):
    db = MagicMock()
    machine = _machine("offline")
    result = await MachineStateService.transition(db, machine, "offline", source="reload")
    assert result.ok
    assert machine.status == "offline"
    sync_spy.assert_awaited_once_with(machine)


@pytest.mark.asyncio
async def test_transition_rejected_does_not_write(sync_spy):
    db = MagicMock()
    machine = _machine("upgrading")
    result = await MachineStateService.transition(db, machine, "using", source="test")
    assert result.ok is False
    assert machine.status == "upgrading"
    sync_spy.assert_not_awaited()
