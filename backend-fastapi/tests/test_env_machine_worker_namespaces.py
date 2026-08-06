"""Worker 设备级 namespace 拉取恢复测试。"""

from core.env_machine.scheduler import _get_reported_namespace


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
    assert _get_reported_namespace(payload, "android", "device-002") == "meeting_public"


def test_device_namespace_falls_back_to_legacy_global_value() -> None:
    """旧 Worker 没有设备级字段时继续使用原全局 namespace。"""
    assert _get_reported_namespace({"namespace": "meeting_public"}, "ios", "device-001") == "meeting_public"
