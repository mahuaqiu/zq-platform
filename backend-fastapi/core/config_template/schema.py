#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2025-04-15
@File: schema.py
@Desc: ConfigTemplate Schema - 配置模板数据验证模式
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ConfigTemplateCreate(BaseModel):
    """创建配置模板请求 Schema"""
    name: str = Field(..., max_length=64, description="模板名称")
    namespace: Optional[str] = Field(None, max_length=64, description="命名空间")
    note: Optional[str] = Field(None, description="备注")
    config_content: str = Field(..., description="配置内容")


class ConfigTemplateUpdate(BaseModel):
    """更新配置模板请求 Schema"""
    name: Optional[str] = Field(None, max_length=64, description="模板名称")
    namespace: Optional[str] = Field(None, max_length=64, description="命名空间")
    note: Optional[str] = Field(None, description="备注")
    config_content: Optional[str] = Field(None, description="配置内容")


class ConfigTemplateResponse(BaseModel):
    """配置模板响应 Schema"""
    id: str = Field(..., description="模板ID")
    name: str = Field(..., description="模板名称")
    namespace: Optional[str] = Field(None, description="命名空间")
    note: Optional[str] = Field(None, description="备注")
    config_content: str = Field(..., description="配置内容")
    version: str = Field(..., description="版本号")
    sys_create_datetime: Optional[datetime] = Field(None, description="创建时间")
    sys_update_datetime: Optional[datetime] = Field(None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class DeployRequest(BaseModel):
    """下发配置请求 Schema"""
    template_id: str = Field(..., description="模板ID")
    machine_ids: List[str] = Field(..., description="机器ID列表")


class DeployDetail(BaseModel):
    """下发详情 Schema"""
    machine_id: str = Field(..., description="机器ID")
    ip: str = Field(..., description="机器IP")
    status: str = Field(..., description="下发状态: success/failed")
    error_message: Optional[str] = Field(None, description="错误信息")


class DeployResponse(BaseModel):
    """下发配置响应 Schema"""
    success_count: int = Field(..., description="成功数量")
    failed_count: int = Field(..., description="失败数量")
    details: List[DeployDetail] = Field(..., description="下发详情列表")


class ConfigPreviewMachine(BaseModel):
    """配置预览机器 Schema"""
    id: str = Field(..., description="机器ID")
    ip: str = Field(..., description="机器IP")
    namespace: str = Field(..., description="命名空间")
    device_type: str = Field(..., description="设备类型")
    status: str = Field(..., description="设备状态")
    config_status: str = Field(..., description="配置状态: synced/pending/updating/offline")
    config_version: Optional[str] = Field(None, description="配置版本")


class ConfigPreviewResponse(BaseModel):
    """配置预览响应 Schema"""
    template_version: str = Field(..., description="模板版本")
    deployable_count: int = Field(..., description="可下发数量")
    updating_count: int = Field(..., description="更新中数量")
    offline_count: int = Field(..., description="离线数量")
    machines: List[ConfigPreviewMachine] = Field(..., description="机器列表")