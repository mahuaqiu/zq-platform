#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time: 2026-04-10
@File: upgrade_service.py
@Desc: Worker 升级管理服务层
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.env_machine.model import EnvMachine
from core.env_machine.upgrade_model import WorkerUpgradeConfig, WorkerUpgradeQueue
from core.env_machine.upgrade_schema import (
    UpgradeDetail,
    BatchUpgradeResponse,
    UpgradeQueueItem,
)

logger = logging.getLogger(__name__)

# Worker 升级接口超时时间（秒）
WORKER_UPGRADE_TIMEOUT = 10


class WorkerUpgradeConfigService:
    """升级配置服务"""

    @staticmethod
    async def get_all(db: AsyncSession) -> List[WorkerUpgradeConfig]:
        """获取所有配置"""
        result = await db.execute(
            select(WorkerUpgradeConfig).where(WorkerUpgradeConfig.is_deleted == False)
        )
        return result.scalars().all()

    @staticmethod
    async def get_by_device_type(db: AsyncSession, device_type: str) -> Optional[WorkerUpgradeConfig]:
        """根据设备类型获取配置"""
        result = await db.execute(
            select(WorkerUpgradeConfig).where(
                and_(
                    WorkerUpgradeConfig.device_type == device_type,
                    WorkerUpgradeConfig.is_deleted == False
                )
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update(db: AsyncSession, config_id: str, version: str, download_url: str, note: Optional[str] = None) -> WorkerUpgradeConfig:
        """更新配置"""
        result = await db.execute(
            select(WorkerUpgradeConfig).where(WorkerUpgradeConfig.id == config_id)
        )
        config = result.scalar_one_or_none()
        if config:
            config.version = version
            config.download_url = download_url
            config.note = note
            await db.commit()
            await db.refresh(config)
        return config


class WorkerUpgradeQueueService:
    """升级队列服务"""

    @staticmethod
    async def get_waiting_by_machine_id(db: AsyncSession, machine_id: str) -> Optional[WorkerUpgradeQueue]:
        """获取机器的等待队列项"""
        result = await db.execute(
            select(WorkerUpgradeQueue).where(
                and_(
                    WorkerUpgradeQueue.machine_id == machine_id,
                    WorkerUpgradeQueue.status == "waiting",
                    WorkerUpgradeQueue.is_deleted == False
                )
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def add_to_queue(db: AsyncSession, machine_id: str, target_version: str, device_type: str, namespace: str) -> WorkerUpgradeQueue:
        """添加到队列"""
        queue_item = WorkerUpgradeQueue(
            machine_id=machine_id,
            target_version=target_version,
            device_type=device_type,
            namespace=namespace,
            status="waiting",
            created_at=datetime.now(),
        )
        db.add(queue_item)
        await db.commit()
        await db.refresh(queue_item)
        return queue_item

    @staticmethod
    async def mark_completed(db: AsyncSession, queue_id: str) -> None:
        """标记为完成"""
        result = await db.execute(
            select(WorkerUpgradeQueue).where(WorkerUpgradeQueue.id == queue_id)
        )
        item = result.scalar_one_or_none()
        if item:
            item.status = "completed"
            item.completed_at = datetime.now()
            await db.commit()

    @staticmethod
    async def get_list(db: AsyncSession, namespace: Optional[str] = None, status: Optional[str] = None) -> Tuple[List[WorkerUpgradeQueue], int]:
        """获取队列列表"""
        conditions = [WorkerUpgradeQueue.is_deleted == False]
        if namespace:
            conditions.append(WorkerUpgradeQueue.namespace == namespace)
        if status:
            conditions.append(WorkerUpgradeQueue.status == status)

        result = await db.execute(
            select(WorkerUpgradeQueue).where(and_(*conditions)).order_by(WorkerUpgradeQueue.created_at.desc())
        )
        items = result.scalars().all()
        return items, len(items)

    @staticmethod
    async def delete_by_id(db: AsyncSession, queue_id: str) -> bool:
        """删除队列项"""
        result = await db.execute(
            select(WorkerUpgradeQueue).where(WorkerUpgradeQueue.id == queue_id)
        )
        item = result.scalar_one_or_none()
        if item and item.status == "waiting":
            item.is_deleted = True
            await db.commit()
            return True
        return False

    @staticmethod
    async def cleanup_completed(db: AsyncSession, days: int = 7) -> int:
        """清理 completed 记录"""
        threshold = datetime.now() - timedelta(days=days)
        result = await db.execute(
            select(WorkerUpgradeQueue).where(
                and_(
                    WorkerUpgradeQueue.status == "completed",
                    WorkerUpgradeQueue.completed_at < threshold
                )
            )
        )
        items = result.scalars().all()
        count = 0
        for item in items:
            item.is_deleted = True
            count += 1
        await db.commit()
        return count

    @staticmethod
    async def mark_timeout_waiting(db: AsyncSession, hours: int = 24) -> int:
        """标记超时的 waiting 为 failed"""
        threshold = datetime.now() - timedelta(hours=hours)
        result = await db.execute(
            select(WorkerUpgradeQueue).where(
                and_(
                    WorkerUpgradeQueue.status == "waiting",
                    WorkerUpgradeQueue.created_at < threshold
                )
            )
        )
        items = result.scalars().all()
        count = 0
        for item in items:
            item.status = "failed"
            count += 1
        await db.commit()
        return count


async def send_upgrade_to_worker(machine: EnvMachine, version: str, download_url: str) -> Tuple[bool, str, str]:
    """调用 Worker 升级接口

    返回: (是否成功, 消息, machine_id)
    """
    url = f"http://{machine.ip}:{machine.port}/worker/upgrade"
    payload = {
        "version": version,
        "download_url": download_url,
    }

    try:
        async with httpx.AsyncClient(timeout=WORKER_UPGRADE_TIMEOUT, trust_env=True, verify=False) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "upgrading":
                    return True, "升级指令已下发", machine.id
                else:
                    return False, f"Worker 返回异常状态: {data.get('status')}", machine.id
            else:
                return False, f"Worker 返回错误状态码: {response.status_code}", machine.id
    except httpx.TimeoutException:
        return False, "Worker 响应超时", machine.id
    except Exception as e:
        logger.error(f"调用 Worker 升级接口失败: {e}")
        return False, f"网络错误: {str(e)}", machine.id


class UpgradeService:
    """升级管理服务"""

    @staticmethod
    async def batch_upgrade(
        db: AsyncSession,
        machine_ids: Optional[List[str]] = None,
        namespace: Optional[str] = None,
        device_type: Optional[str] = None,
    ) -> BatchUpgradeResponse:
        """批量升级（并发调用）"""
        # 获取版本配置
        configs = await WorkerUpgradeConfigService.get_all(db)
        config_map = {c.device_type: c for c in configs}

        # 查询机器
        conditions = [EnvMachine.is_deleted == False, EnvMachine.available == True]
        if machine_ids:
            conditions.append(EnvMachine.id.in_(machine_ids))
        if namespace:
            conditions.append(EnvMachine.namespace == namespace)
        if device_type:
            conditions.append(EnvMachine.device_type == device_type)

        result = await db.execute(select(EnvMachine).where(and_(*conditions)))
        machines = result.scalars().all()

        response = BatchUpgradeResponse()

        # 收集需要并发升级的机器信息
        upgrade_tasks = []  # 存储并发任务
        upgrade_machine_map = {}  # machine_id -> (machine, config)

        for machine in machines:
            config = config_map.get(machine.device_type)
            if not config:
                response.skipped_count += 1
                response.details.append(UpgradeDetail(
                    machine_id=machine.id,
                    ip=machine.ip,
                    status="skipped",
                    message="未找到对应设备类型的升级配置"
                ))
                continue

            # 版本比对
            if machine.version and machine.version >= config.version:
                response.skipped_count += 1
                response.details.append(UpgradeDetail(
                    machine_id=machine.id,
                    ip=machine.ip,
                    status="skipped",
                    message="已是最新版本"
                ))
                continue

            # 状态判断
            if machine.status == "online":
                # 收集并发任务
                upgrade_tasks.append(send_upgrade_to_worker(machine, config.version, config.download_url))
                upgrade_machine_map[machine.id] = (machine, config)

            elif machine.status == "using":
                # 加入队列
                await WorkerUpgradeQueueService.add_to_queue(
                    db, machine.id, config.version, machine.device_type, machine.namespace
                )
                response.waiting_count += 1
                response.details.append(UpgradeDetail(
                    machine_id=machine.id,
                    ip=machine.ip,
                    status="waiting",
                    message="机器使用中，已加入升级队列"
                ))

            else:
                # offline, upgrading 状态跳过
                response.skipped_count += 1
                response.details.append(UpgradeDetail(
                    machine_id=machine.id,
                    ip=machine.ip,
                    status="skipped",
                    message=f"机器状态为 {machine.status}，无法升级"
                ))

        # 并发调用所有 Worker 升级接口
        if upgrade_tasks:
            logger.info(f"并发升级 {len(upgrade_tasks)} 台机器")
            results = await asyncio.gather(*upgrade_tasks, return_exceptions=True)

            # 处理并发结果
            for task_result in results:
                if isinstance(task_result, Exception):
                    # 异常情况（理论上不应该发生，因为 send_upgrade_to_worker 捕获了所有异常）
                    logger.error(f"并发任务异常: {task_result}")
                    response.failed_count += 1
                    continue

                success, message, machine_id = task_result
                machine, config = upgrade_machine_map[machine_id]

                if success:
                    machine.status = "upgrading"
                    response.upgraded_count += 1
                    response.details.append(UpgradeDetail(
                        machine_id=machine.id,
                        ip=machine.ip,
                        status="upgraded",
                        message=message
                    ))
                else:
                    response.failed_count += 1
                    response.details.append(UpgradeDetail(
                        machine_id=machine.id,
                        ip=machine.ip,
                        status="failed",
                        message=message
                    ))

        await db.commit()
        return response

    @staticmethod
    async def get_preview(db: AsyncSession, namespace: Optional[str] = None, device_type: Optional[str] = None, ip: Optional[str] = None) -> dict:
        """获取升级预览"""
        configs = await WorkerUpgradeConfigService.get_all(db)
        config_map = {c.device_type: c for c in configs}

        conditions = [EnvMachine.is_deleted == False, EnvMachine.available == True]
        if namespace:
            conditions.append(EnvMachine.namespace == namespace)
        if device_type:
            conditions.append(EnvMachine.device_type == device_type)
        if ip:
            conditions.append(EnvMachine.ip.contains(ip))

        result = await db.execute(select(EnvMachine).where(and_(*conditions)))
        machines = result.scalars().all()

        upgradable = []
        waiting = []
        latest = []
        offline = []

        for machine in machines:
            config = config_map.get(machine.device_type)
            upgrade_status = "待升级"

            if not config:
                upgrade_status = "无配置"
            elif machine.version and machine.version >= config.version:
                upgrade_status = "已最新"
            elif machine.status == "online":
                upgrade_status = "待升级"
            elif machine.status == "using":
                upgrade_status = "待队列"
            elif machine.status == "upgrading":
                upgrade_status = "升级中"
            else:
                upgrade_status = "离线"

            machine_info = {
                "id": machine.id,
                "ip": machine.ip,
                "device_type": machine.device_type,
                "version": machine.version or "-",
                "status": machine.status,
                "upgrade_status": upgrade_status,
            }

            if upgrade_status == "待升级":
                upgradable.append(machine_info)
            elif upgrade_status == "待队列":
                waiting.append(machine_info)
            elif upgrade_status in ["已最新", "升级中"]:
                latest.append(machine_info)
            else:
                offline.append(machine_info)

        return {
            "upgradable_count": len(upgradable),
            "waiting_count": len(waiting),
            "latest_count": len(latest),
            "offline_count": len(offline),
            "machines": upgradable + waiting + latest + offline,
        }