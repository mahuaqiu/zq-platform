#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控业务逻辑
"""
from datetime import datetime
from typing import List, Optional, Dict, Any, Type

from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_service import BaseService
from core.performance_monitor.model import PerformanceCollect, PerformanceData, PerformanceTag, PerformanceVersion
from core.performance_monitor.schema import (
    CollectStartRequest, CollectStopRequest, WorkerReportRequest,
    TagCreateRequest, TagUpdateRequest, VersionCreateRequest
)


class PerformanceCollectService(BaseService):
    """采集记录服务"""
    model = PerformanceCollect

    @classmethod
    async def start_collect(cls, db: AsyncSession, request: CollectStartRequest) -> str:
        """开始采集"""
        collect = PerformanceCollect(
            device_id=request.device_id,
            start_time=datetime.utcnow(),
            interval=request.interval,
            target_processes=request.target_processes,
            status="running"
        )
        db.add(collect)
        await db.commit()
        await db.refresh(collect)
        return collect.id

    @classmethod
    async def stop_collect(cls, db: AsyncSession, collect_id: Optional[str], device_id: str) -> bool:
        """停止采集"""
        if collect_id:
            collect = await db.get(PerformanceCollect, collect_id)
            if collect:
                collect.status = "stopped"
                collect.end_time = datetime.utcnow()
                await db.commit()
                return True
        else:
            # 停止该设备所有正在运行的采集
            stmt = select(PerformanceCollect).where(
                and_(PerformanceCollect.device_id == device_id, PerformanceCollect.status == "running")
            )
            result = await db.execute(stmt)
            collects = result.scalars().all()
            for c in collects:
                c.status = "stopped"
                c.end_time = datetime.utcnow()
            await db.commit()
            return len(collects) > 0
        return False

    @classmethod
    async def get_collect_status(cls, db: AsyncSession, device_id: str) -> Optional[Dict[str, Any]]:
        """获取采集状态"""
        stmt = select(PerformanceCollect).where(
            and_(PerformanceCollect.device_id == device_id, PerformanceCollect.status == "running")
        ).order_by(desc(PerformanceCollect.start_time)).limit(1)
        result = await db.execute(stmt)
        collect = result.scalar_one_or_none()
        if collect:
            # 将 datetime 转换为带 Z 后缀的 UTC 格式字符串
            start_time_str = collect.start_time.strftime('%Y-%m-%dT%H:%M:%S') + 'Z' if collect.start_time else None
            return {
                "is_collecting": True,
                "collect_id": collect.id,
                "interval": collect.interval,
                "target_processes": collect.target_processes,
                "start_time": start_time_str,
                "elapsed_seconds": int((datetime.utcnow() - collect.start_time).total_seconds())
            }
        return {"is_collecting": False}

    @classmethod
    async def get_collect_list(cls, db: AsyncSession, device_id: Optional[str], page: int, page_size: int) -> Dict[str, Any]:
        """获取采集列表"""
        conditions = [PerformanceCollect.is_deleted == False]
        if device_id:
            conditions.append(PerformanceCollect.device_id == device_id)

        stmt = select(PerformanceCollect).where(and_(*conditions)).order_by(desc(PerformanceCollect.start_time))
        # 计算总数
        count_stmt = select(func.count()).select_from(PerformanceCollect).where(and_(*conditions))
        count_result = await db.execute(count_stmt)
        total = count_result.scalar()

        # 分页查询
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(stmt)
        items = result.scalars().all()

        return {"total": total, "items": items}


class PerformanceDataService(BaseService):
    """性能数据服务"""
    model = PerformanceData

    @classmethod
    async def report_data(cls, db: AsyncSession, request: WorkerReportRequest) -> bool:
        """接收 Worker 上报数据（批量）"""
        for sample in request.samples:
            # 将 timezone-aware datetime 转换为 timezone-naive datetime
            # Worker 上报的 timestamp 带有 UTC timezone，需要转换为 naive datetime
            timestamp_naive = sample.timestamp.replace(tzinfo=None) if sample.timestamp.tzinfo else sample.timestamp

            data = PerformanceData(
                collect_id=request.collect_id,
                timestamp=timestamp_naive,
                relative_time=sample.relative_time,
                cpu_usage=sample.system.cpu_usage,
                gpu_usage=sample.system.gpu_usage,
                commit_memory=sample.system.commit_memory,
                memory_usage=sample.system.memory_usage,
                power=sample.system.power,
                cpu_speed=sample.system.cpu_speed,
                cpu_temp=sample.system.cpu_temp,
                process_handles=sample.system.process_handles,
                upload_speed=sample.system.upload_speed,
                download_speed=sample.system.download_speed,
                target_processes=[p.model_dump() for p in sample.target_processes],
                top10_cpu=[p.model_dump() for p in sample.top10_cpu],
                top10_gpu=[p.model_dump() for p in sample.top10_gpu]
            )
            db.add(data)
        await db.commit()
        return True

    @classmethod
    async def get_collect_data(cls, db: AsyncSession, collect_id: str, page: int, page_size: int) -> Dict[str, Any]:
        """获取采集数据"""
        stmt = select(PerformanceData).where(
            PerformanceData.collect_id == collect_id
        ).order_by(PerformanceData.relative_time)

        # 计算总数
        count_stmt = select(func.count()).select_from(PerformanceData).where(PerformanceData.collect_id == collect_id)
        count_result = await db.execute(count_stmt)
        total = count_result.scalar()

        # 分页查询
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(stmt)
        items = result.scalars().all()

        return {"total": total, "items": items}

    @classmethod
    async def get_latest_data(cls, db: AsyncSession, collect_id: str, limit: int = 10) -> List[PerformanceData]:
        """获取最新数据"""
        stmt = select(PerformanceData).where(
            PerformanceData.collect_id == collect_id
        ).order_by(desc(PerformanceData.relative_time)).limit(limit)
        result = await db.execute(stmt)
        items = result.scalars().all()
        return list(reversed(items))


class PerformanceTagService(BaseService):
    """标签服务"""
    model = PerformanceTag

    @classmethod
    async def create_tag(cls, db: AsyncSession, request: TagCreateRequest) -> str:
        """创建标签"""
        tag = PerformanceTag(
            collect_id=request.collect_id,
            name=request.name,
            start_relative_time=request.start_relative_time,
            duration=request.duration,
            type=request.type
        )
        db.add(tag)
        await db.commit()
        await db.refresh(tag)
        return tag.id

    @classmethod
    async def get_tags(cls, db: AsyncSession, collect_id: str) -> List[PerformanceTag]:
        """获取标签列表"""
        stmt = select(PerformanceTag).where(PerformanceTag.collect_id == collect_id)
        result = await db.execute(stmt)
        return result.scalars().all()

    @classmethod
    async def update_tag(cls, db: AsyncSession, tag_id: str, **kwargs) -> bool:
        """更新标签"""
        tag = await db.get(PerformanceTag, tag_id)
        if tag:
            for key, value in kwargs.items():
                if value is not None and hasattr(tag, key):
                    setattr(tag, key, value)
            await db.commit()
            return True
        return False

    @classmethod
    async def delete_tag(cls, db: AsyncSession, tag_id: str) -> bool:
        """删除标签"""
        tag = await db.get(PerformanceTag, tag_id)
        if tag:
            await db.delete(tag)
            await db.commit()
            return True
        return False


class PerformanceVersionService(BaseService):
    """版本对比服务"""
    model = PerformanceVersion

    @classmethod
    async def create_version(cls, db: AsyncSession, request: VersionCreateRequest) -> str:
        """创建版本"""
        # 从第一个 collect_id 获取 device_id
        first_collect = await db.get(PerformanceCollect, request.collect_ids[0])
        if not first_collect:
            raise ValueError("采集记录不存在")

        version = PerformanceVersion(
            device_id=first_collect.device_id,
            name=request.name,
            collect_ids=request.collect_ids,  # 直接使用字符串列表
            is_protected=False
        )
        db.add(version)
        await db.commit()
        await db.refresh(version)
        return version.id

    @classmethod
    async def get_versions(cls, db: AsyncSession, device_id: str) -> List[PerformanceVersion]:
        """获取版本列表"""
        stmt = select(PerformanceVersion).where(PerformanceVersion.device_id == device_id)
        result = await db.execute(stmt)
        return result.scalars().all()

    @classmethod
    async def get_compare_data(cls, db: AsyncSession, version_ids: List[str]) -> Dict[str, Any]:
        """获取对比数据"""
        versions_data = []
        for vid in version_ids:
            version = await db.get(PerformanceVersion, vid)
            if version:
                collect_ids = version.collect_ids  # 已经是字符串列表
                collects = []
                for cid in collect_ids:
                    collect = await db.get(PerformanceCollect, cid)
                    if collect:
                        # 获取该采集的所有数据
                        stmt = select(PerformanceData).where(PerformanceData.collect_id == cid).order_by(PerformanceData.relative_time)
                        result = await db.execute(stmt)
                        data = result.scalars().all()
                        # 获取标签
                        tags = await PerformanceTagService.get_tags(db, cid)
                        collects.append({
                            "collect": collect,
                            "data": data,
                            "tags": tags
                        })
                versions_data.append({
                    "version": version,
                    "collects": collects
                })

        return {"versions": versions_data}