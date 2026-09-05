#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导出临时文件清理 —— 调度器内置周期任务。

不走 DB 任务表（无需前端管理），由持有领导权租约的实例在
init_scheduler 中注册，每小时执行一次。
"""
import logging

logger = logging.getLogger(__name__)


async def cleanup_export_task(job_code: str = None, **kwargs) -> None:
    """每小时清理过期导出临时文件。"""
    from core.performance_monitor.service import ExportTaskService

    try:
        await ExportTaskService.cleanup_export_files()
    except Exception as e:
        logger.error(f"清理导出文件失败: {e}")
