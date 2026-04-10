#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time: 2026-04-10
@File: upgrade_model.py
@Desc: Worker 升级管理模型
"""
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Index

from app.base_model import BaseModel


class WorkerUpgradeConfig(BaseModel):
    """Worker 升级配置表 - 存储 Windows/Mac 最新版本信息"""
    __tablename__ = "worker_upgrade_config"

    device_type = Column(String(20), nullable=False, unique=True, comment="设备类型: windows/mac")
    version = Column(String(32), nullable=False, comment="目标版本号(时间戳格式)")
    download_url = Column(String(512), nullable=False, comment="安装包下载地址")
    note = Column(Text, nullable=True, comment="备注")


class WorkerUpgradeQueue(BaseModel):
    """Worker 升级队列 - 记录等待升级的机器"""
    __tablename__ = "worker_upgrade_queue"

    machine_id = Column(String(36), nullable=False, index=True, comment="机器ID")
    target_version = Column(String(32), nullable=False, comment="目标版本号")
    status = Column(String(20), nullable=False, default="waiting", comment="状态: waiting/completed/failed")
    device_type = Column(String(20), nullable=False, comment="设备类型")
    namespace = Column(String(64), nullable=False, comment="机器分类")
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment="入队时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")

    __table_args__ = (
        Index("ix_upgrade_queue_status", "status"),
    )