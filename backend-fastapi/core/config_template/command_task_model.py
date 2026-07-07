#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: Codex
@Time: 2026-07-05
@File: command_task_model.py
@Desc: CommandTask Model - 命令任务记录模型
"""
from sqlalchemy import Column, String, Text, Integer, JSON, Index, DateTime

from app.base_model import BaseModel


class CommandTask(BaseModel):
    """
    命令任务记录表

    字段说明：
    - template_id: 关联的模板ID（可选，无模板时为空）
    - template_type: 模板类型 (config/script/command)
    - template_name: 模板名称（冗余）
    - command: 命令内容（仅command类型）
    - machine_count: 目标机器数量
    - status: 任务状态 (running/success/failed/partial)
    - success_count: 成功数量
    - failed_count: 失败数量
    - result_detail: 每台机器的执行结果详情（JSON数组）
    - finished_datetime: 任务结束时间
    """
    __tablename__ = "command_task"

    # 关联模板ID
    template_id = Column(String(50), nullable=True, comment="关联模板ID")

    # 模板类型
    template_type = Column(String(20), nullable=False, comment="模板类型: config/script/command")

    # 模板名称（冗余）
    template_name = Column(String(64), nullable=False, comment="模板名称")

    # 命令内容（仅command类型）
    command = Column(Text, nullable=True, comment="命令内容")

    # 目标机器数量
    machine_count = Column(Integer, nullable=False, default=0, comment="目标机器数量")

    # 任务状态
    status = Column(String(20), nullable=False, default="running", comment="任务状态")

    # 成功数量
    success_count = Column(Integer, nullable=False, default=0, comment="成功数量")

    # 失败数量
    failed_count = Column(Integer, nullable=False, default=0, comment="失败数量")

    # 执行结果详情
    result_detail = Column(JSON, nullable=True, comment="执行结果详情")

    # 任务结束时间
    finished_datetime = Column(DateTime, nullable=True, comment="任务结束时间")

    # 索引
    __table_args__ = (
        Index("ix_command_task_template_type", "template_type"),
        Index("ix_command_task_status", "status"),
        Index("ix_command_task_create_datetime", "sys_create_datetime"),
    )
