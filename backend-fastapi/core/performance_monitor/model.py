#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控数据模型
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, JSON, ForeignKey, Index

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

    # 状态：running/stopped/error
    status = Column(String(20), nullable=False, default="running", index=True, comment="状态：running/stopped/error")

    # 保护标记（不被自动清理）
    is_protected = Column(Boolean, nullable=False, default=False, comment="保护标记")

    # 状态显示名称映射
    STATUS_DISPLAY = {
        "running": "运行中",
        "stopped": "已停止",
        "error": "异常",
    }

    def get_status_display(self) -> str:
        """返回状态的中文显示名称"""
        return self.STATUS_DISPLAY.get(self.status, self.status)


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
    - power: 功耗 W
    - cpu_speed: CPU速度 GHz
    - cpu_temp: CPU温度 °C
    - process_handles: 进程句柄数
    - upload_speed: 上传速度 MB/s
    - download_speed: 下载速度 MB/s
    - target_processes: 目标进程数据（含实例明细）
    - top10_cpu: CPU TOP10
    - top10_gpu: GPU TOP10
    """
    __tablename__ = "performance_data"

    # 采集记录ID（关联 performance_collect）
    collect_id = Column(String(21), ForeignKey("performance_collect.id"), nullable=False, index=True, comment="采集记录ID")

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

    # 功耗 W
    power = Column(Float, nullable=True, comment="功耗 W")

    # CPU速度 GHz
    cpu_speed = Column(Float, nullable=True, comment="CPU速度 GHz")

    # CPU温度 °C
    cpu_temp = Column(Float, nullable=True, comment="CPU温度 °C")

    # 进程句柄数
    process_handles = Column(Integer, nullable=True, comment="进程句柄数")

    # 上传速度 MB/s
    upload_speed = Column(Float, nullable=True, comment="上传速度 MB/s")

    # 下载速度 MB/s
    download_speed = Column(Float, nullable=True, comment="下载速度 MB/s")

    # ===== 进程数据 =====

    # 目标进程数据（含实例明细）
    target_processes = Column(JSON, nullable=True, comment="目标进程数据")

    # CPU TOP10
    top10_cpu = Column(JSON, nullable=True, comment="CPU TOP10")

    # GPU TOP10
    top10_gpu = Column(JSON, nullable=True, comment="GPU TOP10")


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
        return self.TYPE_DISPLAY.get(self.type, self.type)


class PerformanceVersion(BaseModel):
    """
    版本对比表

    字段说明：
    - device_id: 设备ID
    - name: 版本名称
    - collect_ids: 包含的采集记录ID列表
    - is_protected: 保护标记
    """
    __tablename__ = "performance_version"

    # 设备ID
    device_id = Column(String(21), nullable=False, index=True, comment="设备ID")

    # 版本名称
    name = Column(String(100), nullable=False, comment="版本名称")

    # 包含的采集记录ID列表
    collect_ids = Column(JSON, nullable=False, comment="包含的采集记录ID列表")

    # 保护标记
    is_protected = Column(Boolean, nullable=False, default=False, comment="保护标记")