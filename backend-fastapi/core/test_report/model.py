#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试报告模型 - Test Report Model
"""
from sqlalchemy import Column, String, Integer, Text, DateTime, Index, JSON

from app.base_model import BaseModel


class TestReportDetail(BaseModel):
    """测试报告失败明细表"""
    __tablename__ = "test_report_detail"

    task_id = Column(String(21), nullable=False, index=True, comment="任务执行ID")
    task_name = Column(String(100), nullable=False, comment="任务名称")
    total_cases = Column(Integer, nullable=False, comment="用例总数")
    case_name = Column(String(200), nullable=False, comment="用例标题")
    case_fail_step = Column(String(100), nullable=False, comment="失败步骤名称")
    case_fail_log = Column(Text, nullable=False, comment="失败日志")
    fail_reason = Column(String(500), nullable=True, comment="失败原因")
    case_round = Column(Integer, nullable=False, comment="失败轮次")
    log_url = Column(String(500), nullable=True, comment="完整日志地址")
    fail_time = Column(DateTime, nullable=True, comment="失败时间")

    __table_args__ = (
        Index('idx_task_case_round', 'task_id', 'case_name', 'case_round'),
    )


class TestReportSummary(BaseModel):
    """测试报告汇总表"""
    __tablename__ = "test_report_summary"

    task_id = Column(String(21), nullable=False, unique=True, comment="任务执行ID")
    task_name = Column(String(100), nullable=False, index=True, comment="任务名称")
    task_base_name = Column(String(100), nullable=True, index=True, comment="任务基础名称")
    total_cases = Column(Integer, nullable=False, comment="用例总数")
    fail_total = Column(Integer, nullable=False, default=0, comment="失败总数")
    pass_rate = Column(String(10), nullable=False, default="0%", comment="通过率")
    compare_change = Column(Integer, nullable=True, comment="同比变化")
    last_fail_total = Column(Integer, nullable=True, comment="上次执行失败数")
    round_stats = Column(JSON, nullable=True, comment="轮次统计")
    fail_always = Column(Integer, nullable=True, default=0, comment="每轮都失败数")
    fail_unstable = Column(Integer, nullable=True, default=0, comment="不稳定用例数")
    step_distribution = Column(JSON, nullable=True, comment="失败步骤分布")
    ai_analysis = Column(Text, nullable=True, comment="AI分析结论")
    analysis_status = Column(String(20), nullable=True, default="pending", comment="分析状态")
    execute_time = Column(DateTime, nullable=True, index=True, comment="执行时间")
    last_report_time = Column(DateTime, nullable=True, index=True, comment="最后上报时间")

    __table_args__ = (
        Index('idx_task_base_name', 'task_base_name'),
        Index('idx_last_report_time', 'last_report_time'),
    )