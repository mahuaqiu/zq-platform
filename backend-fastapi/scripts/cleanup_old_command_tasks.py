#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: Codex
@Time: 2026-07-05
@File: cleanup_old_command_tasks.py
@Desc: 清理超过7天的命令任务记录
"""
import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from core.config_template.command_task_model import CommandTask

logger = logging.getLogger(__name__)


async def cleanup_old_command_tasks(days: int = 7):
    """清理指定天数之前的命令任务记录"""
    async for db in get_db():
        try:
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=days)

            result = await db.execute(
                select(CommandTask).where(
                    CommandTask.sys_create_datetime < cutoff_date
                )
            )
            tasks = list(result.scalars().all())

            if tasks:
                for task in tasks:
                    task.is_deleted = True
                await db.commit()
                logger.info(f"已清理 {len(tasks)} 条超过 {days} 天的命令任务记录")
            else:
                logger.info(f"没有需要清理的超过 {days} 天的命令任务记录")

        except Exception as e:
            logger.error(f"清理命令任务记录失败: {e}")
            await db.rollback()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(cleanup_old_command_tasks())
