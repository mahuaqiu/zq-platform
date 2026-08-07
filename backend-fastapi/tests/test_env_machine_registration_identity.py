"""Worker 注册物理身份与命名空间切换回归测试。"""

from contextlib import asynccontextmanager
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


@asynccontextmanager
async def _noop_lock(*args, **kwargs):
    """单测不依赖 Redis，直接通过锁上下文。"""
    yield "test-holder"


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
            "core.env_machine.api.EnvMachineService.get_by_device_identity",
            new=AsyncMock(return_value=[machine]),
        ),
        patch(
            "core.env_machine.api.EnvLockManager.env_registration_lock_or_raise",
            new=_noop_lock,
        ),
        patch(
            "core.env_machine.api.EnvLockManager.env_locks_or_raise",
            new=_noop_lock,
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


@pytest.mark.asyncio
async def test_changed_device_sn_reuses_unique_host_machine() -> None:
    """人工编辑过 SN 后，升级注册应更新原机器而非插入新记录。"""
    db = MagicMock()
    machine = _machine("machine-1", "meeting_app")
    machine.device_type = "android"
    machine.device_sn = "edited-sn"

    with (
        patch(
            "core.env_machine.api.EnvMachineService.get_by_device_identity",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "core.env_machine.api.EnvMachineService.get_by_host_device_type",
            new=AsyncMock(return_value=[machine]),
        ),
    ):
        result = await _get_registration_machine(
            db,
            ip="10.0.0.1",
            device_type="android",
            device_sn="worker-sn",
        )

    assert result is machine
    assert machine.device_sn == "worker-sn"


@pytest.mark.asyncio
async def test_changed_device_sn_does_not_merge_multiple_host_devices() -> None:
    """同宿主机有多台同类型设备时，SN 不一致不能猜测匹配关系。"""
    db = MagicMock()
    first = _machine("machine-1", "meeting_app")
    second = _machine("machine-2", "meeting_app")
    first.device_type = second.device_type = "android"

    with (
        patch(
            "core.env_machine.api.EnvMachineService.get_by_device_identity",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "core.env_machine.api.EnvMachineService.get_by_host_device_type",
            new=AsyncMock(return_value=[first, second]),
        ),
    ):
        result = await _get_registration_machine(
            db,
            ip="10.0.0.1",
            device_type="android",
            device_sn="worker-sn",
        )

    assert result is None


@pytest.mark.asyncio
async def test_missing_worker_device_sn_reuses_unique_edited_host_machine() -> None:
    """宿主机上报空 SN 时，也应复用唯一的人工编辑记录。"""
    db = MagicMock()
    machine = _machine("machine-1", "meeting_old")
    machine.device_sn = "manual-value"

    with (
        patch(
            "core.env_machine.api.EnvMachineService.get_by_device_identity",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "core.env_machine.api.EnvMachineService.get_by_host_device_type",
            new=AsyncMock(return_value=[machine]),
        ),
    ):
        result = await _get_registration_machine(
            db,
            ip="10.0.0.1",
            device_type="windows",
            device_sn=None,
        )

    assert result is machine
    assert machine.device_sn is None


@pytest.mark.asyncio
async def test_windows_null_registration_merges_empty_sn_history() -> None:
    """Windows 重注册会合并历史 device_sn=null 和 device_sn="" 记录。"""
    db = MagicMock()
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    primary = _machine("configured", "meeting_old", extra_message={"web": {}})
    duplicate = _machine("duplicate", "meeting_new")
    duplicate.device_sn = None
    primary.device_sn = ""

    with (
        patch(
            "core.env_machine.api.EnvMachineService.get_by_device_identity",
            new=AsyncMock(return_value=[primary, duplicate]),
        ),
        patch(
            "core.env_machine.api.EnvPoolManager.remove_machine_from_cache",
            new=AsyncMock(),
        ),
    ):
        result = await _get_registration_machine(
            db,
            ip="10.0.0.1",
            device_type="windows",
            device_sn=None,
        )

    assert result is primary
    assert primary.device_sn is None
    db.delete.assert_awaited_once_with(duplicate)
