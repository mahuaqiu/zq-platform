#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试报告 Schema - Test Report Schema
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


# ==================== 明细相关 ====================

class FailReportCreate(BaseModel):
    """失败记录上报请求"""
    task_id: str = Field(..., alias="taskId", description="任务执行ID")
    task_name: str = Field(..., alias="taskName", description="任务名称")
    total_cases: int = Field(..., alias="totalCases", description="用例总数")
    case_name: str = Field(..., alias="caseName", description="用例标题")
    case_fail_step: str = Field(..., alias="caseFailStep", description="失败步骤")
    case_fail_log: str = Field(..., alias="caseFailLog", description="失败日志")
    case_round: int = Field(..., alias="caseRound", description="失败轮次")
    log_url: Optional[str] = Field(None, alias="logUrl", description="日志HTML文件路径")
    fail_time: Optional[datetime] = Field(None, alias="failTime", description="失败时间")

    class Config:
        populate_by_name = True


class TestReportDetailResponse(BaseModel):
    """明细响应"""
    id: str
    task_id: str = Field(..., alias="taskId")
    task_name: str = Field(..., alias="taskName")
    case_name: str = Field(..., alias="caseName")
    case_fail_step: str = Field(..., alias="caseFailStep")
    case_fail_log: str = Field(..., alias="caseFailLog")
    case_round: int = Field(..., alias="caseRound")
    log_url: Optional[str] = Field(None, alias="logUrl")
    fail_time: Optional[datetime] = Field(None, alias="failTime")
    sys_create_datetime: datetime = Field(..., alias="createTime")

    class Config:
        populate_by_name = True
        from_attributes = True


# ==================== 汇总相关 ====================

class RoundStatItem(BaseModel):
    """轮次统计项"""
    round: int
    fail_count: int


class StepDistributionItem(BaseModel):
    """失败步骤分布项"""
    step: str
    count: int


class TestReportSummaryResponse(BaseModel):
    """汇总响应"""
    id: str
    task_id: str = Field(..., alias="taskId")
    task_name: str = Field(..., alias="taskName")
    total_cases: int = Field(..., alias="totalCases")
    fail_total: int = Field(..., alias="failTotal")
    pass_rate: str = Field(..., alias="passRate")
    compare_change: Optional[int] = Field(None, alias="compareChange")
    last_fail_total: Optional[int] = Field(None, alias="lastFailTotal")
    round_stats: Optional[List[RoundStatItem]] = Field(None, alias="roundStats")
    fail_always: Optional[int] = Field(None, alias="failAlways")
    fail_unstable: Optional[int] = Field(None, alias="failUnstable")
    step_distribution: Optional[List[StepDistributionItem]] = Field(None, alias="stepDistribution")
    ai_analysis: Optional[str] = Field(None, alias="aiAnalysis")
    analysis_status: Optional[str] = Field(None, alias="analysisStatus")
    execute_time: Optional[datetime] = Field(None, alias="executeTime")

    class Config:
        populate_by_name = True
        from_attributes = True


class TestReportListItem(BaseModel):
    """列表项响应"""
    id: str
    task_id: str = Field(..., alias="taskId")
    task_name: str = Field(..., alias="taskName")
    execute_time: Optional[datetime] = Field(None, alias="executeTime")
    total_cases: int = Field(..., alias="totalCases")
    fail_total: int = Field(..., alias="failTotal")
    pass_rate: str = Field(..., alias="passRate")
    compare_change: Optional[int] = Field(None, alias="compareChange")

    class Config:
        populate_by_name = True
        from_attributes = True