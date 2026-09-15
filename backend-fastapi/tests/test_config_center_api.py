"""配置中心 API 测试：列表分页契约 + 免鉴权查询接口行为。"""

import asyncio
import inspect
import json

import pytest
from fastapi import HTTPException

from core.config_center import api as config_center_api
from core.config_center import public_api as config_center_public


def test_list_config_items_accepts_camel_case_page_size():
    """前端以 pageSize 传参，后端 Query 必须声明 alias="pageSize"（与全库列表接口惯例一致）。"""
    query = inspect.signature(config_center_api.list_config_items).parameters[
        "page_size"
    ].default
    assert query.alias == "pageSize"


class _FakeItem:
    """替代 ORM 对象：免鉴权查询只读 value 字段。"""

    def __init__(self, value: str):
        self.value = value


def _query(monkeypatch, item) -> dict:
    """绕过 DB 直接调用查询函数，monkeypatch 服务层按键查找。"""

    async def fake_get_by_field(db, field, key):
        assert field == "key"
        return item

    monkeypatch.setattr(
        config_center_public.ConfigCenterService, "get_by_field", fake_get_by_field
    )
    return asyncio.run(
        config_center_public.query_config_value(key="ocr_config", db=None)
    )


def test_public_query_returns_parsed_dict(monkeypatch):
    """key=ocr_config 时返回解析后的字典本身，如 {"充许": "允许"}。"""
    value = json.dumps({"充许": "允许", "聊关": "聊天"}, ensure_ascii=False)
    result = _query(monkeypatch, _FakeItem(value))
    assert result == {"充许": "允许", "聊关": "聊天"}


def test_public_query_404_when_key_missing(monkeypatch):
    with pytest.raises(HTTPException) as exc_info:
        _query(monkeypatch, None)
    assert exc_info.value.status_code == 404


def test_public_query_422_when_value_not_json(monkeypatch):
    with pytest.raises(HTTPException) as exc_info:
        _query(monkeypatch, _FakeItem("not-json"))
    assert exc_info.value.status_code == 422


def test_public_query_422_when_value_not_dict(monkeypatch):
    with pytest.raises(HTTPException) as exc_info:
        _query(monkeypatch, _FakeItem('["a", "b"]'))
    assert exc_info.value.status_code == 422
