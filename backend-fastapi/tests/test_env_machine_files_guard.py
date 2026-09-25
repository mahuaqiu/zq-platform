# tests/test_env_machine_files_guard.py
"""文件管理路由前置校验(_get_file_machine)测试。"""
import pytest
from fastapi import HTTPException

from core.env_machine import api as env_machine_api
from core.env_machine.model import EnvMachine
from core.env_machine.service import EnvMachineService


def _machine(**kw) -> EnvMachine:
    defaults = dict(ip="10.0.0.5", port=8080, status="online", device_type="windows")
    defaults.update(kw)
    return EnvMachine(**defaults)


def _patch_get_by_id(monkeypatch, machine):
    async def fake_get_by_id(db, record_id):
        return machine

    monkeypatch.setattr(EnvMachineService, "get_by_id", fake_get_by_id)


async def test_guard_ok(monkeypatch):
    _patch_get_by_id(monkeypatch, _machine())
    machine = await env_machine_api._get_file_machine("id1", db=None)
    assert machine.ip == "10.0.0.5"


async def test_guard_missing(monkeypatch):
    _patch_get_by_id(monkeypatch, None)
    with pytest.raises(HTTPException) as exc:
        await env_machine_api._get_file_machine("id1", db=None)
    assert exc.value.status_code == 404


async def test_guard_rejects_non_host_types(monkeypatch):
    _patch_get_by_id(monkeypatch, None)
    for t in ("android", "ios", "harmony_mobile", "linux", "harmony_pc"):
        _patch_get_by_id(monkeypatch, _machine(device_type=t))
        with pytest.raises(HTTPException) as exc:
            await env_machine_api._get_file_machine("id1", db=None)
        assert exc.value.status_code == 400, t


async def test_guard_rejects_offline(monkeypatch):
    _patch_get_by_id(monkeypatch, _machine(status="offline"))
    with pytest.raises(HTTPException) as exc:
        await env_machine_api._get_file_machine("id1", db=None)
    assert exc.value.status_code == 400


async def test_guard_rejects_missing_ip_or_port(monkeypatch):
    for kw in ({"ip": None}, {"port": None}):
        _patch_get_by_id(monkeypatch, _machine(**kw))
        with pytest.raises(HTTPException) as exc:
            await env_machine_api._get_file_machine("id1", db=None)
        assert exc.value.status_code == 400
