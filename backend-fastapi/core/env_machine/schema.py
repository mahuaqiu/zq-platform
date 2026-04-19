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
    config_version: Optional[str] = Field(None, description="配置版本")
    devices: Dict[str, List[Any]] = Field(..., description="设备列表，key为device_type，value为device_sn列表（字符串或{\"udid\":\"...\"}对象）")


class EnvMachineListRequest(BaseModel):
    """执行机列表查询请求 Schema"""
    namespace: Optional[str] = Field(None, description="机器分类，None表示查询全部")
    device_type: Optional[str] = Field(None, description="机器类型")
    ip: Optional[str] = Field(None, description="IP地址（模糊查询）")
    asset_number: Optional[str] = Field(None, description="资产编号（模糊查询）")
    mark: Optional[str] = Field(None, description="标签（模糊查询）")
    available: Optional[bool] = Field(None, description="是否启用")
    note: Optional[str] = Field(None, description="备注（模糊查询）")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


class EnvMachineCreateRequest(BaseModel):
    """新增执行机请求 Schema"""
    namespace: str = Field(..., description="机器分类")
    device_type: str = Field(..., description="机器类型：windows/mac/ios/android")
    asset_number: str = Field(..., description="资产编号（必填）")
    ip: Optional[str] = Field(None, description="IP地址（Windows/Mac）")
    device_sn: Optional[str] = Field(None, description="设备SN（iOS/Android）")
    note: Optional[str] = Field(None, description="备注")


class EnvMachineUpdateRequest(BaseModel):
    """更新执行机请求 Schema"""
    asset_number: Optional[str] = Field(None, description="资产编号")
    ip: Optional[str] = Field(None, description="IP地址")
    device_sn: Optional[str] = Field(None, description="设备SN")
    mark: Optional[str] = Field(None, description="标签")
    available: Optional[bool] = Field(None, description="是否启用")
    note: Optional[str] = Field(None, description="备注")
    extra_message: Optional[Dict[str, Any]] = Field(None, description="扩展信息(JSON格式，包含机器使用的账号信息)")


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
    asset_number: Optional[str] = Field(None, description="资产编号")
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
    config_version: Optional[str] = Field(None, description="配置版本")
    last_keepusing_time: Optional[datetime] = Field(None, description="最后保持使用时间")
    sort: int = Field(default=0, description="排序")
    is_deleted: bool = Field(default=False, description="是否删除")
    sys_create_datetime: Optional[datetime] = Field(None, description="创建时间")
    sys_update_datetime: Optional[datetime] = Field(None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class DebugActionRequest(BaseModel):
    """设备调试操作请求 Schema"""
    action_type: str = Field(..., description="操作类型：click/swipe/input/press/screenshot")
    params: Dict[str, Any] = Field(default_factory=dict, description="操作参数")


class DebugActionResponse(BaseModel):
    """设备调试操作响应 Schema"""
    success: bool = Field(..., description="操作是否成功")
    result: Optional[Dict[str, Any]] = Field(None, description="操作结果，如截图返回 screenshot_base64")