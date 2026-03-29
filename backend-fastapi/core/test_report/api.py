#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试报告 API - Test Report API
"""
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.base_schema import PaginatedResponse, ResponseModel
from core.test_report.schema import (
    FailReportCreate,
    TestReportDetailResponse,
    TestReportSummaryResponse,
    TestReportListItem,
)
from core.test_report.service import (
    TestReportDetailService,
    TestReportSummaryService,
    TestReportDetailQueryService,
)
from core.test_report.model import TestReportDetail

router = APIRouter(prefix="/test-report", tags=["测试报告"])


# ==================== Token 认证（上报接口专用） ====================

async def verify_api_token(authorization: Optional[str] = Header(None)):
    """验证 API Token"""
    if not settings.TEST_REPORT_API_TOKEN:
        # 未配置 Token 时允许所有请求（开发模式）
        return True

    if not authorization:
        raise HTTPException(status_code=401, detail="缺少 Authorization 头")

    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization

    if token != settings.TEST_REPORT_API_TOKEN:
        raise HTTPException(status_code=401, detail="Token 无效")

    return True


# ==================== 上报接口 ====================

@router.post("/fail", response_model=ResponseModel, summary="推送失败用例记录")
async def report_fail(
    data: FailReportCreate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_api_token)
):
    """推送失败用例记录（使用独立 Token 认证）"""
    # 创建明细记录
    detail = TestReportDetail(
        task_id=data.task_id,
        task_name=data.task_name,
        total_cases=data.total_cases,
        case_name=data.case_name,
        case_fail_step=data.case_fail_step,
        case_fail_log=data.case_fail_log,
        case_round=data.case_round,
        log_url=data.log_url,
        fail_time=data.fail_time,
    )
    db.add(detail)
    await db.commit()

    return ResponseModel(message="上报成功")


# ==================== 查询接口 ====================

@router.get("", response_model=PaginatedResponse[TestReportListItem], summary="获取报告列表")
async def get_report_list(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize", description="每页数量"),
    task_name: Optional[str] = Query(None, alias="taskName", description="任务名称筛选"),
    db: AsyncSession = Depends(get_db)
):
    """获取报告列表（支持任务名称筛选、分页）"""
    items, total = await TestReportSummaryService.get_list_with_filter(
        db, page=page, page_size=page_size, task_name=task_name
    )

    response_items = [TestReportListItem.model_validate(item) for item in items]
    return PaginatedResponse(items=response_items, total=total)


@router.get("/summary/{task_id}", response_model=TestReportSummaryResponse, summary="获取报告汇总")
async def get_report_summary(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取单个报告汇总"""
    summary = await TestReportSummaryService.get_by_task_id(db, task_id)
    if not summary:
        raise HTTPException(status_code=404, detail="报告不存在")

    return TestReportSummaryResponse.model_validate(summary)


@router.get("/detail/{task_id}", response_model=PaginatedResponse[TestReportDetailResponse], summary="获取报告明细")
async def get_report_detail(
    task_id: str,
    category: str = Query(default="all", description="分类筛选: all/final_fail/always_fail/unstable"),
    db: AsyncSession = Depends(get_db)
):
    """获取报告明细列表"""
    # 先检查汇总是否存在
    summary = await TestReportSummaryService.get_by_task_id(db, task_id)
    if not summary:
        raise HTTPException(status_code=404, detail="报告不存在")

    details = await TestReportDetailQueryService.get_details_by_category(
        db, task_id, category
    )

    response_items = [TestReportDetailResponse.model_validate(d) for d in details]
    return PaginatedResponse(items=response_items, total=len(response_items))


@router.get("/log/{task_id}/{case_name}", response_model=ResponseModel, summary="获取用例完整日志")
async def get_case_log(
    task_id: str,
    case_name: str,
    db: AsyncSession = Depends(get_db)
):
    """获取用例完整日志地址"""
    from sqlalchemy import select

    result = await db.execute(
        select(TestReportDetail).where(
            TestReportDetail.task_id == task_id,
            TestReportDetail.case_name == case_name,
            TestReportDetail.is_deleted == False
        ).order_by(TestReportDetail.case_round.desc()).limit(1)
    )
    detail = result.scalar_one_or_none()

    if not detail:
        raise HTTPException(status_code=404, detail="用例记录不存在")

    return ResponseModel(data={"logUrl": detail.log_url})