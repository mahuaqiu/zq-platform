#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File: background_tasks.py
@Desc: 后台任务创建工具 - 强引用持有 + 异常记录

asyncio.create_task 创建的任务如果没有保存引用，可能在执行中途被垃圾回收；
未捕获的异常也会被静默丢弃。统一通过 spawn_background_task 创建后台任务：
模块级集合持有强引用直到任务结束，异常统一记录日志。
"""
import asyncio
import logging
from typing import Coroutine, Optional

logger = logging.getLogger(__name__)

# 模块级强引用，防止任务被 GC 中途取消
_background_tasks: set = set()


def _on_task_done(task: "asyncio.Task") -> None:
    """任务结束回调：移除强引用并记录未捕获异常。"""
    _background_tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            "后台任务异常退出: task=%s, error=%s", task.get_name(), exc, exc_info=exc
        )


def spawn_background_task(coro: Coroutine, *, name: Optional[str] = None) -> "asyncio.Task":
    """
    创建有强引用、有异常记录的后台任务

    用于替代裸 asyncio.create_task 的 fire-and-forget 场景。

    Args:
        coro: 协程对象
        name: 任务名（便于日志排查）

    Returns:
        asyncio.Task: 创建的任务
    """
    task = asyncio.create_task(coro, name=name)
    _background_tasks.add(task)
    task.add_done_callback(_on_task_done)
    return task
