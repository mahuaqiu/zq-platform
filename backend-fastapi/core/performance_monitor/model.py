#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控数据模型
"""
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, JSON, ForeignKey

from app.base_model import BaseModel


class PerformanceCollect(BaseModel):
    """
    采集记录表

    字段说明：
    - device_id: 设备ID（关联 env_machine）
    - name: 采集名称（可选）
    - start_time: 开始时间
    - end_time: 结束时间（停止后填充）
    - interval: 采集频率（秒）
    - target_processes: 目标进程配置
    - status: 状态：running/stopped/error
    - is_protected: 保护标记（不被自动清理）
    """
    __tablename__ = "performance_collect"

    # 设备ID（关联 env_machine）
    device_id = Column(String(21), nullable=False, index=True, comment="设备ID")

    # 采集名称（可选）
    name = Column(String(100), nullable=True, comment="采集名称")

    # 开始时间
    start_time = Column(DateTime, nullable=False, comment="开始时间")

    # 结束时间（停止后填充）
    end_time = Column(DateTime, nullable=True, comment="结束时间")

    # 采集频率（秒）
    interval = Column(Integer, nullable=False, default=5, comment="采集频率（秒）")

    # 目标进程配置
    target_processes = Column(JSON, nullable=True, comment="目标进程配置")

    # 状态：pending/starting/running/stopping/stopped/failed/timed_out/interrupted
    status = Column(String(20), nullable=False, default="pending", index=True, comment="采集状态")
    last_heartbeat_at = Column(DateTime, nullable=True, comment="Worker 最后心跳时间")
    last_sequence = Column(Integer, nullable=True, comment="Worker 最后采样序号")
    last_elapsed_ms = Column(Integer, nullable=True, comment="Worker 最后样本相对时间（毫秒）")
    failure_code = Column(String(80), nullable=True, comment="失败错误码")
    failure_message = Column(String(500), nullable=True, comment="失败消息")
    end_reason = Column(String(40), nullable=True, comment="结束原因")

    # 保护标记（不被自动清理）
    is_protected = Column(Boolean, nullable=False, default=False, comment="保护标记")

    # 状态显示名称映射
    STATUS_DISPLAY = {
        "pending": "等待启动",
        "starting": "启动中",
        "running": "运行中",
        "stopping": "停止中",
        "stopped": "已停止",
        "failed": "启动失败",
        "timed_out": "已超时",
        "interrupted": "已中断",
        "error": "异常",
    }

    def get_status_display(self) -> str:
        """返回状态的中文显示名称"""
        return self.STATUS_DISPLAY.get(self.status, "") or self.status or ""


class PerformanceData(BaseModel):
    """
    性能数据表

    字段说明：
    - collect_id: 采集记录ID（关联 performance_collect）
    - timestamp: 实际时间
    - relative_time: 相对时间（秒，从采集开始算）
    - cpu_usage: CPU使用率 %
    - gpu_usage: GPU使用率 %
    - commit_memory: 提交内存 GB
    - memory_usage: 内存使用 GB
    - process_handles: 进程句柄数
    - target_processes: 目标进程数据（含实例明细）
    - top10_cpu: CPU TOP10
    - top10_gpu: GPU TOP10
    - hwinfo_raw: HWiNFO原始传感器数据（完整）
    """
    __tablename__ = "performance_data"

    # 采集记录ID（关联 performance_collect）
    collect_id = Column(String(21), ForeignKey("performance_collect.id"), nullable=False, index=True, comment="采集记录ID")
    sample_key = Column(String(128), nullable=False, unique=True, index=True, comment="采样幂等键")
    sequence = Column(Integer, nullable=False, comment="采样序号")
    elapsed_ms = Column(Integer, nullable=False, comment="相对采集开始时间，毫秒")
    # 实际时间
    timestamp = Column(DateTime, nullable=False, comment="实际时间")

    # 相对时间（秒，从采集开始算）
    relative_time = Column(Integer, nullable=False, comment="相对时间（秒）")

    # ===== 系统指标 =====

    # CPU使用率 %
    cpu_usage = Column(Float, nullable=True, comment="CPU使用率 %")

    # GPU使用率 %
    gpu_usage = Column(Float, nullable=True, comment="GPU使用率 %")

    # 提交内存 GB
    commit_memory = Column(Float, nullable=True, comment="提交内存 GB")

    # 内存使用 GB
    memory_usage = Column(Float, nullable=True, comment="内存使用 GB")

    # 进程句柄数
    process_handles = Column(Integer, nullable=True, comment="进程句柄数")

    # ===== 进程数据 =====

    # 目标进程数据（含实例明细）
    target_processes = Column(JSON, nullable=True, comment="目标进程数据")

    # CPU TOP10
    top10_cpu = Column(JSON, nullable=True, comment="CPU TOP10")

    # GPU TOP10
    top10_gpu = Column(JSON, nullable=True, comment="GPU TOP10")

    # HWiNFO原始传感器数据（完整）
    hwinfo_raw = Column(JSON, nullable=True, comment="HWiNFO原始传感器数据（完整）")
    system_metrics = Column(JSON, nullable=True, comment="Rust 系统 CPU/GPU 指标")


class PerformanceTag(BaseModel):
    """
    标签表

    字段说明：
    - collect_id: 采集记录ID（关联 performance_collect）
    - name: 标签名称（如"发起共享"、"场景加载"）
    - start_relative_time: 起始相对时间（秒）
    - duration: 时间长度（秒）
    - type: 类型：peak/mean（峰值区间/均值区间）
    """
    __tablename__ = "performance_tag"

    # 采集记录ID（关联 performance_collect）
    collect_id = Column(String(21), ForeignKey("performance_collect.id"), nullable=False, index=True, comment="采集记录ID")

    # 标签名称
    name = Column(String(50), nullable=False, comment="标签名称")

    # 起始相对时间（秒）
    start_relative_time = Column(Integer, nullable=False, comment="起始相对时间（秒）")

    # 时间长度（秒）
    duration = Column(Integer, nullable=False, comment="时间长度（秒）")

    # 类型：peak/mean
    type = Column(String(20), nullable=False, default="peak", comment="类型：peak/mean")

    # 类型显示名称映射
    TYPE_DISPLAY = {
        "peak": "峰值区间",
        "mean": "均值区间",
    }

    def get_type_display(self) -> str:
        """返回类型的中文显示名称"""
        return self.TYPE_DISPLAY.get(self.type, "") or self.type or ""


class PerformanceVersion(BaseModel):
    """
    版本对比表

    字段说明：
    - device_id: 设备ID
    - name: 版本名称
    - collect_ids: 包含的采集记录ID列表
    - time_ranges: 时间范围映射 {collect_id: {start, end}}
    - is_protected: 保护标记
    """
    __tablename__ = "performance_version"

    # 设备ID
    device_id = Column(String(21), nullable=False, index=True, comment="设备ID")

    # 版本名称
    name = Column(String(100), nullable=False, comment="版本名称")

    # 包含的采集记录ID列表
    collect_ids = Column(JSON, nullable=False, comment="包含的采集记录ID列表")

    # 时间范围映射: {collect_id: {start: 相对秒数, end: 相对秒数}}
    time_ranges = Column(JSON, nullable=True, comment="时间范围映射")

    # 保护标记
    is_protected = Column(Boolean, nullable=False, default=False, comment="保护标记")


class PerformanceMetricMapping(BaseModel):
    """
    指标映射配置表

    字段说明：
    - hwinfo_key: HWiNFO传感器键名
    - display_name: 中文显示名称
    - category: 指标分类
    - is_primary: 是否常用指标
    - unit: 单位
    """
    __tablename__ = "performance_metric_mapping"

    # hwinfo传感器原始名称
    hwinfo_key = Column(String(100), nullable=False, unique=True, index=True, comment="HWiNFO传感器键名")

    # 中文显示名称
    display_name = Column(String(100), nullable=False, comment="中文显示名称")

    # 指标分类
    category = Column(String(20), nullable=False, default="system", comment="指标分类")

    # 是否常用指标
    is_primary = Column(Boolean, nullable=False, default=False, comment="是否常用指标")

    # 单位
    unit = Column(String(20), nullable=True, comment="单位")

    # 排序
    sort = Column(Integer, nullable=False, default=0, comment="排序")


class PerformanceMarker(BaseModel):
    """
    标记数据表（v0.3.0新增）

    字段说明：
    - collect_id: 采集记录ID
    - name: 标记名称
    - start_time: 开始时间（相对时间，秒）
    - end_time: 结束时间（相对时间，秒，可选）
    - color: 标记颜色
    - note: 备注信息
    """
    __tablename__ = "performance_marker"

    # 采集记录ID
    collect_id = Column(String(21), ForeignKey("performance_collect.id"), nullable=False, index=True, comment="采集记录ID")

    # 标记名称
    name = Column(String(50), nullable=False, comment="标记名称")

    # 开始时间（相对时间，秒）
    start_time = Column(Integer, nullable=False, comment="开始时间")

    # 结束时间（相对时间，秒，可选）
    end_time = Column(Integer, nullable=True, comment="结束时间")

    # 标记颜色
    color = Column(String(10), nullable=False, default="#409eff", comment="标记颜色")

    # 备注
    note = Column(String(200), nullable=True, comment="备注信息")


# 导入对比标签模型
from core.performance_monitor.compare_model import CompareTag


class ExportTask(BaseModel):
    """
    导出任务表

    字段说明：
    - task_type: 任务类型（compare_export）
    - params: 任务参数 JSONB（version_ids, metric, hwinfo_key）
    - status: 状态（pending/processing/completed/failed）
    - progress: 进度（0-100）
    - message: 进度消息或错误信息
    - file_path: 生成的文件路径
    - completed_at: 完成时间
    """
    __tablename__ = "export_task"

    # 任务类型
    task_type = Column(String(50), nullable=False, index=True, comment="任务类型")

    # 任务参数 JSONB
    params = Column(JSON, nullable=False, comment="任务参数")

    # 状态
    status = Column(String(20), nullable=False, default="pending", index=True, comment="状态")

    # 进度
    progress = Column(Integer, nullable=False, default=0, comment="进度（0-100）")

    # 进度消息
    message = Column(String(500), nullable=True, comment="进度消息")

    # 文件路径
    file_path = Column(String(500), nullable=True, comment="文件路径")

    # 完成时间
    completed_at = Column(DateTime, nullable=True, comment="完成时间")

    # 状态显示映射
    STATUS_DISPLAY = {
        "pending": "等待中",
        "processing": "处理中",
        "completed": "已完成",
        "failed": "失败",
    }

    def get_status_display(self) -> str:
        return self.STATUS_DISPLAY.get(self.status, "") or self.status or ""