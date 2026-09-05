"""版本号比较回归测试：防止退回字符串比较（"10.0" < "9.0"）。"""

import pytest

from utils.version import compare_versions


class TestCompareVersions:
    def test_double_digit_not_older_than_single(self):
        """10.x 不能被判旧于 9.x（字符串比较的经典错误）"""
        assert compare_versions("10.0", "9.0") == 1
        assert compare_versions("9.0", "10.0") == -1

    def test_upgrade_service_scenario(self):
        """升级服务场景：升到 10.x 的机器不应再被 9.x 配置触发升级"""
        assert compare_versions("10.0.2", "9.9") >= 0
        assert compare_versions("10.0", "10.0") == 0

    def test_multi_segment_numeric(self):
        assert compare_versions("1.2.3", "1.2.10") == -1
        assert compare_versions("1.2.10", "1.2.3") == 1
        assert compare_versions("1.2.3", "1.2.3") == 0

    def test_missing_segments_treated_as_zero(self):
        assert compare_versions("1.2", "1.2.0") == 0
        assert compare_versions("1.2", "1.2.1") == -1

    def test_non_numeric_segments(self):
        """非数字段（如 rc/beta）按字符串比较"""
        assert compare_versions("1.0.0", "1.0.0-rc1") == 1
        assert compare_versions("1.0.0-rc1", "1.0.0-rc2") == -1

    @pytest.mark.parametrize("left,right", [("10.0", "9.0"), ("2.3.1", "2.3"), ("1.10", "1.9")])
    def test_left_greater(self, left, right):
        assert compare_versions(left, right) == 1
