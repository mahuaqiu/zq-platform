"""配置模板下发对鸿蒙设备的边界单测。"""

from unittest.mock import MagicMock

from core.config_template.service import ConfigTemplateService


def test_harmony_machine_is_rejected_by_config_deploy_guard() -> None:
    """鸿蒙 HDC target 不应进入 Worker 宿主机配置下发。"""
    machine = MagicMock()
    machine.device_type = "harmony_pc"
    allowed, reason = ConfigTemplateService._should_deploy(machine, MagicMock())
    assert allowed is False
    assert reason == "该设备类型暂不支持配置下发"
