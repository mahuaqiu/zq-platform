#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
版本对比标签 Schema
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CompareTagCreate(BaseModel):
    """创建对比标签请求"""
    name: str = Field(..., max_length=100, description="标签名称")
    type: str = Field(default="peak", description="类型: peak(冲高) / stable(稳态)")
    start_time: int = Field(..., ge=0, description="开始时间（相对秒数）")
    end_time: int = Field(..., ge=0, description="结束时间（相对秒数）")
    note: Optional[str] = Field(None, max_length=500, description="备注")


class CompareTagUpdate(BaseModel):
    """更新对比标签请求"""
    name: Optional[str] = Field(None, max_length=100)
    type: Optional[str] = Field(None)
    start_time: Optional[int] = Field(None, ge=0)
    end_time: Optional[int] = Field(None, ge=0)
    note: Optional[str] = Field(None, max_length=500)


class CompareTagResponse(BaseModel):
    """对比标签响应"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    type: str
    type_display: str = ""
    start_time: int
    end_time: int
    note: Optional[str]