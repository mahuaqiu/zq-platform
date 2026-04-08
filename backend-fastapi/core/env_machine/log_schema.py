#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: Claude
@Time: 2026-04-04
@File: log_schema.py
@Desc: 执行机申请日志 Schema
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EnvMachineLogCreate(BaseModel):
    """创建申请日志请求"""
    namespace: str = Field(..., description="机器分类")
    machine_id: str = Field(..., description="机器ID")
    ip: Optional[str] = Field(None, description="机器IP")
    device_type: str = Field(..., description="机器类型")
    device_sn: Optional[str] = Field(None, description="设备SN")
    mark: Optional[str] = Field(None, description="申请的标签")
    source_pool: Optional[str] = Field(None, description="机器来源池")  # 新增
    testcase_id: Optional[str] = Field(None, description="用例编号")
    action: str = Field(..., description="操作类型: apply/release")
    result: str = Field(..., description="结果: success/fail")
    fail_reason: Optional[str] = Field(None, description="失败原因")
    apply_time: Optional[datetime] = Field(None, description="申请时间")


class EnvMachineLogUpdate(BaseModel):
    """更新申请日志请求（释放时使用）"""
    release_time: Optional[datetime] = Field(None, description="释放时间")
    duration_minutes: Optional[int] = Field(None, description="占用时长（分钟）")


class EnvMachineLogResponse(BaseModel):
    """申请日志响应"""
    id: str = Field(..., description="日志ID")
    namespace: str = Field(..., description="机器分类")
    machine_id: str = Field(..., description="机器ID")
    ip: Optional[str] = Field(None, description="机器IP")
    device_type: str = Field(..., description="机器类型")
    device_sn: Optional[str] = Field(None, description="设备SN")
    mark: Optional[str] = Field(None, description="申请的标签")
    source_pool: Optional[str] = Field(None, description="机器来源池")  # 新增
    testcase_id: Optional[str] = Field(None, description="用例编号")
    action: str = Field(..., description="操作类型")
    result: str = Field(..., description="结果")
    fail_reason: Optional[str] = Field(None, description="失败原因")
    apply_time: Optional[datetime] = Field(None, description="申请时间")
    release_time: Optional[datetime] = Field(None, description="释放时间")
    duration_minutes: Optional[int] = Field(None, description="占用时长（分钟）")
    sys_create_datetime: Optional[datetime] = Field(None, description="创建时间")

    model_config = {"from_attributes": True}


# ============ 统计相关 Schema ============

class DeviceTypeStats(BaseModel):
    """设备类型统计"""
    type: str = Field(..., description="设备类型")
    total: int = Field(..., description="总数")
    enabled: int = Field(..., description="启用数")
    disabled: int = Field(..., description="未启用数")


class DeviceStats(BaseModel):
    """设备统计"""
    total: int = Field(..., description="设备总数")
    online: int = Field(..., description="在线数")
    offline: int = Field(..., description="离线数")
    by_type: List[DeviceTypeStats] = Field(default_factory=list, description="按类型统计")


class Apply24hStats(BaseModel):
    """24小时申请统计"""
    total: int = Field(..., description="申请总次数")
    success: int = Field(..., description="成功次数")
    failed: int = Field(..., description="资源不足次数")


class TopTagItem(BaseModel):
    """TOP标签项"""
    tag: str = Field(..., description="标签")
    count: int = Field(..., description="次数")


class TopDurationItem(BaseModel):
    """TOP占用时长项"""
    ip: Optional[str] = Field(None, description="IP地址")
    device_sn: Optional[str] = Field(None, description="设备SN")
    device_type: str = Field(..., description="设备类型")
    duration_minutes: int = Field(..., description="占用时长（分钟）")
    duration_display: str = Field(..., description="显示格式")


class OfflineMachineItem(BaseModel):
    """离线机器项"""
    id: str = Field(..., description="机器ID")
    ip: Optional[str] = Field(None, description="IP地址")
    device_sn: Optional[str] = Field(None, description="设备SN")
    device_type: str = Field(..., description="设备类型")
    offline_duration: str = Field(..., description="离线时长")


class DashboardStatsResponse(BaseModel):
    """看板统计响应"""
    device_stats: DeviceStats = Field(..., description="设备统计")
    apply_24h: Apply24hStats = Field(..., description="24小时申请统计")
    top10_tags: List[TopTagItem] = Field(default_factory=list, description="TOP10标签申请次数")
    top20_duration: List[TopDurationItem] = Field(default_factory=list, description="TOP20占用时长")
    top10_insufficient: List[TopTagItem] = Field(default_factory=list, description="TOP10资源不足标签")
    offline_machines: List[OfflineMachineItem] = Field(default_factory=list, description="离线机器列表")