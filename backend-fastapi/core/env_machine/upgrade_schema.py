#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time: 2026-04-10
@File: upgrade_schema.py
@Desc: Worker 升级管理 Schema
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class UpgradeConfigResponse(BaseModel):
    """升级配置响应"""
    id: str = Field(..., description="配置ID")
    device_type: str = Field(..., description="设备类型: windows/mac")
    version: str = Field(..., description="目标版本号")
    download_url: str = Field(..., description="下载地址")
    note: Optional[str] = Field(None, description="备注")

    model_config = {"from_attributes": True}


class UpgradeConfigUpdateRequest(BaseModel):
    """更新升级配置请求"""
    version: str = Field(..., description="目标版本号")
    download_url: str = Field(..., description="下载地址")
    note: Optional[str] = Field(None, description="备注")


class WorkerUpgradeInfo(BaseModel):
    """Worker 获取升级信息响应"""
    version: str = Field(..., description="目标版本号")
    download_url: str = Field(..., description="下载地址")


class StartUpgradeRequest(BaseModel):
    """Worker 手动触发升级请求"""
    machine_id: str = Field(..., description="机器ID")
    version: str = Field(..., description="目标版本号")


class BatchUpgradeRequest(BaseModel):
    """批量升级请求"""
    machine_ids: Optional[List[str]] = Field(None, description="指定机器ID列表")
    namespace: Optional[str] = Field(None, description="设备类别筛选")
    device_type: Optional[str] = Field(None, description="设备类型筛选")


class UpgradeDetail(BaseModel):
    """升级详情"""
    machine_id: str = Field(..., description="机器ID")
    ip: str = Field(..., description="IP地址")
    status: str = Field(..., description="状态: upgraded/waiting/skipped/failed")
    message: str = Field(..., description="消息")


class BatchUpgradeResponse(BaseModel):
    """批量升级响应"""
    upgraded_count: int = Field(default=0, description="已升级数量")
    waiting_count: int = Field(default=0, description="等待队列数量")
    skipped_count: int = Field(default=0, description="跳过数量")
    failed_count: int = Field(default=0, description="失败数量")
    details: List[UpgradeDetail] = Field(default_factory=list, description="详情列表")


class UpgradeQueueItem(BaseModel):
    """升级队列项"""
    id: str = Field(..., description="队列ID")
    machine_id: str = Field(..., description="机器ID")
    ip: Optional[str] = Field(None, description="IP地址")
    device_type: str = Field(..., description="设备类型")
    target_version: str = Field(..., description="目标版本")
    status: str = Field(..., description="状态")
    created_at: Optional[datetime] = Field(None, description="入队时间")

    model_config = {"from_attributes": True}


class UpgradePreviewResponse(BaseModel):
    """升级预览响应"""
    upgradable_count: int = Field(default=0, description="可升级数量")
    waiting_count: int = Field(default=0, description="待队列数量")
    latest_count: int = Field(default=0, description="已最新数量")
    offline_count: int = Field(default=0, description="离线数量")
    machines: List[dict] = Field(default_factory=list, description="机器列表")