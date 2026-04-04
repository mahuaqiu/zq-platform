#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: Claude
@Time: 2026-04-04
@File: log_model.py
@Desc: 执行机申请日志模型
"""
from sqlalchemy import Column, String, Integer, DateTime, Index

from app.base_model import BaseModel


class EnvMachineLog(BaseModel):
    """
    执行机申请日志表

    记录每次申请/释放操作的详细信息
    """
    __tablename__ = "env_machine_log"

    # 机器分类
    namespace = Column(String(64), nullable=False, comment="机器分类")

    # 机器ID
    machine_id = Column(String(36), nullable=False, comment="机器ID")

    # 机器IP
    ip = Column(String(45), nullable=True, comment="机器IP")

    # 机器类型：windows/mac/android/ios
    device_type = Column(String(20), nullable=False, comment="机器类型")

    # 设备SN（移动端）
    device_sn = Column(String(64), nullable=True, comment="设备SN")

    # 申请的标签
    mark = Column(String(255), nullable=True, comment="申请的标签")

    # 机器来源池（新增）
    source_pool = Column(String(64), nullable=True, comment="机器来源池")

    # 操作类型：apply/release
    action = Column(String(20), nullable=False, comment="操作类型: apply/release")

    # 结果：success/fail
    result = Column(String(20), nullable=False, comment="结果: success/fail")

    # 失败原因
    fail_reason = Column(String(255), nullable=True, comment="失败原因")

    # 申请时间
    apply_time = Column(DateTime, nullable=True, comment="申请时间")

    # 释放时间
    release_time = Column(DateTime, nullable=True, comment="释放时间")

    # 占用时长（分钟）
    duration_minutes = Column(Integer, nullable=True, comment="占用时长（分钟）")

    # 复合索引
    __table_args__ = (
        Index('ix_env_machine_log_create_time', 'sys_create_datetime'),
        Index('ix_env_machine_log_namespace_time', 'namespace', 'sys_create_datetime'),
        Index('ix_env_machine_log_machine_id', 'machine_id'),
    )

    def __str__(self):
        source = self.source_pool or "N/A"
        return f"{self.namespace}/{self.ip or self.device_sn} - {self.action} - {self.result} - from:{source}"