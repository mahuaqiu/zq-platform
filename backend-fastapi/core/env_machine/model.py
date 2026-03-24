#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2025-03-25
@File: model.py
@Desc: EnvMachine Model - 执行机模型 - 用于管理自动化测试执行机
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Boolean, Text, DateTime, JSON, UniqueConstraint, Index

from app.base_model import BaseModel


class EnvMachine(BaseModel):
    """
    执行机表

    字段说明：
    - namespace: 机器分类
    - ip: 机器 IP（支持 IPv6）
    - port: 机器端口
    - mark: 机器标签，多个用逗号分隔
    - device_type: 机器类型：windows/mac/android/ios
    - device_sn: 设备 SN（移动端必填）
    - available: 是否启用
    - status: 状态：online/using/offline
    - note: 备注
    - sync_time: 同步时间
    - extra_message: 扩展信息，按标签存储
    - version: 机器版本
    - last_keepusing_time: 最后保持使用时间
    """
    __tablename__ = "env_machine"

    # 机器分类
    namespace = Column(String(64), nullable=False, comment="机器分类")

    # 机器 IP（支持 IPv6）
    ip = Column(String(45), nullable=False, comment="机器 IP")

    # 机器端口
    port = Column(String(10), nullable=False, comment="机器端口")

    # 机器标签，多个用逗号分隔
    mark = Column(String(255), nullable=True, comment="机器标签")

    # 机器类型：windows/mac/android/ios
    device_type = Column(String(20), nullable=False, comment="机器类型")

    # 设备 SN（移动端必填）
    device_sn = Column(String(64), nullable=True, comment="设备 SN")

    # 是否启用
    available = Column(Boolean, nullable=False, default=False, comment="是否启用")

    # 状态：online/using/offline
    status = Column(String(20), nullable=False, default="online", comment="状态")

    # 备注
    note = Column(Text, nullable=True, comment="备注")

    # 同步时间
    sync_time = Column(DateTime, nullable=False, default=datetime.now, comment="同步时间")

    # 扩展信息，按标签存储
    extra_message = Column(JSON, nullable=True, comment="扩展信息")

    # 机器版本
    version = Column(String(32), nullable=True, comment="机器版本")

    # 最后保持使用时间
    last_keepusing_time = Column(DateTime, nullable=True, comment="最后保持使用时间")

    # 复合唯一索引和普通索引
    __table_args__ = (
        UniqueConstraint("namespace", "ip", "device_type", "device_sn", name="uq_env_machine_namespace_ip_device"),
        Index("ix_env_machine_status", "status"),
        Index("ix_env_machine_sync_time", "sync_time"),
    )

    # 状态显示名称映射
    STATUS_DISPLAY = {
        "online": "在线",
        "using": "使用中",
        "offline": "离线",
    }

    def get_status_display(self) -> str:
        """返回状态的中文显示名称"""
        return self.STATUS_DISPLAY.get(self.status, self.status)

    def to_cache_dict(self) -> dict:
        """转换为缓存字典格式"""
        return {
            "id": self.id,
            "namespace": self.namespace,
            "ip": self.ip,
            "port": self.port,
            "mark": self.mark,
            "device_type": self.device_type,
            "device_sn": self.device_sn,
            "available": self.available,
            "status": self.status,
            "note": self.note,
            "sync_time": self.sync_time.isoformat() if self.sync_time else None,
            "extra_message": self.extra_message,
            "version": self.version,
            "last_keepusing_time": self.last_keepusing_time.isoformat() if self.last_keepusing_time else None,
        }

    def __str__(self):
        return f"{self.namespace}/{self.ip}:{self.port} ({self.device_type})"