#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2025-12-31
@File: service.py
@Desc: Scheduler Service - APScheduler 4.x 调度服务 - 基于 APScheduler 4.x 实现的定时任务调度核心服务
"""
"""
Scheduler Service - APScheduler 4.x 调度服务
基于 APScheduler 4.x 实现的定时任务调度核心服务
"""
import json
import logging
import os
import socket
from datetime import datetime
from typing import Optional, Dict, Any, List

from apscheduler import AsyncScheduler
from apscheduler.datastores.memory import MemoryDataStore
from apscheduler.eventbrokers.local import LocalEventBroker
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from utils.logging_config import get_logger

# 使用专门的 scheduler logger
logger = get_logger("scheduler")


class SchedulerService:
    """
    定时任务调度服务 (APScheduler 4.x)
    
    功能特点：
    1. 使用 APScheduler 4.x 的 AsyncScheduler
    2. 支持多种触发器类型（cron、interval、date）
    3. 自动从数据库加载任务
    4. 通过事件订阅监听任务执行
    5. 自动更新任务状态和记录日志
    """

    _instance = None
    _scheduler: Optional[AsyncScheduler] = None
    _running: bool = False

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_scheduler(self) -> Optional[AsyncScheduler]:
        """获取调度器实例"""
        return self._scheduler

    def set_scheduler(self, scheduler: AsyncScheduler):
        """设置调度器实例"""
        self._scheduler = scheduler
        self._running = True

    def is_running(self) -> bool:
        """判断调度器是否运行中"""
        return self._running and self._scheduler is not None

    def set_running(self, running: bool):
        """设置运行状态"""
        self._running = running

    async def load_jobs_from_db(self):
        """从数据库加载所有启用的任务"""
        logger.info("开始从数据库加载任务...")
        
        if not self._scheduler:
            logger.warning("调度器未初始化，无法加载任务")
            return
            
        try:
            from sqlalchemy import select
            from app.database import AsyncSessionLocal
            from core.scheduler.model import SchedulerJob

            async with AsyncSessionLocal() as db:
                # 获取所有启用的任务
                result = await db.execute(
                    select(SchedulerJob).where(
                        SchedulerJob.status == 1,
                        SchedulerJob.is_deleted == False  # noqa: E712
                    )
                )
                jobs = result.scalars().all()
                
                logger.info(f"查询到 {len(jobs)} 个启用的任务")

                for job in jobs:
                    try:
                        success = await self.add_job(job)
                        if success:
                            logger.info(f"加载任务成功: {job.code}")
                        else:
                            logger.warning(f"加载任务返回失败: {job.code}")
                    except Exception as e:
                        logger.error(f"加载任务失败 {job.code}: {str(e)}")

                logger.info(f"任务加载完成，共加载 {len(jobs)} 个任务")
        except Exception as e:
            logger.error(f"从数据库加载任务失败: {str(e)}")

    async def add_job(self, job_obj) -> bool:
        """添加任务到调度器"""
        if not self._scheduler:
            logger.error("调度器未初始化")
            return False
            
        try:
            # 构建触发器
            trigger = self._build_trigger(job_obj)
            if not trigger:
                logger.error(f"无法为任务 {job_obj.code} 构建触发器")
                return False

            # 导入任务函数
            task_func = self._import_task_func(job_obj.task_func)
            if not task_func:
                logger.error(f"无法导入任务函数: {job_obj.task_func}")
                return False

            # 解析任务参数
            kwargs = json.loads(job_obj.task_kwargs) if job_obj.task_kwargs else {}
            kwargs['job_code'] = job_obj.code

            # 创建带日志记录的包装函数
            wrapper_func = self._create_job_wrapper(task_func, job_obj.code, kwargs)

            # APScheduler 4.x: 需要先使用 configure_task 注册任务
            task_id = job_obj.code
            await self._scheduler.configure_task(task_id, func=wrapper_func)

            # 添加任务调度（返回的是 schedule ID，不是 schedule 对象）
            schedule_id = await self._scheduler.add_schedule(
                func_or_task_id=task_id,
                trigger=trigger,
                id=job_obj.code,
            )

            # 获取 schedule 对象以更新下次执行时间
            schedules = await self._scheduler.get_schedules()
            schedule_obj = None
            for schedule in schedules:
                if schedule.id == schedule_id:
                    schedule_obj = schedule
                    break

            # 更新数据库中的下次执行时间
            if schedule_obj and schedule_obj.next_fire_time:
                from app.database import AsyncSessionLocal
                from sqlalchemy import select
                from core.scheduler.model import SchedulerJob

                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(SchedulerJob).where(SchedulerJob.code == job_obj.code)
                    )
                    db_job = result.scalar_one_or_none()
                    if db_job:
                        # 将带时区的时间转换为不带时区的时间
                        next_fire = schedule_obj.next_fire_time
                        if next_fire and next_fire.tzinfo is not None:
                            next_fire = next_fire.replace(tzinfo=None)
                        db_job.next_run_time = next_fire
                        await db.commit()

            logger.info(f"任务 {job_obj.code} 已添加到调度器")
            return True
        except Exception as e:
            logger.error(f"添加任务失败 {job_obj.code}: {str(e)}")
            return False

    def _check_host_ip_match(self, job_execute_host_ip: Optional[str]) -> tuple[bool, str]:
        """
        检查任务执行主机IP是否匹配本机

        Args:
            job_execute_host_ip: 任务配置的执行主机IP

        Returns:
            (是否可执行, 原因说明)
        """
        host_ip = settings.HOST_IP or ""

        # 任务未指定执行IP → 任意机器可执行
        if not job_execute_host_ip:
            return True, "任务未指定执行主机"

        # 任务指定了IP，但本机未配置 → 不执行
        if not host_ip:
            return False, f"任务指定IP为 {job_execute_host_ip}，本机未配置 HOST_IP"

        # IP匹配检查
        if host_ip == job_execute_host_ip:
            return True, f"IP匹配: {host_ip}"

        return False, f"IP不匹配: 任务要求 {job_execute_host_ip}，本机为 {host_ip}"

    def _create_job_wrapper(self, task_func, job_code: str, kwargs: dict):
        """创建带日志记录的任务包装函数"""
        async def wrapper():
            return await self._execute_job(task_func, job_code, kwargs)
        return wrapper

    async def _execute_job(self, task_func, job_code: str, kwargs: dict):
        """执行任务并记录日志"""
        from app.database import AsyncSessionLocal
        from core.scheduler.model import SchedulerJob, SchedulerLog
        from sqlalchemy import select

        start_time = datetime.now()
        exception_info = None
        result = None
        skip_reason = None
        job_obj = None

        # 获取任务配置并进行IP检查
        try:
            async with AsyncSessionLocal() as db:
                query_result = await db.execute(
                    select(SchedulerJob).where(SchedulerJob.code == job_code)
                )
                job_obj = query_result.scalar_one_or_none()

                if not job_obj:
                    logger.error(f"[{job_code}] 未找到任务记录")
                    return None

                # IP匹配检查
                can_execute, ip_reason = self._check_host_ip_match(job_obj.execute_host_ip)
                if not can_execute:
                    skip_reason = ip_reason
                    logger.info(f"[{job_code}] 跳过执行: {ip_reason}")
        except Exception as e:
            logger.error(f"[{job_code}] 获取任务配置失败: {str(e)}")
            return None

        # 获取本机IP用于日志记录
        executor_ip = settings.HOST_IP or socket.gethostname()

        # 如果IP不匹配，记录跳过日志后返回
        if skip_reason:
            end_time = datetime.now()
            try:
                async with AsyncSessionLocal() as db:
                    if job_obj:
                        log = SchedulerLog(
                            job_id=str(job_obj.id),
                            job_name=job_obj.name,
                            job_code=job_obj.code,
                            start_time=start_time,
                            end_time=end_time,
                            duration=(end_time - start_time).total_seconds(),
                            hostname=executor_ip,
                            status='skipped',
                            result=skip_reason,
                        )
                        db.add(log)
                        await db.commit()
                        logger.info(f"[{job_code}] 已记录跳过日志")
            except Exception as e:
                logger.error(f"[{job_code}] 记录跳过日志失败: {str(e)}")
            return None

        # 正常执行任务
        try:
            result = await task_func(**kwargs)
        except Exception as e:
            exception_info = e
            logger.error(f"[{job_code}] 任务执行失败: {str(e)}")

        end_time = datetime.now()

        # 记录日志和更新任务状态
        try:
            async with AsyncSessionLocal() as db:
                # 获取任务
                query_result = await db.execute(
                    select(SchedulerJob).where(SchedulerJob.code == job_code)
                )
                job_obj = query_result.scalar_one_or_none()

                if not job_obj:
                    logger.error(f"[{job_code}] 未找到任务记录")
                    return result

                # 创建执行日志
                log = SchedulerLog(
                    job_id=str(job_obj.id),
                    job_name=job_obj.name,
                    job_code=job_obj.code,
                    start_time=start_time,
                    end_time=end_time,
                    duration=(end_time - start_time).total_seconds(),
                    hostname=executor_ip,
                    process_id=os.getpid(),
                )

                if exception_info:
                    # 执行失败
                    job_obj.last_run_status = 'failed'
                    job_obj.last_run_result = str(exception_info)
                    job_obj.failure_count += 1
                    log.status = 'failed'
                    log.exception = str(exception_info)
                    import traceback
                    log.traceback = traceback.format_exc()
                else:
                    # 执行成功
                    job_obj.last_run_status = 'success'
                    job_obj.last_run_result = str(result) if result else None
                    job_obj.success_count += 1
                    log.status = 'success'
                    log.result = str(result) if result else None

                job_obj.total_run_count += 1
                job_obj.last_run_time = end_time

                # 更新下次执行时间
                try:
                    schedules = await self._scheduler.get_schedules()
                    for schedule in schedules:
                        if schedule.id == job_code:
                            # 将带时区的时间转换为不带时区的时间
                            next_fire = schedule.next_fire_time
                            if next_fire and next_fire.tzinfo is not None:
                                next_fire = next_fire.replace(tzinfo=None)
                            job_obj.next_run_time = next_fire
                            break
                except Exception as e:
                    logger.warning(f"[{job_code}] 获取下次执行时间失败: {str(e)}")

                db.add(log)
                await db.commit()
                logger.info(f"[{job_code}] 执行完成，状态: {log.status}")

                # 一次性任务（date 类型）执行后自动清理
                if job_obj.trigger_type == 'date':
                    await self._cleanup_one_time_job(db, job_obj)

        except Exception as e:
            logger.error(f"[{job_code}] 记录任务执行日志失败: {str(e)}")

        if exception_info:
            raise exception_info

        return result

    async def remove_job(self, job_code: str) -> bool:
        """从调度器移除任务"""
        if not self._scheduler:
            return False
            
        try:
            await self._scheduler.remove_schedule(job_code)
            logger.info(f"任务 {job_code} 已从调度器移除")
            return True
        except Exception as e:
            logger.error(f"移除任务失败 {job_code}: {str(e)}")
            return False

    async def pause_job(self, job_code: str) -> bool:
        """暂停任务"""
        if not self._scheduler:
            return False
            
        try:
            await self._scheduler.pause_schedule(job_code)
            logger.info(f"任务 {job_code} 已暂停")
            return True
        except Exception as e:
            logger.error(f"暂停任务失败 {job_code}: {str(e)}")
            return False

    async def resume_job(self, job_code: str) -> bool:
        """恢复任务"""
        if not self._scheduler:
            return False
            
        try:
            await self._scheduler.unpause_schedule(job_code)
            logger.info(f"任务 {job_code} 已恢复")
            return True
        except Exception as e:
            logger.error(f"恢复任务失败 {job_code}: {str(e)}")
            return False

    async def modify_job(self, job_obj) -> bool:
        """修改任务"""
        try:
            # 先移除旧任务
            await self.remove_job(job_obj.code)

            # 如果任务是启用状态，重新添加
            if job_obj.is_enabled():
                return await self.add_job(job_obj)

            return True
        except Exception as e:
            logger.error(f"修改任务失败 {job_obj.code}: {str(e)}")
            return False

    async def run_job_now(self, job_code: str) -> bool:
        """立即执行任务"""
        if not self._scheduler:
            logger.error("调度器未初始化")
            return False

        try:
            from sqlalchemy import select
            from app.database import AsyncSessionLocal
            from core.scheduler.model import SchedulerJob

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(SchedulerJob).where(SchedulerJob.code == job_code)
                )
                job_obj = result.scalar_one_or_none()

                if not job_obj:
                    logger.error(f"任务不存在: {job_code}")
                    return False

                # 解析任务参数
                kwargs = json.loads(job_obj.task_kwargs) if job_obj.task_kwargs else {}
                kwargs['job_code'] = job_obj.code

                # 导入任务函数
                task_func = self._import_task_func(job_obj.task_func)
                if not task_func:
                    logger.error(f"无法导入任务函数: {job_obj.task_func}")
                    return False

                await self._execute_job(task_func, job_code, kwargs)
                return True

        except Exception as e:
            logger.error(f"立即执行任务失败 {job_code}: {str(e)}")
            return False

    async def get_job_info(self, job_code: str) -> Optional[Dict[str, Any]]:
        """获取任务信息"""
        if not self._scheduler:
            return None
            
        try:
            schedules = await self._scheduler.get_schedules()
            for schedule in schedules:
                if schedule.id == job_code:
                    return {
                        'id': schedule.id,
                        'next_run_time': schedule.next_fire_time.isoformat() if schedule.next_fire_time else None,
                        'trigger': str(schedule.trigger),
                    }
            return None
        except Exception as e:
            logger.error(f"获取任务信息失败 {job_code}: {str(e)}")
            return None

    async def get_all_jobs(self) -> List[Dict[str, Any]]:
        """获取所有任务"""
        if not self._scheduler:
            return []
            
        try:
            schedules = await self._scheduler.get_schedules()
            return [
                {
                    'id': schedule.id,
                    'next_run_time': schedule.next_fire_time.isoformat() if schedule.next_fire_time else None,
                    'trigger': str(schedule.trigger),
                }
                for schedule in schedules
            ]
        except Exception as e:
            logger.error(f"获取所有任务失败: {str(e)}")
            return []

    def _build_trigger(self, job_obj):
        """构建触发器"""
        try:
            if job_obj.trigger_type == 'cron':
                # Cron 触发器
                parts = job_obj.cron_expression.split()
                if len(parts) != 5:
                    logger.error(f"Cron 表达式格式错误: {job_obj.cron_expression}")
                    return None

                return CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4],
                )

            elif job_obj.trigger_type == 'interval':
                # 间隔触发器
                return IntervalTrigger(seconds=job_obj.interval_seconds)

            elif job_obj.trigger_type == 'date':
                # 指定时间触发器
                return DateTrigger(run_time=job_obj.run_date)

            else:
                logger.error(f"不支持的触发器类型: {job_obj.trigger_type}")
                return None

        except Exception as e:
            logger.error(f"构建触发器失败: {str(e)}")
            return None

    def _import_task_func(self, task_path: str):
        """动态导入任务函数"""
        try:
            module_path, func_name = task_path.rsplit('.', 1)
            module = __import__(module_path, fromlist=[func_name])
            return getattr(module, func_name)
        except Exception as e:
            logger.error(f"导入任务函数失败 {task_path}: {str(e)}")
            return None

    async def _cleanup_one_time_job(self, db, job_obj):
        """清理一次性任务"""
        try:
            job_code = job_obj.code

            # 从调度器移除
            try:
                await self._scheduler.remove_schedule(job_code)
            except Exception:
                pass

            # 软删除数据库记录
            job_obj.is_deleted = True
            await db.commit()

            logger.debug(f"一次性任务已清理: {job_code}")
        except Exception as e:
            logger.error(f"清理一次性任务失败 {job_obj.code}: {str(e)}")

    async def cleanup_expired_jobs(self, days: int = 7) -> int:
        """
        清理过期的一次性任务
        
        Args:
            days: 清理多少天前的任务，默认7天
        """
        try:
            from datetime import timedelta
            from sqlalchemy import select
            from app.database import AsyncSessionLocal
            from core.scheduler.model import SchedulerJob

            cutoff = datetime.now() - timedelta(days=days)

            async with AsyncSessionLocal() as db:
                # 查找过期的一次性任务
                result = await db.execute(
                    select(SchedulerJob).where(
                        SchedulerJob.trigger_type == 'date',
                        SchedulerJob.run_date < cutoff,
                        SchedulerJob.is_deleted == False  # noqa: E712
                    )
                )
                expired_jobs = result.scalars().all()

                count = len(expired_jobs)
                if count > 0:
                    for job in expired_jobs:
                        # 从调度器移除
                        try:
                            await self._scheduler.remove_schedule(job.code)
                        except Exception:
                            pass
                        # 软删除
                        job.is_deleted = True

                    await db.commit()
                    logger.info(f"清理了 {count} 个过期的一次性任务")

                return count
        except Exception as e:
            logger.error(f"清理过期任务失败: {str(e)}")
            return 0

    async def init_scheduler(self):
        """
        初始化调度器

        创建 AsyncScheduler 实例，启动调度器，并从数据库加载任务

        注意：APScheduler 4.0.0a6 版本需要调用 __aenter__ 来初始化调度器，
        然后才能调用 configure_task、add_schedule 等方法。
        """
        try:
            # 创建事件代理和数据存储
            # APScheduler 4.0.0a6: 需要手动设置 _event_broker 属性（alpha 版本 bug）
            event_broker = LocalEventBroker()
            data_store = MemoryDataStore()
            data_store._event_broker = event_broker  # 修复 alpha 版本 bug

            # 创建调度器实例
            self._scheduler = AsyncScheduler(
                data_store=data_store,
                event_broker=event_broker
            )

            # 手动调用 __aenter__ 初始化调度器
            # 这是 APScheduler 4.0.0a6 的要求，只有初始化后才能调用其他方法
            await self._scheduler.__aenter__()

            # 启动调度器后台运行（这才是真正让调度器执行任务的关键！）
            await self._scheduler.start_in_background()

            self._running = True
            logger.info("调度器已初始化并启动")

            # 从数据库加载任务
            await self.load_jobs_from_db()

            return True
        except Exception as e:
            logger.error(f"初始化调度器失败: {str(e)}")
            self._running = False
            return False

    async def shutdown(self):
        """
        关闭调度器

        注意：APScheduler 4.0.0a6 需要调用 __aexit__ 来正确关闭调度器
        """
        if not self._scheduler:
            return

        try:
            # 先停止调度器
            await self._scheduler.stop()
            # 调用 __aexit__ 清理资源
            await self._scheduler.__aexit__(None, None, None)
            logger.info("调度器已关闭")
        except Exception as e:
            logger.error(f"关闭调度器失败: {str(e)}")

        self._running = False
        self._scheduler = None


# 全局调度器服务实例
scheduler_service = SchedulerService()
