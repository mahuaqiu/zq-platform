#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2025-03-25
@File: schema.py
@Desc: EnvMachine Schema - 执行机管理数据验证模式
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class EnvRegisterRequest(BaseModel):
    """执行机注册请求 Schema"""
    ip: str = Field(..., description="机器IP")
    port: str = Field(..., description="机器端口")
    namespace: str = Field(..., description="机器分类")
    version: Optional[str] = Field(None, description="机器版本")
    devices: Dict[str, List[str]] = Field(..., description="设备列表，key为device_type，value为device_sn列表")


class EnvMachineAllocation(BaseModel):
    """执行机申请请求 Schema"""
    id: str = Field(..., description="机器ID")
    ip: str = Field(..., description="机器IP")
    port: str = Field(..., description="机器端口")
    device_type: str = Field(..., description="机器类型")
    device_sn: Optional[str] = Field(None, description="设备SN")

    model_config = ConfigDict(extra="allow")


class EnvMachineIdItem(BaseModel):
    """执行机ID请求 Schema"""
    id: str = Field(..., description="机器ID")


class EnvSuccessResponse(BaseModel):
    """成功响应 Schema"""
    status: str = Field(default="success", description="响应状态")
    data: Any = Field(default=None, description="响应数据")


class EnvFailResponse(BaseModel):
    """失败响应 Schema"""
    status: str = Field(default="fail", description="响应状态")
    result: str = Field(..., description="错误描述")


class EnvMachineResponse(BaseModel):
    """执行机信息响应 Schema"""
    id: str = Field(..., description="机器ID")
    namespace: str = Field(..., description="机器分类")
    ip: str = Field(..., description="机器IP")
    port: str = Field(..., description="机器端口")
    mark: Optional[str] = Field(None, description="机器标签")
    device_type: str = Field(..., description="机器类型")
    device_sn: Optional[str] = Field(None, description="设备SN")
    available: bool = Field(..., description="是否启用")
    status: str = Field(..., description="状态")
    status_display: Optional[str] = Field(None, description="状态显示名称")
    note: Optional[str] = Field(None, description="备注")
    sync_time: Optional[datetime] = Field(None, description="同步时间")
    extra_message: Optional[Dict[str, Any]] = Field(None, description="扩展信息")
    version: Optional[str] = Field(None, description="机器版本")
    last_keepusing_time: Optional[datetime] = Field(None, description="最后保持使用时间")
    sort: int = Field(default=0, description="排序")
    is_deleted: bool = Field(default=False, description="是否删除")
    sys_create_datetime: Optional[datetime] = Field(None, description="创建时间")
    sys_update_datetime: Optional[datetime] = Field(None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)