#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控 Schema - 请求和响应数据验证模式
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer


# ===== 请求 Schema =====


class CollectStartRequest(BaseModel):
    """开始采集请求 Schema"""
    device_id: str = Field(..., description="设备ID")
    name: Optional[str] = Field(None, max_length=100, description="采集名称")
    interval: int = Field(default=5, ge=1, le=60, description="采集频率（秒）")
    target_processes: Optional[List[Dict[str, Any]]] = Field(None, description="目标进程配置")


class CollectStopRequest(BaseModel):
    """停止采集请求 Schema"""
    collect_id: Optional[str] = Field(None, description="采集记录ID（可选，不传则停止该设备所有采集）")
    device_id: str = Field(..., description="设备ID")


class CollectListRequest(BaseModel):
    """采集列表查询请求 Schema"""
    device_id: Optional[str] = Field(None, description="设备ID")
    status: Optional[str] = Field(None, description="状态：running/stopped/error")
    is_protected: Optional[bool] = Field(None, description="是否受保护")
    name: Optional[str] = Field(None, description="采集名称（模糊查询）")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


class CollectDataRequest(BaseModel):
    """采集数据查询请求 Schema"""
    collect_id: str = Field(..., description="采集记录ID")
    start_relative_time: Optional[int] = Field(None, ge=0, description="起始相对时间（秒）")
    end_relative_time: Optional[int] = Field(None, ge=0, description="结束相对时间（秒）")


class ProcessInstance(BaseModel):
    """进程实例 Schema"""
    instance_id: str = Field(..., description="实例ID")
    cpu_usage: Optional[float] = Field(None, ge=0, le=100, description="CPU使用率 %")
    gpu_usage: Optional[float] = Field(None, ge=0, le=100, description="GPU使用率 %")
    memory_usage: Optional[float] = Field(None, ge=0, description="内存使用 GB")
    thread_count: Optional[int] = Field(None, ge=0, description="线程数")
    handle_count: Optional[int] = Field(None, ge=0, description="句柄数")


class TargetProcess(BaseModel):
    """目标进程 Schema"""
    process_name: str = Field(..., description="进程名称")
    display_name: Optional[str] = Field(None, description="显示名称")
    instances: List[ProcessInstance] = Field(default_factory=list, description="实例列表")


class SystemMetrics(BaseModel):
    """系统指标 Schema"""
    cpu_usage: Optional[float] = Field(None, ge=0, le=100, description="CPU使用率 %")
    gpu_usage: Optional[float] = Field(None, ge=0, le=100, description="GPU使用率 %")
    commit_memory: Optional[float] = Field(None, ge=0, description="提交内存 GB")
    memory_usage: Optional[float] = Field(None, ge=0, description="内存使用 GB")
    power: Optional[float] = Field(None, ge=0, description="功耗 W")
    cpu_speed: Optional[float] = Field(None, ge=0, description="CPU速度 GHz")
    cpu_temp: Optional[float] = Field(None, description="CPU温度 °C")
    process_handles: Optional[int] = Field(None, ge=0, description="进程句柄数")
    upload_speed: Optional[float] = Field(None, ge=0, description="上传速度 KB/s")
    download_speed: Optional[float] = Field(None, ge=0, description="下载速度 KB/s")


class Top10Process(BaseModel):
    """TOP10 进程 Schema"""
    process_name: str = Field(..., description="进程名称")
    value: float = Field(..., description="指标值")


# ===== Worker 上报数据 Schema =====


class ProcessInstanceReport(BaseModel):
    """进程实例上报 Schema"""
    pid: int = Field(..., description="进程ID")
    cpu: float = Field(..., ge=0, le=100, description="CPU使用率 %")
    memory: float = Field(..., ge=0, description="内存使用 MB")
    gpu: float = Field(default=0, ge=0, le=100, description="GPU使用率 %")
    committed_memory: float = Field(default=0, ge=0, description="提交内存 MB")


class TargetProcessReport(BaseModel):
    """目标进程上报 Schema"""
    name: str = Field(..., description="进程名称")
    total_cpu: float = Field(..., ge=0, le=100, description="总CPU使用率 %")
    total_memory: float = Field(..., ge=0, description="总内存使用 MB")
    total_committed_memory: float = Field(default=0, ge=0, description="总提交内存 MB")
    total_gpu: float = Field(default=0, ge=0, le=100, description="总GPU使用率 %")
    instances: List[ProcessInstanceReport] = Field(default_factory=list, description="实例列表")


class SystemMetricsReport(BaseModel):
    """系统指标上报 Schema"""
    cpu_usage: float = Field(..., ge=0, le=100, description="CPU使用率 %")
    gpu_usage: float = Field(..., ge=0, le=100, description="GPU使用率 %")
    commit_memory: float = Field(..., ge=0, description="提交内存 GB")
    memory_usage: float = Field(..., ge=0, description="内存使用 GB")
    power: float = Field(..., ge=0, description="功耗 W")
    cpu_speed: float = Field(..., ge=0, description="CPU速度 GHz")
    cpu_temp: float = Field(..., description="CPU温度 °C")
    process_handles: int = Field(..., ge=0, description="进程句柄数")
    upload_speed: float = Field(..., ge=0, description="上传速度 KB/s")
    download_speed: float = Field(..., ge=0, description="下载速度 KB/s")


class Top10ProcessReport(BaseModel):
    """TOP10 进程上报 Schema"""
    name: str = Field(..., description="进程名称")
    cpu: Optional[float] = Field(None, description="CPU使用率 %")
    memory: Optional[float] = Field(None, description="内存使用 MB")
    gpu: Optional[float] = Field(None, description="GPU使用率 %")


class PerformanceSampleReport(BaseModel):
    """单个性能样本上报 Schema"""
    timestamp: datetime = Field(..., description="实际时间")
    relative_time: int = Field(..., ge=0, description="相对时间（秒）")
    system: SystemMetricsReport = Field(..., description="系统指标")
    target_processes: List[TargetProcessReport] = Field(default_factory=list, description="目标进程")
    top10_cpu: List[Top10ProcessReport] = Field(default_factory=list, description="CPU TOP10")
    top10_gpu: List[Top10ProcessReport] = Field(default_factory=list, description="GPU TOP10")


class WorkerReportRequest(BaseModel):
    """Worker 上报数据请求 Schema（批量上报）"""
    collect_id: str = Field(..., description="采集记录ID")
    device_id: str = Field(..., description="设备ID")
    samples: List[PerformanceSampleReport] = Field(default_factory=list, description="性能样本列表")


class PerformanceReportRequest(BaseModel):
    """性能报告请求 Schema"""
    collect_id: str = Field(..., description="采集记录ID")
    start_relative_time: Optional[int] = Field(None, ge=0, description="起始相对时间（秒）")
    end_relative_time: Optional[int] = Field(None, ge=0, description="结束相对时间（秒）")


class TagCreateRequest(BaseModel):
    """创建标签请求 Schema"""
    collect_id: str = Field(..., description="采集记录ID")
    name: str = Field(..., max_length=50, description="标签名称")
    start_relative_time: int = Field(..., ge=0, description="起始相对时间（秒）")
    duration: int = Field(..., gt=0, description="时间长度（秒）")
    type: str = Field(default="peak", description="类型：peak/mean")


class TagUpdateRequest(BaseModel):
    """更新标签请求 Schema"""
    name: Optional[str] = Field(None, max_length=50, description="标签名称")
    start_relative_time: Optional[int] = Field(None, ge=0, description="起始相对时间（秒）")
    duration: Optional[int] = Field(None, gt=0, description="时间长度（秒）")
    type: Optional[str] = Field(None, description="类型：peak/mean")


class VersionCreateRequest(BaseModel):
    """创建版本请求 Schema"""
    device_id: str = Field(..., description="设备ID")
    name: str = Field(..., max_length=100, description="版本名称")
    collect_ids: List[str] = Field(..., description="包含的采集记录ID列表")


class VersionCompareRequest(BaseModel):
    """版本对比请求 Schema"""
    version_ids: List[str] = Field(..., min_length=2, description="版本ID列表，至少2个")


# ===== 响应 Schema =====


class CollectResponse(BaseModel):
    """采集记录响应 Schema"""
    id: str = Field(..., description="采集记录ID")
    device_id: str = Field(..., description="设备ID")
    name: Optional[str] = Field(None, description="采集名称")
    start_time: datetime = Field(..., description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    interval: int = Field(..., description="采集频率（秒）")
    target_processes: Optional[List[Dict[str, Any]]] = Field(None, description="目标进程配置")
    status: str = Field(..., description="状态：running/stopped/error")
    status_display: Optional[str] = Field(None, description="状态显示名称")
    is_protected: bool = Field(default=False, description="保护标记")
    sort: int = Field(default=0, description="排序")
    is_deleted: bool = Field(default=False, description="是否删除")
    sys_create_datetime: Optional[datetime] = Field(None, description="创建时间")
    sys_update_datetime: Optional[datetime] = Field(None, description="更新时间")

    @field_serializer('start_time', 'end_time', 'sys_create_datetime', 'sys_update_datetime')
    def serialize_datetime_as_utc(self, value: Optional[datetime]) -> Optional[str]:
        """将 naive datetime 序列化为带 Z 后缀的 UTC 格式"""
        if value is None:
            return None
        # 如果是 naive datetime，视为 UTC，添加 Z 后缀
        if value.tzinfo is None:
            return value.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
        # 如果是 aware datetime，转换为 UTC 后序列化
        return value.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S') + 'Z'

    model_config = ConfigDict(from_attributes=True)


class DataResponse(BaseModel):
    """性能数据响应 Schema"""
    id: str = Field(..., description="数据ID")
    collect_id: str = Field(..., description="采集记录ID")
    timestamp: datetime = Field(..., description="实际时间")
    relative_time: int = Field(..., description="相对时间（秒）")
    cpu_usage: Optional[float] = Field(None, description="CPU使用率 %")
    gpu_usage: Optional[float] = Field(None, description="GPU使用率 %")
    commit_memory: Optional[float] = Field(None, description="提交内存 GB")
    memory_usage: Optional[float] = Field(None, description="内存使用 GB")
    power: Optional[float] = Field(None, description="功耗 W")
    cpu_speed: Optional[float] = Field(None, description="CPU速度 GHz")
    cpu_temp: Optional[float] = Field(None, description="CPU温度 °C")
    process_handles: Optional[int] = Field(None, description="进程句柄数")
    upload_speed: Optional[float] = Field(None, description="上传速度 MB/s")
    download_speed: Optional[float] = Field(None, description="下载速度 MB/s")
    target_processes: Optional[List[Dict[str, Any]]] = Field(None, description="目标进程数据")
    top10_cpu: Optional[List[Dict[str, Any]]] = Field(None, description="CPU TOP10")
    top10_gpu: Optional[List[Dict[str, Any]]] = Field(None, description="GPU TOP10")
    sort: int = Field(default=0, description="排序")
    is_deleted: bool = Field(default=False, description="是否删除")
    sys_create_datetime: Optional[datetime] = Field(None, description="创建时间")
    sys_update_datetime: Optional[datetime] = Field(None, description="更新时间")

    @field_serializer('timestamp', 'sys_create_datetime', 'sys_update_datetime')
    def serialize_datetime_as_utc(self, value: Optional[datetime]) -> Optional[str]:
        """将 naive datetime 序列化为带 Z 后缀的 UTC 格式"""
        if value is None:
            return None
        # 如果是 naive datetime，视为 UTC，添加 Z 后缀
        if value.tzinfo is None:
            return value.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
        # 如果是 aware datetime，转换为 UTC 后序列化
        return value.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S') + 'Z'

    model_config = ConfigDict(from_attributes=True)


class TagResponse(BaseModel):
    """标签响应 Schema"""
    id: str = Field(..., description="标签ID")
    collect_id: str = Field(..., description="采集记录ID")
    name: str = Field(..., description="标签名称")
    start_relative_time: int = Field(..., description="起始相对时间（秒）")
    duration: int = Field(..., description="时间长度（秒）")
    type: str = Field(..., description="类型：peak/mean")
    type_display: Optional[str] = Field(None, description="类型显示名称")
    sort: int = Field(default=0, description="排序")
    is_deleted: bool = Field(default=False, description="是否删除")
    sys_create_datetime: Optional[datetime] = Field(None, description="创建时间")
    sys_update_datetime: Optional[datetime] = Field(None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class VersionResponse(BaseModel):
    """版本响应 Schema"""
    id: str = Field(..., description="版本ID")
    device_id: str = Field(..., description="设备ID")
    name: str = Field(..., description="版本名称")
    collect_ids: List[str] = Field(..., description="包含的采集记录ID列表")
    is_protected: bool = Field(default=False, description="保护标记")
    sort: int = Field(default=0, description="排序")
    is_deleted: bool = Field(default=False, description="是否删除")
    sys_create_datetime: Optional[datetime] = Field(None, description="创建时间")
    sys_update_datetime: Optional[datetime] = Field(None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class PaginatedResponse(BaseModel):
    """分页响应 Schema"""
    items: List[Any] = Field(default_factory=list, description="数据列表")
    total: int = Field(default=0, description="总数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=20, description="每页数量")
    pages: int = Field(default=0, description="总页数")