"""配置中心 API 契约测试。"""

import inspect

from core.config_center import api as config_center_api


def test_list_config_items_accepts_camel_case_page_size():
    """前端以 pageSize 传参，后端 Query 必须声明 alias="pageSize"（与全库列表接口惯例一致）。"""
    query = inspect.signature(config_center_api.list_config_items).parameters[
        "page_size"
    ].default
    assert query.alias == "pageSize"
