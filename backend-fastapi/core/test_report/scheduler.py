#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试报告定时任务 - Test Report Scheduler
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select, func, not_, delete
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.database import AsyncSessionLocal
from app.config import settings
from core.test_report.model import TestReportDetail, TestReportSummary
from core.test_report.service import TestReportSummaryService
from scheduler.service import scheduler_service

logger = logging.getLogger(__name__)

ANALYZE_JOB_ID = "test_report_analyze"  # 分析任务 ID
ANALYZE_INTERVAL_MINUTES = 5  # 执行间隔（分钟）

CLEANUP_JOB_ID = "test_report_cleanup"  # 清理任务 ID


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


async def cleanup_old_reports():
    """
    清理过期的测试报告

    清理规则：
    1. HTML 文件：删除超过 TEST_REPORT_HTML_CLEANUP_DAYS 天的文件
    2. 空目录：清理空目录
    3. 数据库明细记录：删除超过 TEST_REPORT_DETAIL_CLEANUP_DAYS 天的记录
    4. test_report_summary 不删除
    """
    html_cleanup_days = settings.TEST_REPORT_HTML_CLEANUP_DAYS
    detail_cleanup_days = settings.TEST_REPORT_DETAIL_CLEANUP_DAYS
    html_path = Path(settings.TEST_REPORT_HTML_PATH)

    logger.info(f"开始清理过期测试报告，HTML保留天数: {html_cleanup_days}，明细保留天数: {detail_cleanup_days}")

    # 1. 清理 HTML 文件
    html_deleted_count = 0
    html_error_count = 0
    cutoff_time = datetime.now() - timedelta(days=html_cleanup_days)

    if html_path.exists():
        try:
            for html_file in html_path.rglob("*.html"):
                try:
                    # 获取文件修改时间
                    file_mtime = datetime.fromtimestamp(html_file.stat().st_mtime)
                    if file_mtime < cutoff_time:
                        html_file.unlink()
                        html_deleted_count += 1
                        logger.debug(f"已删除过期 HTML 文件: {html_file}")
                except Exception as e:
                    html_error_count += 1
                    logger.warning(f"删除 HTML 文件失败 {html_file}: {e}")

            # 2. 清理空目录
            for dir_path in sorted(html_path.rglob("*"), key=lambda x: len(x.parts), reverse=True):
                if dir_path.is_dir():
                    try:
                        if not any(dir_path.iterdir()):  # 目录为空
                            dir_path.rmdir()
                            logger.debug(f"已删除空目录: {dir_path}")
                    except Exception as e:
                        logger.warning(f"删除空目录失败 {dir_path}: {e}")

        except Exception as e:
            logger.error(f"清理 HTML 文件目录失败: {e}")
    else:
        logger.warning(f"HTML 文件存储路径不存在: {html_path}")

    # 3. 清理数据库明细记录
    db_deleted_count = 0
    async with AsyncSessionLocal() as db:
        try:
            detail_cutoff_time = datetime.now() - timedelta(days=detail_cleanup_days)

            # 删除超过保留天数的明细记录（仅删除未软删除的记录）
            result = await db.execute(
                delete(TestReportDetail).where(
                    TestReportDetail.sys_create_datetime < detail_cutoff_time,
                    TestReportDetail.is_deleted == False
                )
            )
            db_deleted_count = result.rowcount
            await db.commit()

            logger.info(f"已删除 {db_deleted_count} 条过期明细记录")

        except Exception as e:
            await db.rollback()
            logger.error(f"清理数据库明细记录失败: {e}")

    logger.info(
        f"清理完成 - HTML文件: 删除 {html_deleted_count} 个, 错误 {html_error_count} 个; "
        f"数据库明细: 删除 {db_deleted_count} 条"
    )


async def _cleanup_job_wrapper():
    """清理任务包装函数"""
    try:
        await cleanup_old_reports()
    except Exception as e:
        logger.error(f"清理任务执行失败: {str(e)}")


async def setup_test_report_scheduler() -> bool:
    """
    设置测试报告定时任务

    使用 APScheduler 4.x API 注册周期任务

    Returns:
        bool: 是否设置成功
    """
    logger.info("开始设置测试报告定时任务...")

    scheduler = scheduler_service.get_scheduler()
    if not scheduler:
        logger.warning("调度器未初始化，无法设置测试报告定时任务")
        return False

    logger.info(f"调度器获取成功: {scheduler}")

    try:
        # 分析任务
        job_id = ANALYZE_JOB_ID
        logger.info(f"正在注册分析任务: {job_id}")
        await scheduler.configure_task(job_id, func=_analyze_job_wrapper)
        await scheduler.add_schedule(
            func_or_task_id=job_id,
            trigger=IntervalTrigger(minutes=ANALYZE_INTERVAL_MINUTES),
            id=job_id,
        )
        logger.info(f"测试报告分析任务已启动，间隔: {ANALYZE_INTERVAL_MINUTES} 分钟")

        # 清理任务（每天晚上 23:00）
        cleanup_job_id = CLEANUP_JOB_ID
        logger.info(f"正在注册清理任务: {cleanup_job_id}")
        await scheduler.configure_task(cleanup_job_id, func=_cleanup_job_wrapper)
        await scheduler.add_schedule(
            func_or_task_id=cleanup_job_id,
            trigger=CronTrigger(hour=23, minute=0),
            id=cleanup_job_id,
        )
        logger.info(f"测试报告清理任务已启动，执行时间: 每天 23:00")

        return True
    except Exception as e:
        logger.error(f"设置测试报告定时任务失败: {str(e)}", exc_info=True)
        return False