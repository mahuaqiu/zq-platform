"""命令超时设置回归测试。

覆盖：
- DeployRequest/模板 schema 的 command_timeout 字段与边界
- execute_single_command 把超时下发为动作级 timeout + 任务级 config.timeout
- wait_task_result 按任务预算自适应拉长轮询间隔（20 分钟 → 60 秒）
"""

import pytest
import pytest_asyncio  # noqa: F401

import core.config_template.worker_client as worker_client_module
from core.config_template.schema import ConfigTemplateCreate, DeployRequest
from core.config_template.worker_client import (
    DEFAULT_COMMAND_TIMEOUT,
    TASK_TIMEOUT_BUFFER,
    poll_interval_for,
)


class TestSchema:
    def test_template_create_default_timeout(self):
        data = ConfigTemplateCreate(name="t", type="command", command="dir", config_content="")
        assert data.command_timeout == DEFAULT_COMMAND_TIMEOUT

    def test_template_create_rejects_zero(self):
        with pytest.raises(ValueError):
            ConfigTemplateCreate(
                name="t", type="command", command="dir", config_content="", command_timeout=0
            )

    def test_template_create_rejects_over_1h(self):
        with pytest.raises(ValueError):
            ConfigTemplateCreate(
                name="t", type="command", command="dir", config_content="", command_timeout=3601
            )

    def test_deploy_request_accepts_timeout_override(self):
        data = DeployRequest(template_id="t1", machine_ids=["m1"], timeout=600)
        assert data.timeout == 600

    def test_deploy_request_timeout_optional(self):
        data = DeployRequest(template_id="t1", machine_ids=["m1"])
        assert data.timeout is None


class TestPollInterval:
    def test_20min_budget_uses_60s_interval(self):
        """用户设定 20 分钟 → 慢轮询 1 分钟一次"""
        assert poll_interval_for(elapsed=120, total_timeout=1200 + 60) == 60.0

    def test_short_budget_clamps_to_20s(self):
        assert poll_interval_for(elapsed=120, total_timeout=180) == 20.0

    def test_1h_budget_clamps_to_120s(self):
        assert poll_interval_for(elapsed=120, total_timeout=3660) == 120.0

    def test_fast_phase_uses_3s(self):
        assert poll_interval_for(elapsed=10, total_timeout=120 + 60) == 3.0


class _CapturePostClient:
    """捕获 POST payload 的假 httpx 客户端。"""

    captured: dict = {}
    status_code = 200

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, headers=None):
        _CapturePostClient.captured = {"url": url, "json": json, "headers": headers}

        class _Resp:
            status_code = 200

            def json(self):
                return {"task_id": "task_x", "status": "accepted", "request_id": "r"}

        return _Resp()


@pytest.mark.asyncio
async def test_execute_single_command_sends_timeouts(monkeypatch):
    """命令超时映射：动作级 timeout 精确等待，任务级 config.timeout 加余量兜底"""
    async def _fake_wait(ip, port, task_id, total_timeout=600.0):
        _CapturePostClient.captured["wait_total"] = total_timeout
        return {"success": True, "stdout": "ok", "stderr": "", "duration": 1.0}

    monkeypatch.setattr(worker_client_module.httpx, "AsyncClient", _CapturePostClient)
    monkeypatch.setattr(worker_client_module, "wait_task_result", _fake_wait)

    machine = {"id": "m1", "ip": "10.0.0.5", "port": 8000, "device_type": "windows"}
    result = await worker_client_module.execute_single_command(
        machine, "long_task.bat", "parent-1", command_timeout=1200
    )

    assert result["success"] is True
    sent = _CapturePostClient.captured["json"]
    assert sent["actions"][0]["action_type"] == "cmd_exec"
    assert sent["actions"][0]["timeout"] == 1200 * 1000
    assert sent["config"]["timeout"] == (1200 + TASK_TIMEOUT_BUFFER) * 1000
    assert _CapturePostClient.captured["wait_total"] == 1200 + TASK_TIMEOUT_BUFFER


@pytest.mark.asyncio
async def test_execute_single_command_default_timeout(monkeypatch):
    """不传超时时默认 120 秒"""
    async def _fake_wait(ip, port, task_id, total_timeout=600.0):
        return {"success": True, "stdout": "ok", "stderr": "", "duration": 1.0}

    monkeypatch.setattr(worker_client_module.httpx, "AsyncClient", _CapturePostClient)
    monkeypatch.setattr(worker_client_module, "wait_task_result", _fake_wait)

    machine = {"id": "m1", "ip": "10.0.0.5", "port": 8000, "device_type": "windows"}
    await worker_client_module.execute_single_command(machine, "dir", "parent-1")

    sent = _CapturePostClient.captured["json"]
    assert sent["actions"][0]["timeout"] == DEFAULT_COMMAND_TIMEOUT * 1000
