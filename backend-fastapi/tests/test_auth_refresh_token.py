"""refresh_token Authorization 头解析回归测试。

头缺失 / 为空 / 只有 scheme 时必须返回 401（通过 None 值触发），
而不是抛 AttributeError / IndexError 导致 500。
"""

# core.auth.api 引入 User 模型但不含其 relationship 链依赖的 Dept/Role/Menu 等模型。
# 与生产一致地导入 core.router（全量路由 → 全量模型注册），
# 避免 SQLAlchemy 懒配置 mapper 时 "Dept/Role/Menu is not defined" 的导入顺序问题
import core.router  # noqa: F401

from core.auth.api import _extract_refresh_token


class TestExtractRefreshToken:
    def test_bearer_prefix(self):
        """前端标准形式：Bearer <token>"""
        assert _extract_refresh_token("Bearer abc.def.ghi") == "abc.def.ghi"

    def test_missing_header(self):
        """头缺失：原实现在这里抛 AttributeError → 500"""
        assert _extract_refresh_token(None) is None

    def test_empty_header(self):
        assert _extract_refresh_token("") is None
        assert _extract_refresh_token("   ") is None

    def test_no_space(self):
        """头无空格：原实现在这里抛 IndexError → 500；
        现按裸 token 返回，后续 verify_refresh_token 校验失败 → 401"""
        assert _extract_refresh_token("Bearer") == "Bearer"

    def test_scheme_only_with_trailing_space(self):
        """"Bearer " 去首尾空格后等同 "Bearer"（无空格），按裸 token 返回，
        后续 verify_refresh_token 校验失败 → 401，不会 500"""
        assert _extract_refresh_token("Bearer ") == "Bearer"

    def test_bare_token(self):
        """兼容裸 token（无 scheme）"""
        assert _extract_refresh_token("abc.def.ghi") == "abc.def.ghi"

    def test_other_scheme(self):
        assert _extract_refresh_token("Token abc") == "abc"
