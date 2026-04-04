#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
初始化定时任务数据
将内部自动管理的任务添加到数据库，使其在管理页面可见
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from core.scheduler.model import SchedulerJob


async def init_scheduler_jobs():
    """初始化定时任务数据"""

    # 内部自动管理的任务列表
    internal_jobs = [
        {
            'name': '设备离线检测',
            'code': 'env_machine_offline_check',
            'description': '检测sync_time超过10分钟的机器，标记为offline',
            'group': 'env_machine',
            'trigger_type': 'interval',
            'interval_seconds': 120,  # 每2分钟
            'task_func': 'core.env_machine.scheduler.check_offline_machines',
            'status': 1,  # 启用
            'priority': 10,
            'remark': '内部任务，自动管理',
        },
        {
            'name': '测试报告分析',
            'code': 'test_report_analyze',
            'description': '检查超时的测试报告并触发汇总分析',
            'group': 'test_report',
            'trigger_type': 'interval',
            'interval_seconds': 300,  # 每5分钟
            'task_func': 'core.test_report.scheduler.check_and_analyze_timeout_reports',
            'status': 1,  # 启用
            'priority': 5,
            'remark': '内部任务，自动管理',
        },
        {
            'name': '测试报告清理',
            'code': 'test_report_cleanup',
            'description': '清理过期的测试报告文件和数据库记录',
            'group': 'test_report',
            'trigger_type': 'cron',
            'cron_expression': '0 23 * * *',  # 每天23:00
            'task_func': 'core.test_report.scheduler.cleanup_old_reports',
            'status': 1,  # 启用
            'priority': 5,
            'remark': '内部任务，自动管理',
        },
        {
            'name': '日志清理',
            'code': 'scheduler_log_cleanup',
            'description': '清理过期的定时任务执行日志',
            'group': 'scheduler',
            'trigger_type': 'cron',
            'cron_expression': '0 3 * * *',  # 每天3:00
            'task_func': 'core.scheduler.tasks.cleanup_task',
            'task_kwargs': '{"days": 7}',
            'status': 1,  # 启用
            'priority': 1,
            'remark': '清理7天前的执行日志',
        },
        {
            'name': '执行机申请日志清理',
            'code': 'env_machine_log_cleanup',
            'description': '清理过期的执行机申请日志',
            'group': 'env_machine',
            'trigger_type': 'cron',
            'cron_expression': '0 3 * * *',  # 每天3:00
            'task_func': 'core.scheduler.tasks.cleanup_env_machine_log_task',
            'task_kwargs': '{"days": 7}',
            'status': 1,  # 启用
            'priority': 1,
            'remark': '清理7天前的执行机申请日志',
        },
    ]

    async with AsyncSessionLocal() as db:
        created_count = 0
        updated_count = 0

        for job_data in internal_jobs:
            # 检查任务是否已存在
            result = await db.execute(
                select(SchedulerJob).where(SchedulerJob.code == job_data['code'])
            )
            existing_job = result.scalar_one_or_none()

            if existing_job:
                # 更新现有任务
                for key, value in job_data.items():
                    setattr(existing_job, key, value)
                updated_count += 1
                print(f"更新任务: {job_data['code']}")
            else:
                # 创建新任务
                new_job = SchedulerJob(**job_data)
                db.add(new_job)
                created_count += 1
                print(f"创建任务: {job_data['code']}")

        await db.commit()

    print(f"\n初始化完成: 创建 {created_count} 个任务, 更新 {updated_count} 个任务")


if __name__ == '__main__':
    asyncio.run(init_scheduler_jobs())