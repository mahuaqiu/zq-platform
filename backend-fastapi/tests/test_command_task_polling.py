"""命令任务结果轮询回归测试。

覆盖 _wait_task_result 的响应解读（_interpret_task_poll）与轮询循环行为：
- 404 必须立即失败（原来 NameError 被裸 except 吞掉后空轮询 600s）
- 网络异常 / 5xx 连续失败快速终止（不再悬挂 10 分钟）
- 正常 running → success / failed 终态返回
"""

import time

import pytest

from core.config_template.api import _interpret_task_poll, _wait_task_result


class TestInterpretTaskPoll:
    def test_running_status_continues(self):
        action, result = _interpret_task_poll(
            200, {"status": "running", "actions": []}
        )
        assert action == "running"
        assert result is None

    def test_accepted_and_cancelling_continue(self):
        for status in ("accepted", "pending", "cancelling"):
            action, _ = _interpret_task_poll(200, {"status": status})
            assert action == "running"

    def test_success_terminal(self):
        action, result = _interpret_task_poll(
            200, {"status": "success", "actions": [{"stdout": "ok", "stderr": ""}]}
        )
        assert action == "done"
        assert result["success"] is True
        assert result["stdout"] == "ok"

    def test_failed_terminal(self):
        action, result = _interpret_task_poll(
            200, {"status": "failed", "actions": [{"stderr": "boom"}]}
        )
        assert action == "done"
        assert result["success"] is False
        assert "boom" in result["stderr"]

    def test_unknown_status_fails_immediately(self):
        """200 但状态值不认识：确定失败，不允许静默轮询到超时"""
        action, result = _interpret_task_poll(200, {"status": "weird"})
        assert action == "done"
        assert result["success"] is False
        assert "weird" in result["stderr"]

    def test_404_is_terminal(self):
        """任务不存在（Worker 重启/过期）必须立即失败——原实现的死代码路径"""
        action, result = _interpret_task_poll(404, None)
        assert action == "gone"
        assert result["success"] is False
        assert "任务不存在" in result["stderr"]

    def test_5xx_is_retryable(self):
        action, result = _interpret_task_poll(502, None)
        assert action == "retry"
        assert result is None

    def test_non_json_200_is_retryable(self):
        """200 但 JSON 解析失败（payload=None）按暂时性失败处理"""
        action, result = _interpret_task_poll(200, None)
        assert action == "retry"


class _AlwaysFailClient:
    """get 始终抛连接异常的假 AsyncClient"""

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url):
        raise ConnectionError("connection refused")


class _NotFoundClient(_AlwaysFailClient):
    async def get(self, url):
        class _Resp:
            status_code = 404

            def json(self):
                return {}

        return _Resp()


@pytest.mark.asyncio
async def test_wait_task_result_fails_fast_on_connection_errors(monkeypatch):
    """网络连续失败 5 次必须终止，而不是空轮询 600 秒"""
    import core.config_template.api as api_module

    async def _no_sleep(_):
        pass

    monkeypatch.setattr(api_module.httpx, "AsyncClient", _AlwaysFailClient)
    monkeypatch.setattr(api_module.asyncio, "sleep", _no_sleep)

    start = time.monotonic()
    result = await _wait_task_result("10.0.0.1", "8080", "task-1")

    assert result["success"] is False
    assert "connection refused" in result["stderr"]
    # 5 次失败 + 无真实 sleep，远小于 600s 超时即返回
    assert time.monotonic() - start < 600
    assert result["duration"] < 600


@pytest.mark.asyncio
async def test_wait_task_result_404_returns_immediately(monkeypatch):
    """Worker 返回 404 时第一次查询即失败返回"""
    import core.config_template.api as api_module

    async def _no_sleep(_):
        pass

    monkeypatch.setattr(api_module.httpx, "AsyncClient", _NotFoundClient)
    monkeypatch.setattr(api_module.asyncio, "sleep", _no_sleep)

    result = await _wait_task_result("10.0.0.1", "8080", "task-gone")

    assert result["success"] is False
    assert "任务不存在" in result["stderr"]
