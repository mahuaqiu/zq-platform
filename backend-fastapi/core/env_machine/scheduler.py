#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2025-03-25
@File: scheduler.py
@Desc: 执行机定时任务管理器 - 延迟释放、离线检测、重启后状态重载
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List

import httpx
from apscheduler import JobLookupError, AsyncScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, update
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
    QUEUE_CLEANUP_JOB_ID = "env_machine_queue_cleanup"  # 队列清理任务 ID
    RELEASE_DELAY_MINUTES = 1  # 延迟释放时间（分钟）
    OFFLINE_THRESHOLD_MINUTES = 10  # 离线检测阈值（分钟）
    OFFLINE_CHECK_INTERVAL_MINUTES = 2  # 离线检测间隔（分钟）
    UPGRADE_TIMEOUT_MINUTES = 30  # 升级超时时间（分钟）
    QUEUE_CLEANUP_INTERVAL_HOURS = 24  # 队列清理间隔（小时）

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
                trigger=DateTrigger(run_time=run_time),
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
                trigger=DateTrigger(run_time=new_run_time),
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
        - 如果状态是 using，调用 pool_manager.release_machine 释放
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
                # 调用 pool_manager.release_machine 释放（会更新日志的 duration_minutes）
                from core.env_machine.pool_manager import EnvPoolManager
                success, error = await EnvPoolManager.release_machine(
                    db, machine_id, machine.namespace
                )
                if success:
                    logger.info(f"机器 {machine_id} 已释放，状态更新为 online")
                else:
                    logger.error(f"机器 {machine_id} 释放失败: {error}")

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
    同时检查 upgrading 状态超时 30 分钟的机器，标记为 offline

    Args:
        job_code: 任务编码（由调度器自动传入）
        **kwargs: 其他参数

    Returns:
        int: 检测到的离线机器数量
    """
    logger.info(f"[{job_code}] 执行离线检测任务")
    threshold = datetime.now() - timedelta(minutes=EnvMachineScheduler.OFFLINE_THRESHOLD_MINUTES)
    upgrade_threshold = datetime.now() - timedelta(minutes=EnvMachineScheduler.UPGRADE_TIMEOUT_MINUTES)

    async with AsyncSessionLocal() as db:
        # 查询 sync_time 超过阈值的 online/using 状态机器
        stmt = select(EnvMachine).where(
            EnvMachine.sync_time < threshold,
            EnvMachine.status.in_(["online", "using"]),
            EnvMachine.is_deleted == False,  # noqa: E712
        )
        result = await db.execute(stmt)
        machines = result.scalars().all()

        # 查询 upgrading 状态超时的机器
        upgrade_stmt = select(EnvMachine).where(
            EnvMachine.sync_time < upgrade_threshold,
            EnvMachine.status == "upgrading",
            EnvMachine.is_deleted == False,  # noqa: E712
        )
        upgrade_result = await db.execute(upgrade_stmt)
        upgrading_machines = upgrade_result.scalars().all()

        if not machines and not upgrading_machines:
            logger.debug("未检测到离线机器")
            return 0

        offline_count = len(machines) + len(upgrading_machines)
        machine_ids = []

        # 处理 online/using 状态超时的机器
        for machine in machines:
            # 取消延迟释放任务（如果有）
            await EnvMachineScheduler.remove_release_job(str(machine.id))

            # 更新状态
            machine.status = "offline"
            machine_ids.append(str(machine.id))
            logger.info(f"机器 {machine.id} 已标记为离线")

        # 处理 upgrading 状态超时的机器
        for machine in upgrading_machines:
            # 更新状态为 offline
            machine.status = "offline"
            machine_ids.append(str(machine.id))
            logger.warning(f"升级超时，机器置为离线: machine_id={machine.id}, ip={machine.ip}")

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


async def cleanup_upgrade_queue(job_code: str = None, **kwargs) -> dict:
    """
    升级队列清理任务

    清理工作：
    1. 清理 7 天前的 completed 记录
    2. 标记超时 24 小时的 waiting 为 failed

    Args:
        job_code: 任务编码（由调度器自动传入）
        **kwargs: 其他参数

    Returns:
        dict: 清理结果统计
    """
    logger.info(f"[{job_code}] 执行升级队列清理任务")

    async with AsyncSessionLocal() as db:
        # 延迟导入避免循环依赖
        from core.env_machine.upgrade_service import WorkerUpgradeQueueService

        # 清理 7 天前的 completed 记录
        completed_count = await WorkerUpgradeQueueService.cleanup_completed(db, days=7)
        if completed_count > 0:
            logger.info(f"已清理 {completed_count} 条已完成的升级记录")

        # 标记超时 24 小时的 waiting 为 failed
        timeout_count = await WorkerUpgradeQueueService.mark_timeout_waiting(db, hours=24)
        if timeout_count > 0:
            logger.warning(f"已标记 {timeout_count} 条超时等待的升级记录为失败")

        logger.info(f"队列清理完成，清理 {completed_count} 条完成记录，标记 {timeout_count} 条超时记录")
        return {
            "completed_cleaned": completed_count,
            "timeout_marked": timeout_count,
        }


async def _queue_cleanup_job_wrapper():
    """队列清理任务包装函数"""
    try:
        await cleanup_upgrade_queue()
    except Exception as e:
        logger.error(f"队列清理任务执行失败: {str(e)}")


async def setup_env_machine_scheduler() -> bool:
    """
    设置执行机定时任务

    - 注册离线检测周期任务
    - 注册队列清理周期任务

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
        # 注册离线检测任务
        offline_job_id = EnvMachineScheduler.OFFLINE_CHECK_JOB_ID
        logger.info(f"正在注册离线检测任务函数: {offline_job_id}")
        await scheduler.configure_task(offline_job_id, func=_offline_check_job_wrapper)
        logger.info(f"任务函数注册成功: {offline_job_id}")

        # 添加离线检测周期调度（每 2 分钟执行一次）
        logger.info(f"正在添加离线检测周期调度，间隔: {EnvMachineScheduler.OFFLINE_CHECK_INTERVAL_MINUTES} 分钟")
        await scheduler.add_schedule(
            func_or_task_id=offline_job_id,
            trigger=IntervalTrigger(minutes=EnvMachineScheduler.OFFLINE_CHECK_INTERVAL_MINUTES),
            id=offline_job_id,
        )
        logger.info(f"离线检测任务已启动，间隔: {EnvMachineScheduler.OFFLINE_CHECK_INTERVAL_MINUTES} 分钟")

        # 注册队列清理任务
        cleanup_job_id = EnvMachineScheduler.QUEUE_CLEANUP_JOB_ID
        logger.info(f"正在注册队列清理任务函数: {cleanup_job_id}")
        await scheduler.configure_task(cleanup_job_id, func=_queue_cleanup_job_wrapper)
        logger.info(f"任务函数注册成功: {cleanup_job_id}")

        # 添加队列清理周期调度（每 24 小时执行一次）
        logger.info(f"正在添加队列清理周期调度，间隔: {EnvMachineScheduler.QUEUE_CLEANUP_INTERVAL_HOURS} 小时")
        await scheduler.add_schedule(
            func_or_task_id=cleanup_job_id,
            trigger=IntervalTrigger(hours=EnvMachineScheduler.QUEUE_CLEANUP_INTERVAL_HOURS),
            id=cleanup_job_id,
        )
        logger.info(f"队列清理任务已启动，间隔: {EnvMachineScheduler.QUEUE_CLEANUP_INTERVAL_HOURS} 小时")

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


async def _check_single_worker(
    client: httpx.AsyncClient,
    worker_key: str,
    worker_machines: List[EnvMachine],
) -> tuple[str, List[EnvMachine], bool, Optional[Dict]]:
    """
    检查单个 Worker 的状态

    Args:
        client: HTTP 客户端
        worker_key: Worker 标识 (ip:port)
        worker_machines: 该 Worker 下的所有机器

    Returns:
        tuple: (worker_key, worker_machines, success, response_data)
    """
    ip = worker_machines[0].ip
    port = worker_machines[0].port
    url = f"http://{ip}:{port}/worker_devices"

    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            data = resp.json()
            return (worker_key, worker_machines, True, data)
        else:
            logger.warning(f"Worker {worker_key} 返回异常状态码: {resp.status_code}")
            return (worker_key, worker_machines, False, None)

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.warning(f"Worker {worker_key} 连接失败: {type(e).__name__}")
        return (worker_key, worker_machines, False, None)

    except Exception as e:
        logger.error(f"Worker {worker_key} 访问异常: {str(e)}")
        return (worker_key, worker_machines, False, None)


async def reload_machine_status_after_restart() -> Dict:
    """
    服务重启后重载机器状态

    延迟10秒后执行，遍历所有机器，主动访问每台设备的/worker_devices接口验证状态。
    - 访问成功：更新设备状态为 online，刷新缓存
    - 访问失败：更新设备状态为 offline，从缓存移除

    Returns:
        Dict: 重载结果统计 {"online_count": N, "offline_count": M, "total": T}
    """
    logger.info("开始执行重启后机器状态重载...")

    # 等待10秒，让服务完全启动
    await asyncio.sleep(10)

    async with AsyncSessionLocal() as db:
        # 查询所有机器（不包括已删除的）
        stmt = select(EnvMachine).where(
            EnvMachine.is_deleted == False,  # noqa: E712
        )
        result = await db.execute(stmt)
        machines = result.scalars().all()

        if not machines:
            logger.info("没有机器需要重载")
            return {"online_count": 0, "offline_count": 0, "total": 0}

        # 按 IP+Port 分组（避免重复请求同一台 Worker）
        worker_groups: Dict[str, List[EnvMachine]] = {}
        for machine in machines:
            key = f"{machine.ip}:{machine.port}"
            if key not in worker_groups:
                worker_groups[key] = []
            worker_groups[key].append(machine)

        total_machines = len(machines)
        online_count = 0
        offline_count = 0
        machine_ids_to_update: List[str] = []

        logger.info(f"准备重载 {total_machines} 台机器，涉及 {len(worker_groups)} 个 Worker")

        # 并发访问所有 Worker
        async with httpx.AsyncClient(timeout=5.0, trust_env=True, verify=False) as client:
            # 创建并发任务
            tasks = [
                _check_single_worker(client, worker_key, worker_machines)
                for worker_key, worker_machines in worker_groups.items()
            ]
            results = await asyncio.gather(*tasks)

        # 处理结果
        now = datetime.now()
        for worker_key, worker_machines, success, data in results:
            if success and data:
                devices = data.get("devices", {})
                namespace = data.get("namespace", "")
                version = data.get("version")
                config_version = data.get("config_version")

                for machine in worker_machines:
                    device_type = machine.device_type
                    if device_type in ("windows", "mac"):
                        # Windows/Mac 不需要检查 device_sn
                        machine.status = "online"
                        machine.sync_time = now
                        machine.namespace = namespace or machine.namespace
                        if version:
                            machine.version = version
                        if config_version:
                            machine.config_version = config_version
                        online_count += 1
                        machine_ids_to_update.append(str(machine.id))
                    elif device_type in ("android", "ios"):
                        # 移动端需要检查 device_sn 是否在列表中
                        # 支持两种格式：字符串列表 ["udid1"] 或对象列表 [{"udid": "udid1"}]
                        device_items = devices.get(device_type, [])
                        device_sns = []
                        for item in device_items:
                            if isinstance(item, dict):
                                device_sns.append(item.get("udid"))
                            elif isinstance(item, str):
                                device_sns.append(item)

                        if machine.device_sn in device_sns:
                            machine.status = "online"
                            machine.sync_time = now
                            machine.namespace = namespace or machine.namespace
                            if version:
                                machine.version = version
                            if config_version:
                                machine.config_version = config_version
                            online_count += 1
                            machine_ids_to_update.append(str(machine.id))
                        else:
                            # 设备不在列表中，标记为 offline
                            machine.status = "offline"
                            offline_count += 1
                            machine_ids_to_update.append(str(machine.id))

                logger.info(f"Worker {worker_key} 访问成功，更新 {len(worker_machines)} 台机器")

            else:
                # 访问失败，标记为 offline
                for machine in worker_machines:
                    machine.status = "offline"
                    offline_count += 1
                    machine_ids_to_update.append(str(machine.id))

        # 提交数据库更改
        await db.commit()

        # 批量同步 Redis 缓存
        from core.env_machine.pool_manager import EnvPoolManager
        await EnvPoolManager.batch_sync_cache(db, machine_ids_to_update)

        result = {
            "online_count": online_count,
            "offline_count": offline_count,
            "total": total_machines,
        }
        logger.info(f"重启后机器状态重载完成: online={online_count}, offline={offline_count}, total={total_machines}")

        return result