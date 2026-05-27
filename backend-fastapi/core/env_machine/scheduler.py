#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2025-03-25
@File: scheduler.py
@Desc: 执行机定时任务管理器 - 离线检测、超时释放检测、重启后状态重载
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List

import httpx
from apscheduler import JobLookupError, AsyncScheduler
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
    1. 离线检测任务：周期性检测 sync_time 超时的机器
    2. 超时释放检测：周期性检测 last_keepusing_time 超时的 using 状态机器
    """

    OFFLINE_CHECK_JOB_ID = "env_machine_offline_check"  # 离线检测任务 ID
    QUEUE_CLEANUP_JOB_ID = "env_machine_queue_cleanup"  # 队列清理任务 ID
    TIMEOUT_CHECK_JOB_ID = "env_machine_timeout_check"  # 超时释放检测任务 ID
    OFFLINE_THRESHOLD_MINUTES = 10  # 离线检测阈值（分钟）
    OFFLINE_CHECK_INTERVAL_MINUTES = 2  # 离线检测间隔（分钟）
    TIMEOUT_THRESHOLD_MINUTES = 2  # 超时释放阈值（分钟）
    UPGRADE_TIMEOUT_MINUTES = 30  # 升级超时时间（分钟）
    QUEUE_CLEANUP_INTERVAL_HOURS = 24  # 队列清理间隔（小时）

    @classmethod
    def _get_scheduler(cls):
        """获取调度器实例"""
        return scheduler_service.get_scheduler()


async def check_timeout_machines(job_code: str = None, **kwargs) -> int:
    """
    使用超时检测任务

    检测 last_keepusing_time 超过 2 分钟的 using 状态机器，自动释放

    Args:
        job_code: 任务编码（由调度器自动传入）
        **kwargs: 其他参数

    Returns:
        int: 释放的机器数量
    """
    logger.info(f"[{job_code}] 执行使用超时检测任务")
    threshold = datetime.now() - timedelta(minutes=EnvMachineScheduler.TIMEOUT_THRESHOLD_MINUTES)

    async with AsyncSessionLocal() as db:
        # 查询 last_keepusing_time 超过阈值的 using 状态机器
        stmt = select(EnvMachine).where(
            EnvMachine.status == "using",
            EnvMachine.last_keepusing_time < threshold,
            EnvMachine.is_deleted == False,  # noqa: E712
        )
        result = await db.execute(stmt)
        machines = result.scalars().all()

        if not machines:
            logger.debug("未检测到超时的使用机器")
            return 0

        release_count = len(machines)
        machine_ids = []

        # 批量释放机器
        from core.env_machine.pool_manager import EnvPoolManager
        for machine in machines:
            success, error = await EnvPoolManager.release_machine(
                db, str(machine.id), machine.namespace
            )
            if success:
                machine_ids.append(str(machine.id))
                logger.info(f"超时释放机器: {machine.id}")
            else:
                logger.error(f"超时释放机器失败: {machine.id}, error={error}")

        logger.info(f"使用超时检测完成，共释放 {release_count} 台机器")
        return release_count


async def _timeout_check_job_wrapper():
    """超时释放检测任务包装函数"""
    try:
        await check_timeout_machines()
    except Exception as e:
        logger.error(f"超时释放检测任务执行失败: {str(e)}")


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
        # 排除 Linux 设备：Linux 设备没有心跳机制，不参与离线检测
        stmt = select(EnvMachine).where(
            EnvMachine.sync_time < threshold,
            EnvMachine.status.in_(["online", "using"]),
            EnvMachine.is_deleted == False,  # noqa: E712
            EnvMachine.is_virtual == False,
            EnvMachine.device_type != 'linux',  # 排除 Linux 设备
        )
        result = await db.execute(stmt)
        machines = result.scalars().all()

        # 查询 upgrading 状态超时的机器
        # 排除 Linux 设备：Linux 设备不支持升级操作
        upgrade_stmt = select(EnvMachine).where(
            EnvMachine.sync_time < upgrade_threshold,
            EnvMachine.status == "upgrading",
            EnvMachine.is_deleted == False,  # noqa: E712
            EnvMachine.is_virtual == False,
            EnvMachine.device_type != 'linux',  # 排除 Linux 设备
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

        # 标记超时 30 分钟的 processing 为 failed（下发过程中异常）
        processing_timeout_count = await WorkerUpgradeQueueService.mark_timeout_processing(db, minutes=30)
        if processing_timeout_count > 0:
            logger.warning(f"已标记 {processing_timeout_count} 条 processing 状态超时的升级记录为失败")

        # 标记超时 24 小时的 waiting 为 failed
        timeout_count = await WorkerUpgradeQueueService.mark_timeout_waiting(db, hours=24)
        if timeout_count > 0:
            logger.warning(f"已标记 {timeout_count} 条超时等待的升级记录为失败")

        logger.info(f"队列清理完成，清理 {completed_count} 条完成记录，标记 {processing_timeout_count} 条 processing 超时记录，标记 {timeout_count} 条 waiting 超时记录")
        return {
            "completed_cleaned": completed_count,
            "processing_timeout_marked": processing_timeout_count,
            "waiting_timeout_marked": timeout_count,
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

    限流策略：每次最多请求10个 Worker，成功后才继续请求下一批。

    Returns:
        Dict: 重载结果统计 {"online_count": N, "offline_count": M, "total": T}
    """
    logger.info("开始执行重启后机器状态重载...")

    # 等待10秒，让服务完全启动
    await asyncio.sleep(10)

    async with AsyncSessionLocal() as db:
        # 查询所有机器（不包括已删除的、虚拟设备和 Linux 设备）
        # Linux 设备没有 worker，不支持重载操作
        stmt = select(EnvMachine).where(
            EnvMachine.is_deleted == False,  # noqa: E712
            EnvMachine.is_virtual == False,
            EnvMachine.device_type != 'linux',  # 排除 Linux 设备
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

        # 限流策略：每次最多请求10个 Worker
        BATCH_SIZE = 10
        worker_items = list(worker_groups.items())
        total_batches = (len(worker_items) + BATCH_SIZE - 1) // BATCH_SIZE

        async with httpx.AsyncClient(timeout=5.0, trust_env=False, verify=False) as client:
            for batch_idx in range(total_batches):
                start_idx = batch_idx * BATCH_SIZE
                end_idx = min(start_idx + BATCH_SIZE, len(worker_items))
                batch_items = worker_items[start_idx:end_idx]

                logger.info(f"正在处理第 {batch_idx + 1}/{total_batches} 批 Worker，共 {len(batch_items)} 个")

                # 创建当前批次的并发任务
                tasks = [
                    _check_single_worker(client, worker_key, worker_machines)
                    for worker_key, worker_machines in batch_items
                ]
                results = await asyncio.gather(*tasks)

                # 处理当前批次结果
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

                # 当前批次处理完成后，继续下一批
                logger.info(f"第 {batch_idx + 1}/{total_batches} 批处理完成")

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