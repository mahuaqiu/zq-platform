#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试报告 API - Test Report API
"""
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.base_schema import PaginatedResponse, ResponseModel
from core.test_report.schema import (
    FailReportCreate,
    TestReportDetailResponse,
    TestReportSummaryResponse,
    TestReportListItem,
    UploadResponse,
)
from core.test_report.service import (
    TestReportSummaryService,
    TestReportDetailQueryService,
)
from core.test_report.model import TestReportDetail, TestReportUploadLog
from core.test_report.utils import should_store_task

router = APIRouter(prefix="/test-report", tags=["测试报告"])


# ==================== 上报接口 ====================

@router.post("/fail", response_model=ResponseModel, summary="推送失败用例记录")
async def report_fail(
    data: FailReportCreate,
    db: AsyncSession = Depends(get_db)
):
    """推送失败用例记录"""
    # 检查是否应该存储（聚合配置过滤）
    if not should_store_task(data.task_project_id):
        return ResponseModel(message="上报成功")

    # 创建明细记录
    detail = TestReportDetail(
        task_project_id=data.task_project_id,
        task_name=data.task_name,
        case_name=data.case_name,
        case_fail_step=data.case_fail_step,
        case_fail_log=data.case_fail_log,
        fail_reason=data.fail_reason,
        round=data.round,
        testcase_block_id=data.testcase_block_id,
        log_url=data.log_url,
        fail_time=data.fail_time,
    )
    db.add(detail)
    await db.commit()

    return ResponseModel(message="上报成功")


@router.post("/upload", response_model=ResponseModel, summary="上传测试报告 HTML")
async def upload_html(
    taskProjectID: str = Form(..., description="任务项目ID"),
    round: int = Form(..., description="执行轮次"),
    testcaseBlockID: str = Form(..., description="用例块ID"),
    file: UploadFile = File(..., description="HTML 文件"),
    db: AsyncSession = Depends(get_db)
):
    """上传测试报告 HTML 文件"""
    # 检查是否应该存储（聚合配置过滤）
    if not should_store_task(taskProjectID):
        return ResponseModel(message="上传成功")

    # 验证 taskProjectID 格式
    if not re.match(r'^[\w\-]+$', taskProjectID):
        raise HTTPException(status_code=400, detail="taskProjectID 格式无效")

    # 验证 testcaseBlockID 格式
    if not re.match(r'^[\w\-]+$', testcaseBlockID):
        raise HTTPException(status_code=400, detail="testcaseBlockID 格式无效")

    # 验证文件扩展名
    if not file.filename or not file.filename.endswith(".html"):
        raise HTTPException(status_code=400, detail="仅支持 .html 文件")

    safe_filename = Path(file.filename).name

    # 构建存储路径
    storage_path = Path(settings.TEST_REPORT_HTML_PATH) / taskProjectID / str(round) / testcaseBlockID
    storage_path.mkdir(parents=True, exist_ok=True)

    file_path = storage_path / safe_filename
    content = await file.read()
    try:
        with open(file_path, "wb") as f:
            f.write(content)
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    # 构建完整 URL
    url = f"{settings.TEST_REPORT_EXTERNAL_BASE_URL}/test-reports-html/{taskProjectID}/{round}/{testcaseBlockID}/{safe_filename}"

    # 记录上传日志（幂等处理）
    result = await db.execute(
        select(TestReportUploadLog).where(
            TestReportUploadLog.task_project_id == taskProjectID,
            TestReportUploadLog.round == round,
            TestReportUploadLog.testcase_block_id == testcaseBlockID,
            TestReportUploadLog.is_deleted == False
        )
    )
    record = result.scalar_one_or_none()

    if record:
        record.file_url = url
        record.file_name = safe_filename
        record.upload_time = datetime.now()
    else:
        log = TestReportUploadLog(
            task_project_id=taskProjectID,
            round=round,
            testcase_block_id=testcaseBlockID,
            file_name=safe_filename,
            file_url=url,
        )
        db.add(log)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        result = await db.execute(
            select(TestReportUploadLog).where(
                TestReportUploadLog.task_project_id == taskProjectID,
                TestReportUploadLog.round == round,
                TestReportUploadLog.testcase_block_id == testcaseBlockID,
                TestReportUploadLog.is_deleted == False
            )
        )
        record = result.scalar_one_or_none()
        if record:
            record.file_url = url
            record.file_name = safe_filename
            record.upload_time = datetime.now()
            await db.commit()

    return ResponseModel(message="上传成功", data={"url": url})


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
            TestReportDetail.task_project_id == task_id,
            TestReportDetail.case_name == case_name,
            TestReportDetail.is_deleted == False
        ).order_by(TestReportDetail.round.desc()).limit(1)
    )
    detail = result.scalar_one_or_none()

    if not detail:
        raise HTTPException(status_code=404, detail="用例记录不存在")

    return ResponseModel(data={"logUrl": detail.log_url})