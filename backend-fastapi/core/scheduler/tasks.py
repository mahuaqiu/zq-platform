#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2025-12-31
@File: tasks.py
@Desc: Scheduler Tasks - 定时任务函数
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from app.database import AsyncSessionLocal
from core.scheduler.model import SchedulerLog
from utils.logging_config import get_logger

# 使用专门的 scheduler logger
logger = get_logger("scheduler.tasks")


async def cleanup_task(job_code: str = None, days: int = 30, **kwargs):
    """
    清理过期日志任务

    Args:
        job_code: 任务编码（由调度器自动传入）
        days: 保留最近N天的数据，默认30天
        **kwargs: 其他参数
    """
    logger.info(f"[{job_code}] 清理任务执行开始，保留最近 {days} 天数据")

    try:
        cutoff = datetime.now() - timedelta(days=days)

        async with AsyncSessionLocal() as db:
            # 删除过期日志
            result = await db.execute(
                select(SchedulerLog).where(SchedulerLog.start_time < cutoff)
            )
            logs = result.scalars().all()
            count = len(logs)

            for log in logs:
                await db.delete(log)

            await db.commit()

        logger.info(f"[{job_code}] 清理任务执行完成，删除了 {count} 条日志")
        return f"清理了 {count} 条过期日志"
    except Exception as e:
        logger.error(f"[{job_code}] 清理任务执行失败: {str(e)}")
        raise
