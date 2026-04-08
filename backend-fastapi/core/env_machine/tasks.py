#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: Claude
@Time: 2026-04-08
@File: tasks.py
@Desc: 执行机定时任务
"""
from datetime import datetime, timedelta
from sqlalchemy import delete, select
from app.database import AsyncSessionLocal
from core.env_machine.model import EnvMachine
from core.env_machine.log_model import EnvMachineLog
from utils.logging_config import get_logger

logger = get_logger("env_machine.tasks")


async def cleanup_offline_devices_task(job_code: str = None, days: int = 7, **kwargs):
    """
    清理过期离线设备任务

    Args:
        job_code: 任务编码（由调度器自动传入）
        days: 清理多少天前的设备，默认7天
        **kwargs: 其他参数
    """
    logger.info(f"[{job_code}] 离线设备清理任务开始，清理 {days} 天前的设备")

    try:
        cutoff = datetime.now() - timedelta(days=days)

        async with AsyncSessionLocal() as db:
            # 物理删除：available=False、status=offline、sync_time超过指定天数、排除manual namespace
            stmt = delete(EnvMachine).where(
                EnvMachine.is_deleted == False,
                EnvMachine.available == False,
                EnvMachine.status == 'offline',
                EnvMachine.sync_time < cutoff,
                EnvMachine.namespace.notlike('%manual%')
            )
            result = await db.execute(stmt)
            count = result.rowcount
            await db.commit()

        logger.info(f"[{job_code}] 离线设备清理任务完成，删除了 {count} 台设备")
        return f"清理了 {count} 台过期离线设备，清理 {days} 天前的数据"
    except Exception as e:
        logger.error(f"[{job_code}] 离线设备清理任务执行失败: {str(e)}")
        raise


async def merge_env_not_enough_logs_task(job_code: str = None, **kwargs):
    """
    合并资源不足日志任务

    每5分钟执行一次，合并同一 testcase_id 连续申请失败的记录。
    连续定义：两条记录的 sys_create_datetime 间隔不超过60秒。

    Args:
        job_code: 任务编码（由调度器自动传入）
        **kwargs: 其他参数
    """
    logger.info(f"[{job_code}] 资源不足日志合并任务开始")

    try:
        async with AsyncSessionLocal() as db:
            # 查询所有未合并的资源不足失败记录（有 testcase_id）
            result = await db.execute(
                select(EnvMachineLog)
                .where(
                    EnvMachineLog.testcase_id.isnot(None),
                    EnvMachineLog.result == "fail",
                    EnvMachineLog.fail_reason == "env not enough"
                )
                .order_by(EnvMachineLog.testcase_id, EnvMachineLog.sys_create_datetime.asc())
            )
            logs = result.scalars().all()

            if not logs:
                logger.info(f"[{job_code}] 资源不足日志合并任务完成，无记录需要合并")
                return "无记录需要合并"

            # 按 testcase_id 分组
            testcase_logs = {}
            for log in logs:
                if log.testcase_id not in testcase_logs:
                    testcase_logs[log.testcase_id] = []
                testcase_logs[log.testcase_id].append(log)

            total_deleted = 0
            for testcase_id, log_list in testcase_logs.items():
                # 按连续性分组（间隔超过60秒为不连续）
                groups = []
                current_group = [log_list[0]]

                for i in range(1, len(log_list)):
                    prev_log = log_list[i - 1]
                    curr_log = log_list[i]
                    time_diff = (curr_log.sys_create_datetime - prev_log.sys_create_datetime).total_seconds()

                    if time_diff <= 60:
                        # 连续，加入当前组
                        current_group.append(curr_log)
                    else:
                        # 不连续，开始新组
                        groups.append(current_group)
                        current_group = [curr_log]

                groups.append(current_group)  # 添加最后一组

                # 每组只保留最后一条，删除其他
                for group in groups:
                    if len(group) > 1:
                        for log in group[:-1]:
                            await db.delete(log)
                            total_deleted += 1

            await db.commit()

        logger.info(f"[{job_code}] 资源不足日志合并任务完成，删除了 {total_deleted} 条记录")
        return f"合并了 {total_deleted} 条资源不足日志"
    except Exception as e:
        logger.error(f"[{job_code}] 资源不足日志合并任务执行失败: {str(e)}")
        raise