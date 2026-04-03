#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2025-03-25
@File: scheduler.py
@Desc: 执行机定时任务管理器 - 延迟释放和离线检测
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from apscheduler import JobLookupError, AsyncScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from core.env_machine.model import EnvMachine
from core.scheduler.service import scheduler_service
from utils.logging_config import get_logger

# 使用专门的 scheduler logger
logger = get_logger("scheduler.env_machine")


class EnvMachineScheduler:
    """
    执行机定时任务管理器

    功能：
    1. 延迟释放任务：每台占用的机器创建独立的延迟任务
    2. 离线检测任务：周期性检测 sync_time 超时的机器
    """

    RELEASE_JOB_PREFIX = "release_"  # 延迟释放任务 ID 前缀
    OFFLINE_CHECK_JOB_ID = "env_machine_offline_check"  # 离线检测任务 ID
    RELEASE_DELAY_MINUTES = 1  # 延迟释放时间（分钟）
    OFFLINE_THRESHOLD_MINUTES = 10  # 离线检测阈值（分钟）
    OFFLINE_CHECK_INTERVAL_MINUTES = 2  # 离线检测间隔（分钟）

    @classmethod
    def get_release_job_id(cls, machine_id: str) -> str:
        """
        获取延迟释放任务 ID

        Args:
            machine_id: 机器 ID

        Returns:
            str: 任务 ID，格式为 release_{machine_id}
        """
        return f"{cls.RELEASE_JOB_PREFIX}{machine_id}"

    @classmethod
    def _get_scheduler(cls):
        """获取调度器实例"""
        return scheduler_service.get_scheduler()

    @classmethod
    async def create_release_job(cls, machine_id: str) -> bool:
        """
        创建延迟释放任务

        在机器被申请时调用，创建一个 1 分钟后执行的一次性任务

        Args:
            machine_id: 机器 ID

        Returns:
            bool: 是否创建成功
        """
        scheduler = cls._get_scheduler()
        if not scheduler:
            logger.warning("调度器未初始化，无法创建延迟释放任务")
            return False

        try:
            job_id = cls.get_release_job_id(machine_id)
            run_time = datetime.now() + timedelta(minutes=cls.RELEASE_DELAY_MINUTES)

            # APScheduler 4.x: 先注册任务函数，再添加调度
            await scheduler.configure_task(job_id, func=cls._release_machine_job_wrapper)
            await scheduler.add_schedule(
                func_or_task_id=job_id,
                trigger=DateTrigger(run_date=run_time),
                id=job_id,
                args=[machine_id],
            )

            logger.info(f"创建延迟释放任务: {job_id}，执行时间: {run_time}")
            return True
        except Exception as e:
            logger.error(f"创建延迟释放任务失败 {machine_id}: {str(e)}")
            return False

    @classmethod
    async def modify_release_job(cls, machine_id: str) -> bool:
        """
        延迟释放任务的执行时间（keepusing 时调用）

        将任务的执行时间延迟到当前时间 + 1 分钟

        Args:
            machine_id: 机器 ID

        Returns:
            bool: 是否修改成功
        """
        scheduler = cls._get_scheduler()
        if not scheduler:
            logger.warning("调度器未初始化，无法修改延迟释放任务")
            return False

        try:
            job_id = cls.get_release_job_id(machine_id)
            new_run_time = datetime.now() + timedelta(minutes=cls.RELEASE_DELAY_MINUTES)

            # APScheduler 4.x: 先移除旧的调度，再添加新的
            try:
                await scheduler.remove_schedule(job_id)
            except JobLookupError:
                logger.debug(f"任务 {job_id} 不存在，将创建新任务")
                return await cls.create_release_job(machine_id)

            # 重新注册并添加调度
            await scheduler.configure_task(job_id, func=cls._release_machine_job_wrapper)
            await scheduler.add_schedule(
                func_or_task_id=job_id,
                trigger=DateTrigger(run_date=new_run_time),
                id=job_id,
                args=[machine_id],
            )

            logger.info(f"延迟释放任务已续期: {job_id}，新执行时间: {new_run_time}")
            return True
        except Exception as e:
            logger.error(f"修改延迟释放任务失败 {machine_id}: {str(e)}")
            return False

    @classmethod
    async def remove_release_job(cls, machine_id: str) -> bool:
        """
        取消延迟释放任务（释放时调用）

        Args:
            machine_id: 机器 ID

        Returns:
            bool: 是否取消成功
        """
        scheduler = cls._get_scheduler()
        if not scheduler:
            logger.warning("调度器未初始化，无法取消延迟释放任务")
            return False

        try:
            job_id = cls.get_release_job_id(machine_id)
            await scheduler.remove_schedule(job_id)
            logger.info(f"取消延迟释放任务: {job_id}")
            return True
        except JobLookupError:
            # 任务不存在，视为成功
            logger.debug(f"任务 {cls.get_release_job_id(machine_id)} 不存在，无需取消")
            return True
        except Exception as e:
            logger.error(f"取消延迟释放任务失败 {machine_id}: {str(e)}")
            return False

    @classmethod
    async def _release_machine_job_wrapper(cls, machine_id: str):
        """
        延迟释放任务包装函数

        APScheduler 调用的入口函数，处理异常和日志

        Args:
            machine_id: 机器 ID
        """
        try:
            await cls.release_machine_job(machine_id)
        except Exception as e:
            logger.error(f"延迟释放任务执行失败 {machine_id}: {str(e)}")

    @classmethod
    async def release_machine_job(cls, machine_id: str) -> None:
        """
        延迟释放任务执行逻辑

        检查机器状态：
        - 如果状态是 using，更新为 online
        - 如果状态是 offline，不变
        - 同步 Redis 缓存状态

        任务执行完毕自动删除（DateTrigger 特性）

        Args:
            machine_id: 机器 ID
        """
        logger.info(f"执行延迟释放任务: {machine_id}")

        async with AsyncSessionLocal() as db:
            # 查询机器当前状态
            stmt = select(EnvMachine).where(EnvMachine.id == machine_id)
            result = await db.execute(stmt)
            machine = result.scalar_one_or_none()

            if not machine:
                logger.warning(f"机器不存在: {machine_id}")
                return

            # 检查机器状态
            if machine.status == "using":
                # 状态是 using，更新为 online
                machine.status = "online"
                machine.last_keepusing_time = None
                await db.commit()
                logger.info(f"机器 {machine_id} 状态已从 using 更新为 online")

                # 同步 Redis 缓存（延迟导入避免循环依赖）
                from core.env_machine.pool_manager import EnvPoolManager
                await EnvPoolManager.sync_machine_to_cache(machine)

            elif machine.status == "offline":
                # 状态是 offline，不变
                logger.info(f"机器 {machine_id} 状态为 offline，跳过释放")
            else:
                # 其他状态（如已经是 online），记录日志
                logger.debug(f"机器 {machine_id} 状态为 {machine.status}，无需释放")


async def check_offline_machines(job_code: str = None, **kwargs) -> int:
    """
    离线检测任务

    检查 sync_time 超过 10 分钟的机器，标记为 offline

    Args:
        job_code: 任务编码（由调度器自动传入）
        **kwargs: 其他参数

    Returns:
        int: 检测到的离线机器数量
    """
    logger.info(f"[{job_code}] 执行离线检测任务")
    threshold = datetime.now() - timedelta(minutes=EnvMachineScheduler.OFFLINE_THRESHOLD_MINUTES)

    async with AsyncSessionLocal() as db:
        # 查询 sync_time 超过阈值的机器
        stmt = select(EnvMachine).where(
            EnvMachine.sync_time < threshold,
            EnvMachine.status.in_(["online", "using"]),
            EnvMachine.is_deleted == False,  # noqa: E712
        )
        result = await db.execute(stmt)
        machines = result.scalars().all()

        if not machines:
            logger.debug("未检测到离线机器")
            return 0

        offline_count = len(machines)
        machine_ids = []

        for machine in machines:
            # 取消延迟释放任务（如果有）
            await EnvMachineScheduler.remove_release_job(str(machine.id))

            # 更新状态
            machine.status = "offline"
            machine_ids.append(str(machine.id))
            logger.info(f"机器 {machine.id} 已标记为离线")

        await db.commit()

        # 批量同步 Redis 缓存（从缓存中移除）（延迟导入避免循环依赖）
        from core.env_machine.pool_manager import EnvPoolManager
        await EnvPoolManager.batch_sync_cache(db, machine_ids)

        logger.info(f"离线检测完成，共标记 {offline_count} 台机器为离线")
        return offline_count


async def _offline_check_job_wrapper():
    """离线检测任务包装函数"""
    try:
        await check_offline_machines()
    except Exception as e:
        logger.error(f"离线检测任务执行失败: {str(e)}")


async def setup_env_machine_scheduler() -> bool:
    """
    设置执行机定时任务

    - 注册离线检测周期任务

    Returns:
        bool: 是否设置成功
    """
    logger.info("开始设置执行机定时任务...")

    scheduler = scheduler_service.get_scheduler()
    if not scheduler:
        logger.warning("调度器未初始化，无法设置执行机定时任务")
        return False

    logger.info(f"调度器获取成功: {scheduler}")

    try:
        job_id = EnvMachineScheduler.OFFLINE_CHECK_JOB_ID

        # 注册任务函数
        logger.info(f"正在注册任务函数: {job_id}")
        await scheduler.configure_task(job_id, func=_offline_check_job_wrapper)
        logger.info(f"任务函数注册成功: {job_id}")

        # 添加周期调度（每 2 分钟执行一次）
        logger.info(f"正在添加周期调度，间隔: {EnvMachineScheduler.OFFLINE_CHECK_INTERVAL_MINUTES} 分钟")
        await scheduler.add_schedule(
            func_or_task_id=job_id,
            trigger=IntervalTrigger(minutes=EnvMachineScheduler.OFFLINE_CHECK_INTERVAL_MINUTES),
            id=job_id,
        )

        logger.info(f"离线检测任务已启动，间隔: {EnvMachineScheduler.OFFLINE_CHECK_INTERVAL_MINUTES} 分钟")
        return True
    except Exception as e:
        logger.error(f"设置执行机定时任务失败: {str(e)}", exc_info=True)
        return False


async def reset_using_machines() -> int:
    """
    重置所有 using 状态的机器为 online

    服务重启后，所有正在使用的机器应该恢复为在线状态，
    因为之前的任务已经丢失。

    Returns:
        int: 重置的机器数量
    """
    from app.database import AsyncSessionLocal
    from sqlalchemy import update

    async with AsyncSessionLocal() as db:
        # 批量更新 using -> online
        stmt = (
            update(EnvMachine)
            .where(EnvMachine.status == "using")
            .values(status="online", last_keepusing_time=None)
        )
        result = await db.execute(stmt)
        await db.commit()

        count = result.rowcount
        if count > 0:
            logger.info(f"已重置 {count} 台 using 状态的机器为 online")
        return count


# 导出便捷函数
async def create_release_job(machine_id: str) -> bool:
    """创建延迟释放任务"""
    return await EnvMachineScheduler.create_release_job(machine_id)


async def modify_release_job(machine_id: str) -> bool:
    """修改延迟释放任务"""
    return await EnvMachineScheduler.modify_release_job(machine_id)


async def remove_release_job(machine_id: str) -> bool:
    """移除延迟释放任务"""
    return await EnvMachineScheduler.remove_release_job(machine_id)