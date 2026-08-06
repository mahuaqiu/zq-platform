#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: Codex
@Time: 2026-07-05
@File: machine_selection_template_model.py
@Desc: MachineSelectionTemplate Model - 机器选择模板模型
"""
from sqlalchemy import Column, String, Text, Index, JSON, text

from app.base_model import BaseModel


class MachineSelectionTemplate(BaseModel):
    """
    机器选择模板表（IP模板）

    字段说明：
    - name: 模板名称（唯一）
    - namespace: 命名空间筛选（可选）
    - device_type: 设备类型筛选（可选）
    - ip_pattern: IP模糊匹配（可选）
    - machine_ids: 固定机器ID列表（二选一，与筛选条件互斥）
    - note: 备注说明
    - version: 版本号（YYYYMMDD-HHMMSS）
    """
    __tablename__ = "machine_selection_template"

    # 模板名称（唯一）
    name = Column(String(64), nullable=False, comment="模板名称")

    # 命名空间筛选
    namespace = Column(String(64), nullable=True, comment="命名空间筛选")

    # 设备类型筛选
    device_type = Column(String(20), nullable=True, comment="设备类型筛选")

    # IP模糊匹配
    ip_pattern = Column(String(64), nullable=True, comment="IP模糊匹配")

    # 固定机器ID列表
    machine_ids = Column(JSON, nullable=True, comment="固定机器ID列表")

    # 固定机器目标快照，以 IP + 设备类型解析当前机器，不依赖易变化的机器 ID
    machine_targets = Column(JSON, nullable=True, comment="机器目标快照")

    # 备注说明
    note = Column(Text, nullable=True, comment="备注说明")

    # 版本号
    version = Column(String(20), nullable=False, comment="版本号")

    # 索引
    __table_args__ = (
        Index(
            "uq_machine_selection_template_active_name",
            "name",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        Index("ix_machine_selection_template_namespace", "namespace"),
    )
