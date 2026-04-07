#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试报告 API - Test Report API
"""
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, Form
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.base_schema import PaginatedResponse, ResponseModel
from utils.logging_config import get_logger

logger = get_logger("api.test_report")
from core.test_report.schema import (
    FailReportCreate,
    TestReportDetailResponse,
    TestReportSummaryResponse,
    TestReportListItem,
    UploadResponse,
    AggregatedReportSummaryResponse,
)
from core.test_report.service import (
    TestReportSummaryService,
    TestReportDetailQueryService,
)
from core.test_report.model import TestReportDetail, TestReportUploadLog, TestReportSummary
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

@router.get("", response_model=PaginatedResponse, summary="获取报告列表")
async def get_report_list(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize", description="每页数量"),
    task_name: Optional[str] = Query(None, alias="taskName", description="任务名称筛选"),
    db: AsyncSession = Depends(get_db)
):
    """获取报告列表（支持任务名称筛选、分页、聚合显示）"""
    aggregation_map = settings.task_aggregation_map

    if aggregation_map:
        # 使用聚合列表
        items, total = await TestReportSummaryService.get_aggregated_list(
            db, page=page, page_size=page_size, task_name=task_name
        )
        response_items = [
            AggregatedReportSummaryResponse(
                id=item.id,
                taskProjectID=item.aggregated_name,
                taskName=item.task_name,
                totalCases=item.total_cases,
                executeTotal=item.execute_total,
                failTotal=item.fail_total,
                passRate=item.pass_rate,
                compareChange=item.compare_change,
                roundStats=item.round_stats,
                failAlways=item.fail_always,
                failUnstable=item.fail_unstable,
                stepDistribution=item.step_distribution,
                executeTime=item.execute_time,
            )
            for item in items
        ]
    else:
        # 无聚合配置，使用原始列表
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
    """获取单个报告汇总（支持聚合名或 task_project_id）"""
    summary = await TestReportSummaryService.get_aggregated_summary(db, task_id)
    if not summary:
        raise HTTPException(status_code=404, detail="报告不存在")

    # 判断是否为聚合结果
    aggregation_map = settings.task_aggregation_map
    if task_id in aggregation_map:
        # 聚合结果，返回聚合响应
        return TestReportSummaryResponse(
            id=summary.aggregated_name,
            task_project_id=summary.aggregated_name,
            task_name=summary.task_name,
            total_cases=summary.total_cases,
            execute_total=summary.execute_total,
            fail_total=summary.fail_total,
            pass_rate=summary.pass_rate,
            compare_change=summary.compare_change,
            last_fail_total=None,
            round_stats=summary.round_stats,
            fail_always=summary.fail_always,
            fail_unstable=summary.fail_unstable,
            step_distribution=summary.step_distribution,
            ai_analysis=None,
            analysis_status=None,
            execute_time=summary.execute_time,
        )

    return TestReportSummaryResponse.model_validate(summary)


@router.get("/detail/{task_id}", response_model=PaginatedResponse[TestReportDetailResponse], summary="获取报告明细")
async def get_report_detail(
    task_id: str,
    category: str = Query(default="all", description="分类筛选: all/final_fail/always_fail/unstable"),
    db: AsyncSession = Depends(get_db)
):
    """获取报告明细列表（支持聚合名或 task_project_id）"""
    aggregation_map = settings.task_aggregation_map

    # 获取 task_project_ids 列表
    if task_id in aggregation_map:
        task_project_ids = aggregation_map[task_id]
    else:
        # 非聚合名，检查汇总是否存在
        summary = await TestReportSummaryService.get_by_task_id(db, task_id)
        if not summary:
            raise HTTPException(status_code=404, detail="报告不存在")
        task_project_ids = [task_id]

    details = await TestReportDetailQueryService.get_details_by_category(
        db, task_project_ids, category
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


# ==================== 删除接口 ====================

@router.delete("/{summary_id}", response_model=ResponseModel, summary="删除报告")
async def delete_report(
    summary_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除报告（软删除数据 + 清理HTML文件）"""
    # 获取 Summary
    summary = await db.get(TestReportSummary, summary_id)
    if not summary or summary.is_deleted:
        raise HTTPException(status_code=404, detail="报告不存在")

    # 获取子任务列表
    task_project_ids = summary.task_project_ids or [summary.task_project_id]

    # 验证 task_project_ids 不为空
    if not task_project_ids:
        raise HTTPException(status_code=400, detail="任务ID列表为空，无法删除")

    try:
        # 第一步：软删除所有数据库记录（不进行文件操作）
        for task_project_id in task_project_ids:
            if not task_project_id:
                logger.warning(f"跳过空的 task_project_id: summary_id={summary_id}")
                continue

            # 删除 Detail（仅删除未软删除的记录）
            await db.execute(
                update(TestReportDetail)
                .where(
                    TestReportDetail.task_project_id == task_project_id,
                    TestReportDetail.is_deleted == False
                )
                .values(is_deleted=True)
            )
            # 删除 UploadLog（仅删除未软删除的记录）
            await db.execute(
                update(TestReportUploadLog)
                .where(
                    TestReportUploadLog.task_project_id == task_project_id,
                    TestReportUploadLog.is_deleted == False
                )
                .values(is_deleted=True)
            )

        # 删除 Summary
        summary.is_deleted = True

        # 第二步：提交数据库事务（确保数据一致性）
        await db.commit()
        logger.info(f"数据库删除成功: summary_id={summary_id}, task_project_ids={task_project_ids}")

        # 第三步：清理HTML文件目录（在事务提交成功后执行）
        # 注意：文件删除失败不影响已提交的数据库状态，仅记录日志
        for task_project_id in task_project_ids:
            if not task_project_id:
                continue

            html_path = Path(settings.TEST_REPORT_HTML_PATH) / task_project_id
            if html_path.exists():
                try:
                    shutil.rmtree(html_path)
                    logger.info(f"已清理HTML文件目录: {html_path}")
                except OSError as e:
                    # 文件删除失败仅记录警告，不影响响应结果
                    logger.warning(f"清理HTML文件目录失败（数据库已删除）: {html_path}, error={e}")

        return ResponseModel(message="删除成功")

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"删除报告失败: summary_id={summary_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除报告失败: {str(e)}")