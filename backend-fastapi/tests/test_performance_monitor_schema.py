"""性能采集请求 schema 契约测试。"""

import pytest
from pydantic import ValidationError

from core.performance_monitor.schema import CollectStartRequest


def _request(**overrides):
    payload = {"device_id": "d1"}
    payload.update(overrides)
    return CollectStartRequest(**payload)


def test_collect_start_timeout_caps_at_24_hours():
    """与 worker 侧 CollectStartRequest 约定一致：timeout 上限统一 24 小时（86400 秒）。"""
    assert _request(timeout=86400).timeout == 86400
    with pytest.raises(ValidationError):
        _request(timeout=86401)


def test_collect_start_timeout_defaults_to_12_hours():
    assert _request().timeout == 43200


def test_collect_start_timeout_floor_is_one_hour():
    """下界 3600 秒（比 Worker 侧 60 秒下限更严）：防止误传小值触发高频采集。"""
    assert _request(timeout=3600).timeout == 3600
    with pytest.raises(ValidationError):
        _request(timeout=3599)
