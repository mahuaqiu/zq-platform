#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: Codex
@Time: 2026-07-05
@File: command_task_service.py
@Desc: CommandTask Service - 命令任务服务层
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_service import BaseService
from core.config_template.command_task_model import CommandTask
from core.config_template.schema import (
    CommandTaskResponse,
    CommandTaskDetailResponse,
)

logger = logging.getLogger(__name__)


class CommandTaskService(BaseService):
    """
    命令任务服务层
    """

    model = CommandTask

    @classmethod
    async def create_task(
        cls,
        db: AsyncSession,
        template_id: Optional[str],
        template_type: str,
        template_name: str,
        command: Optional[str],
        machine_count: int,
        auto_commit: bool = True
    ) -> CommandTask:
        """创建任务记录"""
        db_obj = CommandTask(
            template_id=template_id,
            template_type=template_type,
            template_name=template_name,
            command=command,
            machine_count=machine_count,
            status="running",
            success_count=0,
            failed_count=0,
        )
        db.add(db_obj)

        if auto_commit:
            await db.commit()
            await db.refresh(db_obj)
        else:
            await db.flush()
            await db.refresh(db_obj)

        return db_obj

    @classmethod
    async def update_task_result(
        cls,
        db: AsyncSession,
        task_id: str,
        status: str,
        success_count: int,
        failed_count: int,
        result_detail: List[dict],
        auto_commit: bool = True
    ) -> Optional[CommandTask]:
        """更新任务结果"""
        task = await cls.get_by_id(db, task_id)
        if not task:
            return None

        task.status = status
        task.success_count = success_count
        task.failed_count = failed_count
        task.result_detail = result_detail
        task.finished_datetime = datetime.now()

        if auto_commit:
            await db.commit()
            await db.refresh(task)
        else:
            await db.flush()
            await db.refresh(task)

        return task

    @classmethod
    async def get_task_list(
        cls,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        template_type: Optional[str] = None,
    ) -> tuple[List[CommandTask], int]:
        """获取任务列表（分页）"""
        query = select(CommandTask).where(CommandTask.is_deleted == False)
        
        if template_type:
            query = query.where(CommandTask.template_type == template_type)
        
        query = query.order_by(CommandTask.sys_create_datetime.desc())
        
        # 获取总数
        from sqlalchemy import func
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 分页查询
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        result = await db.execute(query)
        items = list(result.scalars().all())
        
        return items, total

    @classmethod
    async def cleanup_old_tasks(cls, db: AsyncSession, days: int = 7) -> int:
        """清理指定天数之前的任务记录"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        result = await db.execute(
            delete(CommandTask).where(
                CommandTask.sys_create_datetime < cutoff_date
            )
        )
        await db.commit()
        
        return result.rowcount
