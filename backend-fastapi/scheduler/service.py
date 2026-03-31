#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2025-03-29
@File: service.py
@Desc: APScheduler 调度器服务 - 单例模式封装
"""
import asyncio
from typing import Optional

from apscheduler import AsyncScheduler
from utils.logging_config import get_logger

logger = get_logger("scheduler")


class SchedulerService:
    """
    调度器服务类 - 单例模式

    封装 APScheduler AsyncScheduler，提供统一的调度器管理

    APScheduler 4.x 使用异步上下文管理器方式运行：
    async with AsyncScheduler() as scheduler:
        ...
    """

    _instance: Optional["SchedulerService"] = None
    _scheduler: Optional[AsyncScheduler] = None
    _context_task: Optional[asyncio.Task] = None
    _running: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def init_scheduler(self) -> AsyncScheduler:
        """
        初始化并启动调度器

        APScheduler 4.x 需要通过 async with 来启动调度器，
        并调用 run_until_stopped() 来让调度器真正执行任务。

        Returns:
            AsyncScheduler: 调度器实例
        """
        if self._scheduler is None:
            self._scheduler = AsyncScheduler()

        if not self._running:
            # 创建后台任务来运行调度器
            async def run_scheduler_context():
                async with self._scheduler:
                    self._running = True
                    logger.info("APScheduler 调度器已启动")
                    try:
                        # run_until_stopped 是关键！让调度器真正执行任务
                        await self._scheduler.run_until_stopped()
                    except asyncio.CancelledError:
                        logger.info("调度器上下文任务被取消")
                        raise

            self._context_task = asyncio.create_task(run_scheduler_context())
            # 等待调度器启动
            await asyncio.sleep(0.1)

        return self._scheduler

    def get_scheduler(self) -> Optional[AsyncScheduler]:
        """
        获取调度器实例

        Returns:
            Optional[AsyncScheduler]: 调度器实例，如果未初始化则返回 None
        """
        return self._scheduler

    async def shutdown(self):
        """关闭调度器"""
        # 先调用 scheduler.stop() 优雅停止
        if self._scheduler is not None and self._running:
            try:
                await self._scheduler.stop()
                logger.info("已调用 scheduler.stop()")
            except Exception as e:
                logger.warning(f"调用 scheduler.stop() 失败: {e}")

        # 然后取消后台任务
        if self._context_task is not None:
            self._context_task.cancel()
            try:
                await self._context_task
            except asyncio.CancelledError:
                pass
            self._context_task = None

        self._running = False
        self._scheduler = None
        logger.info("APScheduler 调度器已关闭")


# 全局单例实例
scheduler_service = SchedulerService()