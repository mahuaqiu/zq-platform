#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File: schema.py
@Desc: ConfigCenter Schema - 配置中心数据验证模式
"""
import json
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

KEY_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


def _validate_pairs_json(value: str) -> str:
    """校验 value 是合法 JSON 且为 {str: str} 对象"""
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"配置值必须是合法的 JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("配置值必须是 JSON 对象（键值对）")
    for k, v in parsed.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise ValueError("配置值的键和值都必须是字符串")
    return value


class ConfigCenterItemCreate(BaseModel):
    """创建配置项请求"""
    key: str = Field(..., pattern=KEY_PATTERN, description="配置键（字母/数字/下划线/中划线，≤64字符）")
    value: str = Field(..., description='配置值 JSON 对象字符串，如 {"充许":"允许"}')
    remark: Optional[str] = Field(None, description="备注")

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: str) -> str:
        return _validate_pairs_json(v)


class ConfigCenterItemUpdate(BaseModel):
    """更新配置项请求（key 不可修改）"""
    value: Optional[str] = Field(None, description="配置值 JSON 对象字符串")
    remark: Optional[str] = Field(None, description="备注")

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return _validate_pairs_json(v)


class ConfigCenterItemResponse(BaseModel):
    """配置项响应"""
    id: str = Field(..., description="配置项ID")
    key: str = Field(..., description="配置键")
    value: str = Field(..., description="配置值 JSON 字符串")
    remark: Optional[str] = Field(None, description="备注")
    sys_create_datetime: Optional[datetime] = Field(None, description="创建时间")
    sys_update_datetime: Optional[datetime] = Field(None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class ConfigCenterBatchDeleteRequest(BaseModel):
    """批量删除请求"""
    ids: List[str] = Field(..., min_length=1, description="配置项ID列表")
