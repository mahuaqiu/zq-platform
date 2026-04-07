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
    task_project_id: str = Field(..., alias="taskProjectID", description="任务项目ID")
    task_name: str = Field(..., alias="taskName", description="任务名称")
    case_name: str = Field(..., alias="caseName", description="用例标题")
    case_fail_step: str = Field(..., alias="caseFailStep", description="失败步骤")
    case_fail_log: str = Field(..., alias="caseFailLog", description="失败日志")
    fail_reason: Optional[str] = Field(None, alias="failReason", description="失败原因")
    round: int = Field(..., alias="round", description="执行轮次")
    testcase_block_id: Optional[str] = Field(None, alias="testcaseBlockID", description="用例块ID")
    log_url: Optional[str] = Field(None, alias="logUrl", description="日志HTML文件路径")
    fail_time: Optional[datetime] = Field(None, alias="failTime", description="失败时间")

    class Config:
        populate_by_name = True


class TestReportDetailResponse(BaseModel):
    """明细响应"""
    id: str
    task_project_id: str = Field(..., alias="taskProjectID")
    task_name: str = Field(..., alias="taskName")
    case_name: str = Field(..., alias="caseName")
    case_fail_step: str = Field(..., alias="caseFailStep")
    case_fail_log: str = Field(..., alias="caseFailLog")
    fail_reason: Optional[str] = Field(None, alias="failReason")
    round: int = Field(..., alias="round")
    testcase_block_id: Optional[str] = Field(None, alias="testcaseBlockID")
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
    task_project_id: str = Field(..., alias="taskProjectID")
    task_name: str = Field(..., alias="taskName")
    total_cases: int = Field(..., alias="totalCases")
    execute_total: int = Field(..., alias="executeTotal")
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
    task_project_id: str = Field(..., alias="taskProjectID")
    task_name: str = Field(..., alias="taskName")
    execute_time: Optional[datetime] = Field(None, alias="executeTime")
    total_cases: int = Field(..., alias="totalCases")
    execute_total: int = Field(..., alias="executeTotal")
    fail_total: int = Field(..., alias="failTotal")
    pass_rate: str = Field(..., alias="passRate")
    compare_change: Optional[int] = Field(None, alias="compareChange")

    class Config:
        populate_by_name = True
        from_attributes = True


class AggregatedReportSummaryResponse(BaseModel):
    """聚合后的报告汇总响应"""
    id: str
    taskProjectID: str
    taskName: str
    totalCases: int
    executeTotal: int
    failTotal: int
    passRate: str
    compareChange: int = 0
    roundStats: Optional[List[RoundStatItem]] = None
    failAlways: int = 0
    failUnstable: int = 0
    stepDistribution: Optional[List[StepDistributionItem]] = None
    executeTime: Optional[datetime] = None

    class Config:
        populate_by_name = True


# ==================== 上传相关 ====================

class UploadResponse(BaseModel):
    """上传响应"""
    url: str = Field(..., description="HTML 文件访问 URL")