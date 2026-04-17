#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: Claude
@Time: 2026-04-04
@File: log_service.py
@Desc: 执行机申请日志服务
"""
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import select, func, and_, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.env_machine.log_model import EnvMachineLog
from core.env_machine.log_schema import (
    EnvMachineLogCreate,
    EnvMachineLogUpdate,
    DeviceStats,
    DeviceTypeStats,
    Apply24hStats,
    TopTagItem,
    TopDurationItem,
    OfflineMachineItem,
)
from core.env_machine.model import EnvMachine


class EnvMachineLogService:
    """执行机申请日志服务"""

    @classmethod
    async def create_log(
        cls,
        db: AsyncSession,
        data: EnvMachineLogCreate
    ) -> EnvMachineLog:
        """创建申请日志"""
        log = EnvMachineLog(**data.model_dump())
        db.add(log)
        await db.flush()
        return log

    @classmethod
    async def update_log(
        cls,
        db: AsyncSession,
        log_id: str,
        data: EnvMachineLogUpdate
    ) -> Optional[EnvMachineLog]:
        """更新申请日志（释放时使用）"""
        result = await db.execute(
            select(EnvMachineLog).where(EnvMachineLog.id == log_id)
        )
        log = result.scalar_one_or_none()
        if log:
            for key, value in data.model_dump(exclude_unset=True).items():
                setattr(log, key, value)
        return log

    @classmethod
    async def get_latest_apply_log(
        cls,
        db: AsyncSession,
        machine_id: str
    ) -> Optional[EnvMachineLog]:
        """获取机器最新的申请日志（未释放的）"""
        result = await db.execute(
            select(EnvMachineLog)
            .where(
                EnvMachineLog.machine_id == machine_id,
                EnvMachineLog.action == "apply",
                EnvMachineLog.result == "success",
                EnvMachineLog.release_time.is_(None)
            )
            .order_by(EnvMachineLog.apply_time.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def cleanup_old_logs(
        cls,
        db: AsyncSession,
        days: int = 7
    ) -> int:
        """清理指定天数前的日志"""
        cutoff = datetime.now() - timedelta(days=days)
        stmt = delete(EnvMachineLog).where(
            EnvMachineLog.sys_create_datetime < cutoff
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount

    # ============ 统计方法 ============

    @classmethod
    async def get_device_stats(
        cls,
        db: AsyncSession,
        namespaces: Optional[List[str]] = None
    ) -> DeviceStats:
        """获取设备统计"""
        # 基础查询条件
        base_filter = [EnvMachine.is_deleted.is_(False)]
        if namespaces:
            base_filter.append(EnvMachine.namespace.in_(namespaces))

        # 总数统计
        total_result = await db.execute(
            select(func.count(EnvMachine.id)).where(*base_filter)
        )
        total = total_result.scalar() or 0

        # 在线/离线统计
        online_result = await db.execute(
            select(func.count(EnvMachine.id)).where(
                *base_filter,
                EnvMachine.status == "online"
            )
        )
        online = online_result.scalar() or 0

        offline_result = await db.execute(
            select(func.count(EnvMachine.id)).where(
                *base_filter,
                EnvMachine.status == "offline"
            )
        )
        offline = offline_result.scalar() or 0

        # 按类型统计
        type_stats = []
        device_types = ["windows", "mac", "android", "ios"]
        for dt in device_types:
            type_total_result = await db.execute(
                select(func.count(EnvMachine.id)).where(
                    *base_filter,
                    EnvMachine.device_type == dt
                )
            )
            type_total = type_total_result.scalar() or 0

            type_enabled_result = await db.execute(
                select(func.count(EnvMachine.id)).where(
                    *base_filter,
                    EnvMachine.device_type == dt,
                    EnvMachine.available.is_(True)
                )
            )
            type_enabled = type_enabled_result.scalar() or 0

            type_stats.append(DeviceTypeStats(
                type=dt,
                total=type_total,
                enabled=type_enabled,
                disabled=type_total - type_enabled
            ))

        return DeviceStats(
            total=total,
            online=online,
            offline=offline,
            by_type=type_stats
        )

    @classmethod
    async def get_apply_24h_stats(
        cls,
        db: AsyncSession,
        namespaces: Optional[List[str]] = None
    ) -> Apply24hStats:
        """获取24小时申请统计"""
        cutoff = datetime.now() - timedelta(hours=24)

        filters = [
            EnvMachineLog.action == "apply",
            EnvMachineLog.sys_create_datetime >= cutoff
        ]
        if namespaces:
            filters.append(EnvMachineLog.namespace.in_(namespaces))

        # 总数
        total_result = await db.execute(
            select(func.count(EnvMachineLog.id)).where(*filters)
        )
        total = total_result.scalar() or 0

        # 成功数
        success_result = await db.execute(
            select(func.count(EnvMachineLog.id)).where(
                *filters,
                EnvMachineLog.result == "success"
            )
        )
        success = success_result.scalar() or 0

        # 资源不足数（失败原因为 "env not enough"）
        failed_result = await db.execute(
            select(func.count(EnvMachineLog.id)).where(
                *filters,
                EnvMachineLog.result == "fail",
                EnvMachineLog.fail_reason == "env not enough"
            )
        )
        failed = failed_result.scalar() or 0

        return Apply24hStats(total=total, success=success, failed=failed)

    @classmethod
    async def get_top10_tags(
        cls,
        db: AsyncSession,
        namespaces: Optional[List[str]] = None
    ) -> List[TopTagItem]:
        """获取24小时内申请次数TOP10标签（仅成功）"""
        cutoff = datetime.now() - timedelta(hours=24)

        filters = [
            EnvMachineLog.action == "apply",
            EnvMachineLog.result == "success",
            EnvMachineLog.sys_create_datetime >= cutoff,
            EnvMachineLog.mark.isnot(None)
        ]
        if namespaces:
            filters.append(EnvMachineLog.namespace.in_(namespaces))

        result = await db.execute(
            select(
                EnvMachineLog.mark,
                func.count(EnvMachineLog.id).label("count")
            )
            .where(*filters)
            .group_by(EnvMachineLog.mark)
            .order_by(func.count(EnvMachineLog.id).desc())
            .limit(10)
        )

        return [TopTagItem(tag=row[0], count=row[1]) for row in result.all()]

    @classmethod
    async def get_top20_duration(
        cls,
        db: AsyncSession,
        namespaces: Optional[List[str]] = None
    ) -> List[TopDurationItem]:
        """获取占用时长TOP20机器（仅统计已释放的记录）"""
        cutoff = datetime.now() - timedelta(hours=24)

        filters = [
            EnvMachineLog.action == "apply",
            EnvMachineLog.result == "success",
            EnvMachineLog.sys_create_datetime >= cutoff,
            EnvMachineLog.duration_minutes.isnot(None)
        ]
        if namespaces:
            filters.append(EnvMachineLog.namespace.in_(namespaces))

        result = await db.execute(
            select(
                EnvMachineLog.ip,
                EnvMachineLog.device_sn,
                EnvMachineLog.device_type,
                func.sum(EnvMachineLog.duration_minutes).label("total_minutes")
            )
            .where(*filters)
            .group_by(EnvMachineLog.ip, EnvMachineLog.device_sn, EnvMachineLog.device_type)
            .order_by(func.sum(EnvMachineLog.duration_minutes).desc())
            .limit(20)
        )

        items = []
        for row in result.all():
            duration_minutes = row[3] or 0
            if duration_minutes >= 60:
                duration_display = f"{duration_minutes // 60}h"
            else:
                duration_display = f"{duration_minutes}m"

            items.append(TopDurationItem(
                ip=row[0],
                device_sn=row[1],
                device_type=row[2],
                duration_minutes=duration_minutes,
                duration_display=duration_display
            ))

        return items

    @classmethod
    async def get_top10_insufficient(
        cls,
        db: AsyncSession,
        namespaces: Optional[List[str]] = None
    ) -> List[TopTagItem]:
        """获取24小时内资源不足TOP10标签"""
        cutoff = datetime.now() - timedelta(hours=24)

        filters = [
            EnvMachineLog.action == "apply",
            EnvMachineLog.result == "fail",
            EnvMachineLog.fail_reason == "env not enough",
            EnvMachineLog.sys_create_datetime >= cutoff,
            EnvMachineLog.mark.isnot(None)
        ]
        if namespaces:
            filters.append(EnvMachineLog.namespace.in_(namespaces))

        result = await db.execute(
            select(
                EnvMachineLog.mark,
                func.count(EnvMachineLog.id).label("count")
            )
            .where(*filters)
            .group_by(EnvMachineLog.mark)
            .order_by(func.count(EnvMachineLog.id).desc())
            .limit(10)
        )

        return [TopTagItem(tag=row[0], count=row[1]) for row in result.all()]

    @classmethod
    async def get_offline_machines(
        cls,
        db: AsyncSession,
        namespaces: Optional[List[str]] = None
    ) -> List[OfflineMachineItem]:
        """获取启用但离线的机器列表"""
        filters = [
            EnvMachine.is_deleted.is_(False),
            EnvMachine.available.is_(True),
            EnvMachine.status == "offline"
        ]
        if namespaces:
            filters.append(EnvMachine.namespace.in_(namespaces))

        result = await db.execute(
            select(EnvMachine).where(*filters)
        )
        machines = result.scalars().all()

        items = []
        for m in machines:
            # 计算离线时长
            if m.sync_time:
                delta = datetime.now() - m.sync_time
                if delta.days > 0:
                    offline_duration = f"{delta.days}天"
                elif delta.seconds >= 3600:
                    offline_duration = f"{delta.seconds // 3600}小时"
                else:
                    offline_duration = f"{delta.seconds // 60}分钟"
            else:
                offline_duration = "未知"

            items.append(OfflineMachineItem(
                id=str(m.id),
                ip=m.ip,
                device_sn=m.device_sn,
                device_type=m.device_type,
                offline_duration=offline_duration
            ))

        return items

    @classmethod
    async def delete_failed_logs_by_testcase_id(
        cls,
        db: AsyncSession,
        testcase_id: str
    ) -> int:
        """
        删除指定 testcase_id 的失败日志

        Args:
            db: 数据库会话
            testcase_id: 用例编号

        Returns:
            int: 删除的记录数量
        """
        stmt = delete(EnvMachineLog).where(
            EnvMachineLog.testcase_id == testcase_id,
            EnvMachineLog.result == "fail",
            EnvMachineLog.fail_reason == "env not enough"
        )
        result = await db.execute(stmt)
        return result.rowcount