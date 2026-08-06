"""Worker 设备级 namespace 拉取恢复测试。"""

import pytest

from core.env_machine.scheduler import _get_reported_namespace, _validate_worker_namespace_payload


def test_device_namespace_prefers_exact_device_override() -> None:
    """平台重启恢复应读取 Worker 的具体设备归属。"""
    payload = {
        "namespace": "meeting_public",
        "device_namespaces": {
            "windows": "meeting_gamma",
            "android": {
                "device-001": "meeting_app",
            },
        },
    }

    assert _get_reported_namespace(payload, "windows") == "meeting_gamma"
    assert _get_reported_namespace(payload, "android", "device-001") == "meeting_app"
    with pytest.raises(ValueError, match="android/device-002"):
        _get_reported_namespace(payload, "android", "device-002")


def test_device_namespace_requires_explicit_mapping() -> None:
    """平台恢复不再接受旧 Worker 的顶层 namespace。"""
    with pytest.raises(ValueError, match="device_namespaces"):
        _get_reported_namespace({"namespace": "meeting_public"}, "ios", "device-001")


def test_worker_namespace_validation_rejects_missing_connected_device_mapping() -> None:
    """在线设备没有精确 namespace 时，平台不应部分恢复该 Worker。"""
    machine = type(
        "Machine",
        (),
        {"device_type": "android", "device_sn": "device-001"},
    )()
    worker_data = {
        "devices": {"android": [{"udid": "device-001"}]},
        "device_namespaces": {"android": {}},
    }

    with pytest.raises(ValueError, match="android/device-001"):
        _validate_worker_namespace_payload(worker_data, [machine])
