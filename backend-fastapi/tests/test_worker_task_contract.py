"""Worker 任务生命周期契约测试。"""

import pytest

from core.config_template.api import _wait_task_result
from core.env_machine.api import _worker_error_message


def test_worker_error_message_supports_structured_error() -> None:
    assert _worker_error_message(
        {"error": {"code": "DEVICE_BUSY", "message": "设备忙碌"}},
        "失败",
    ) == "设备忙碌"


def test_worker_error_message_supports_legacy_string() -> None:
    assert _worker_error_message({"error": "旧错误"}, "失败") == "旧错误"


@pytest.mark.asyncio
async def test_wait_task_result_accepts_cancelling_then_terminal(monkeypatch) -> None:
    responses = iter([
        {"status": "cancelling", "actions": []},
        {"status": "cancelled", "actions": [{"error": "用户取消"}]},
    ])

    class Response:
        status_code = 200

        def json(self):
            return next(responses)

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            return Response()

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr("core.config_template.api.httpx.AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr("core.config_template.api.asyncio.sleep", no_sleep)
    result = await _wait_task_result("127.0.0.1", 8080, "task-1")
    assert result["success"] is False
    assert result["stderr"] == "用户取消"