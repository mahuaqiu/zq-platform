"""性能采集请求 schema 契约测试。"""

import pytest
from pydantic import ValidationError

from core.performance_monitor.schema import CollectStartRequest


def _request(**overrides):
    payload = {"collect_id": "c1", "device_id": "d1"}
    payload.update(overrides)
    return CollectStartRequest(**payload)


def test_collect_start_timeout_caps_at_24_hours():
    """与 worker 侧 CollectStartRequest 约定一致：timeout 上限统一 24 小时（86400 秒）。"""
    assert _request(timeout=86400).timeout == 86400
    with pytest.raises(ValidationError):
        _request(timeout=86401)
