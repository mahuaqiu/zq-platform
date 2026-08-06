"""Worker 注册物理身份与命名空间切换回归测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.env_machine.api import _get_registration_machine, register_env_machine
from core.env_machine.schema import EnvRegisterRequest


def _machine(machine_id: str, namespace: str, extra_message=None):
    machine = MagicMock()
    machine.id = machine_id
    machine.namespace = namespace
    machine.ip = "10.0.0.1"
    machine.port = "8088"
    machine.device_type = "windows"
    machine.device_sn = None
    machine.extra_message = extra_message
    machine.mark = ""
    machine.note = ""
    machine.asset_number = ""
    machine.available = True
    machine.status = "online"
    machine.version = "1.0.0"
    machine.config_version = None
    machine.scripts = None
    return machine


@pytest.mark.asyncio
async def test_namespace_switch_updates_existing_machine() -> None:
    """同一物理机切换命名空间时更新原记录，不新增机器。"""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    machine = _machine(
        "machine-1",
        "meeting_old",
        extra_message={"account-a": {"username": "tester"}},
    )
    request = EnvRegisterRequest(
        ip="10.0.0.1",
        port="9090",
        namespace="meeting_new",
        devices={"windows": []},
    )

    with (
        patch(
            "core.env_machine.api._get_registration_machine",
            new=AsyncMock(return_value=machine),
        ),
        patch(
            "core.env_machine.api.EnvMachineService.get_by_namespace",
            new=AsyncMock(return_value=([machine], 1)),
        ),
        patch(
            "core.env_machine.api.EnvPoolManager.remove_machine_from_cache",
            new=AsyncMock(),
        ) as remove_cache,
        patch(
            "core.env_machine.api.EnvPoolManager.sync_machine_to_cache",
            new=AsyncMock(),
        ),
    ):
        response = await register_env_machine(request, db)

    assert response.status == "success"
    assert machine.namespace == "meeting_new"
    assert machine.port == "9090"
    assert machine.extra_message == {"account-a": {"username": "tester"}}
    db.add.assert_not_called()
    remove_cache.assert_awaited_once_with("machine-1", "meeting_old")


@pytest.mark.asyncio
async def test_duplicate_registration_records_are_merged() -> None:
    """历史重复记录会合并配置并删除多余记录。"""
    db = MagicMock()
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    primary = _machine("configured", "meeting_old", extra_message={"tag": {}})
    duplicate = _machine("duplicate", "meeting_new")
    duplicate.mark = "tag"

    with (
        patch(
            "core.env_machine.api.EnvMachineService.get_by_device_identity",
            new=AsyncMock(return_value=[primary, duplicate]),
        ),
        patch(
            "core.env_machine.api.EnvPoolManager.remove_machine_from_cache",
            new=AsyncMock(),
        ) as remove_cache,
    ):
        result = await _get_registration_machine(
            db,
            ip="10.0.0.1",
            device_type="windows",
            device_sn=None,
        )

    assert result is primary
    assert primary.extra_message == {"tag": {}}
    assert primary.mark == "tag"
    db.delete.assert_awaited_once_with(duplicate)
    db.flush.assert_awaited_once()
    remove_cache.assert_awaited_once_with("duplicate", "meeting_new")
