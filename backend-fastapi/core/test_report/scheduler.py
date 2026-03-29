#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试报告定时任务 - Test Report Scheduler
"""
import logging
import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select, func, not_
from apscheduler.triggers.interval import IntervalTrigger

from app.database import AsyncSessionLocal
from app.config import settings
from core.test_report.model import TestReportDetail, TestReportSummary
from core.test_report.service import TestReportSummaryService
from scheduler.service import scheduler_service

logger = logging.getLogger(__name__)

ANALYZE_JOB_ID = "test_report_analyze"  # 分析任务 ID
ANALYZE_INTERVAL_MINUTES = 5  # 执行间隔（分钟）


async def check_and_analyze_timeout_reports():
    """
    检查并分析超时的测试报告

    扫描逻辑：
    1. 查询有明细但无汇总的 task_id
    2. 判断最后上报时间是否超过配置的超时时间
    3. 触发汇总分析
    """
    timeout_minutes = settings.ANALYZE_TIMEOUT_MINUTES
    logger.info(f"开始扫描超时测试报告，超时时间: {timeout_minutes} 分钟")

    async with AsyncSessionLocal() as db:
        try:
            # 查询有明细但无汇总的 task_id
            subquery = select(TestReportSummary.task_id).where(
                TestReportSummary.is_deleted == False
            )

            # 查询明细中有但汇总中没有的 task_id
            result = await db.execute(
                select(
                    TestReportDetail.task_id,
                    func.max(TestReportDetail.sys_create_datetime).label('last_report_time')
                ).where(
                    TestReportDetail.is_deleted == False,
                    not_(TestReportDetail.task_id.in_(subquery))
                ).group_by(TestReportDetail.task_id)
            )

            pending_tasks = result.all()

            for task_id, last_report_time in pending_tasks:
                # 检查是否超时
                if last_report_time:
                    time_diff = datetime.now() - last_report_time
                    if time_diff > timedelta(minutes=timeout_minutes):
                        logger.info(f"task_id={task_id} 超时，触发汇总分析")
                        try:
                            await TestReportSummaryService.analyze_summary(db, task_id)
                            logger.info(f"task_id={task_id} 汇总分析完成")
                        except Exception as e:
                            logger.error(f"task_id={task_id} 汇总分析失败: {e}")

            logger.info(f"扫描完成，共检查 {len(pending_tasks)} 个待分析任务")

        except Exception as e:
            logger.error(f"扫描超时测试报告失败: {e}")


async def _analyze_job_wrapper():
    """分析任务包装函数"""
    try:
        await check_and_analyze_timeout_reports()
    except Exception as e:
        logger.error(f"分析任务执行失败: {str(e)}")


def setup_test_report_scheduler() -> bool:
    """
    设置测试报告定时任务

    使用 APScheduler 4.x API 注册周期任务

    Returns:
        bool: 是否设置成功
    """
    scheduler = scheduler_service.get_scheduler()
    if not scheduler:
        logger.warning("调度器未初始化，无法设置测试报告定时任务")
        return False

    try:
        async def _setup():
            job_id = ANALYZE_JOB_ID

            # 注册任务函数
            await scheduler.configure_task(job_id, func=_analyze_job_wrapper)

            # 添加周期调度（每 5 分钟执行一次）
            await scheduler.add_schedule(
                func_or_task_id=job_id,
                trigger=IntervalTrigger(minutes=ANALYZE_INTERVAL_MINUTES),
                id=job_id,
            )

            logger.info(f"测试报告定时任务已启动，间隔: {ANALYZE_INTERVAL_MINUTES} 分钟")

        # 尝试在当前事件循环中运行
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(_setup())
        except RuntimeError:
            # 没有运行中的事件循环，创建新的
            asyncio.run(_setup())

        return True
    except Exception as e:
        logger.error(f"设置测试报告定时任务失败: {str(e)}")
        return False