"""鸿蒙设备资源池标签和独立占用逻辑单测。"""

from core.env_machine.pool_manager import EnvPoolManager


def _harmony_machine(device_type: str, udid: str, mark: str = "harmony") -> dict:
    """构造资源池缓存中的鸿蒙设备。"""
    return {
        "id": f"machine-{udid}",
        "ip": "10.0.0.10",
        "port": 8080,
        "device_type": device_type,
        "device_sn": udid,
        "status": "online",
        "available": True,
        "mark": mark,
        "is_virtual": False,
        "extra_message": {},
    }


def test_harmony_tags_keep_full_device_type() -> None:
    """移动和 PC 标签提取后不能退化为通用 harmony。"""
    assert EnvPoolManager.validate_single_tag("harmony_mobile_phone") == (True, "")
    assert EnvPoolManager.validate_single_tag("harmony_pc_desktop") == (True, "")
    assert EnvPoolManager._device_type_from_tag("harmony_mobile_phone") == "harmony_mobile"
    assert EnvPoolManager._device_type_from_tag("harmony_pc_desktop") == "harmony_pc"


def test_harmony_devices_are_allocated_by_udid() -> None:
    """同一宿主机 IP 下不同鸿蒙 target 可以并行申请，同一 UDID 不能重复占用。"""
    machines = {
        "m1": _harmony_machine("harmony_pc", "pc-001", "harmony_pc_desktop"),
        "m2": _harmony_machine("harmony_pc", "pc-002", "harmony_pc_desktop"),
    }
    occupied_ips: set[str] = set()
    occupied_sns: set[str] = set()

    first = EnvPoolManager._allocate_single(
        machines, "harmony_pc_desktop", occupied_ips, occupied_sns
    )
    second = EnvPoolManager._allocate_single(
        machines, "harmony_pc_desktop", occupied_ips, occupied_sns
    )

    assert first is not None
    assert second is not None
    assert first["device_type"] == "harmony_pc"
    assert second["device_type"] == "harmony_pc"
    assert first["device_sn"] != second["device_sn"]
    assert occupied_ips == set()
    assert occupied_sns == {"pc-001", "pc-002"}


def test_harmony_tag_validation_rejects_unknown_prefix() -> None:
    """未知平台标签仍然必须被拒绝。"""
    valid, message = EnvPoolManager.validate_single_tag("ohos_pc_desktop")
    assert valid is False
    assert "标签前缀" in message


def test_harmony_tag_validation_rejects_generic_harmony_prefix() -> None:
    """鸿蒙标签必须明确区分移动和 PC。"""
    valid, message = EnvPoolManager.validate_single_tag("harmony_desktop")
    assert valid is False
    assert "harmony_mobile" in message
