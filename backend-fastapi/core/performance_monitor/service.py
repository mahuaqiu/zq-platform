#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控业务逻辑
"""
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Type

from sqlalchemy import select, and_, desc, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_service import BaseService
from core.performance_monitor.model import (
    PerformanceCollect, PerformanceData, PerformanceTag, PerformanceVersion,
    PerformanceMetricMapping, PerformanceMarker
)
from core.performance_monitor.utils import extract_core_metrics
from core.performance_monitor.schema import (
    CollectStartRequest, CollectStopRequest, WorkerReportRequest,
    TagCreateRequest, TagUpdateRequest, VersionCreateRequest,
    WorkerReportRequestV3, MetricMappingCreate, MetricMappingUpdate,
    MarkerCreate, MarkerUpdate, AdvancedMetricsQuery
)

logger = logging.getLogger(__name__)


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

    @classmethod
    async def delete_collect(cls, db: AsyncSession, collect_id: str) -> bool:
        """删除采集记录及其所有数据"""
        collect = await db.get(PerformanceCollect, collect_id)
        if not collect:
            return False

        # 先删除关联的性能数据
        data_stmt = select(PerformanceData).where(PerformanceData.collect_id == collect_id)
        data_result = await db.execute(data_stmt)
        data_items = data_result.scalars().all()
        for data_item in data_items:
            await db.delete(data_item)

        # 再删除关联的标签
        tag_stmt = select(PerformanceTag).where(PerformanceTag.collect_id == collect_id)
        tag_result = await db.execute(tag_stmt)
        tag_items = tag_result.scalars().all()
        for tag_item in tag_items:
            await db.delete(tag_item)

        # 最后删除采集记录
        await db.delete(collect)
        await db.commit()
        return True

    @classmethod
    async def set_protected(cls, db: AsyncSession, collect_id: str, is_protected: bool) -> bool:
        """设置采集记录保护状态"""
        collect = await db.get(PerformanceCollect, collect_id)
        if not collect:
            return False
        collect.is_protected = is_protected
        await db.commit()
        return True


class PerformanceDataService(BaseService):
    """性能数据服务"""
    model = PerformanceData

    @classmethod
    async def report_data(cls, db: AsyncSession, request) -> bool:
        """
        接收 Worker 上报数据（批量）

        支持 v0.2.2 (WorkerReportRequest) 和 v0.3.0 (WorkerReportRequestV3)
        v0.3.0 优先使用 hwinfo_raw 提取核心指标，回退到 system 字段
        v0.3.1 支持 relative_time 自动计算（不传时根据 collect.start_time 计算）
        """
        # 获取采集记录的 start_time，用于计算 relative_time
        collect = await db.get(PerformanceCollect, request.collect_id)
        if not collect:
            logger.warning(f"采集记录不存在: {request.collect_id}")
            return False

        start_time = collect.start_time

        for sample in request.samples:
            # 将 timezone-aware datetime 转换为 timezone-naive datetime
            # Worker 上报的 timestamp 带有 UTC timezone，需要转换为 naive datetime
            timestamp_naive = sample.timestamp.replace(tzinfo=None) if sample.timestamp.tzinfo else sample.timestamp

            # 计算 relative_time：如果未提供则根据 timestamp 和 start_time 计算
            relative_time = sample.relative_time
            if relative_time is None:
                # 计算 timestamp 相对于 start_time 的秒数
                relative_time = int((timestamp_naive - start_time).total_seconds())
                # 确保 relative_time 不为负数（防止时间误差）
                relative_time = max(0, relative_time)

            # v0.3.0: 检查 hwinfo_raw 是否存在，优先从中提取核心指标
            hwinfo_raw = getattr(sample, 'hwinfo_raw', None)
            system = getattr(sample, 'system', None)
            target_processes_raw = [p.model_dump() for p in sample.target_processes]

            if hwinfo_raw:
                # v0.3.0: 从 hwinfo_raw 提取核心指标
                core_metrics = extract_core_metrics(hwinfo_raw, target_processes_raw)
                cpu_usage = core_metrics.get("cpu_usage")
                gpu_usage = core_metrics.get("gpu_usage")
                commit_memory = core_metrics.get("commit_memory")
            elif system:
                # v0.2.2: 使用 system 字段
                cpu_usage = system.cpu_usage
                gpu_usage = system.gpu_usage
                commit_memory = system.commit_memory
            else:
                # 无数据时设为 None
                cpu_usage = None
                gpu_usage = None
                commit_memory = None

            # 获取其他系统指标（从 system 或 hwinfo_raw）
            if system:
                memory_usage = system.memory_usage
                power = system.power
                cpu_speed = system.cpu_speed
                cpu_temp = system.cpu_temp
                process_handles = system.process_handles
                upload_speed = system.upload_speed
                download_speed = system.download_speed
            else:
                memory_usage = None
                power = None
                cpu_speed = None
                cpu_temp = None
                process_handles = None
                upload_speed = None
                download_speed = None

            data = PerformanceData(
                collect_id=request.collect_id,
                timestamp=timestamp_naive,
                relative_time=sample.relative_time,
                cpu_usage=cpu_usage,
                gpu_usage=gpu_usage,
                commit_memory=commit_memory,
                memory_usage=memory_usage,
                power=power,
                cpu_speed=cpu_speed,
                cpu_temp=cpu_temp,
                process_handles=process_handles,
                upload_speed=upload_speed,
                download_speed=download_speed,
                target_processes=target_processes_raw,
                top10_cpu=[p.model_dump() for p in sample.top10_cpu],
                top10_gpu=[p.model_dump() for p in sample.top10_gpu],
                hwinfo_raw=hwinfo_raw
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

    @classmethod
    async def query_advanced_metrics(
        cls, db: AsyncSession, request: AdvancedMetricsQuery
    ) -> Dict[str, Any]:
        """
        查询高级指标时序数据

        Args:
            db: 数据库会话
            request: 查询请求，包含 collect_id, metric_keys, start_time, end_time

        Returns:
            按指标键名分组的时序数据
        """
        # 构建基础查询条件
        conditions = [PerformanceData.collect_id == request.collect_id]
        if request.start_time is not None:
            conditions.append(PerformanceData.relative_time >= request.start_time)
        if request.end_time is not None:
            conditions.append(PerformanceData.relative_time <= request.end_time)

        # 查询数据
        stmt = select(PerformanceData).where(
            and_(*conditions)
        ).order_by(PerformanceData.relative_time)
        result = await db.execute(stmt)
        items = result.scalars().all()

        # 构建指标映射字典（用于获取 display_name 和 unit）
        mapping_stmt = select(PerformanceMetricMapping).where(
            PerformanceMetricMapping.hwinfo_key.in_(request.metric_keys)
        )
        mapping_result = await db.execute(mapping_stmt)
        mappings = {m.hwinfo_key: m for m in mapping_result.scalars().all()}

        # 按指标键名分组数据
        metrics_data: Dict[str, Dict[str, Any]] = {}
        for key in request.metric_keys:
            mapping = mappings.get(key)
            metrics_data[key] = {
                "hwinfo_key": key,
                "display_name": mapping.display_name if mapping else key,
                "unit": mapping.unit if mapping else None,
                "data": []
            }

        # 遍历数据，提取每个指标的值
        for item in items:
            hwinfo_raw = item.hwinfo_raw or {}
            for key in request.metric_keys:
                if key in hwinfo_raw:
                    value_info = hwinfo_raw.get(key, {})
                    value = value_info.get("value") if isinstance(value_info, dict) else None
                    metrics_data[key]["data"].append({
                        "relative_time": item.relative_time,
                        "value": value
                    })

        # 检查是否有有效数据
        has_data = any(len(m["data"]) > 0 for m in metrics_data.values())
        if not has_data:
            logger.warning(f"查询高级指标未找到有效数据，collect_id={request.collect_id}, keys={request.metric_keys}")

        return metrics_data


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


class MetricMappingService(BaseService):
    """指标映射服务"""
    model = PerformanceMetricMapping

    @classmethod
    async def get_mappings(
        cls, db: AsyncSession, keyword: Optional[str] = None, category: Optional[str] = None
    ) -> List[PerformanceMetricMapping]:
        """
        获取映射列表

        Args:
            db: 数据库会话
            keyword: 搜索关键词（模糊匹配 hwinfo_key 或 display_name）
            category: 指标分类过滤

        Returns:
            映射列表
        """
        conditions = [PerformanceMetricMapping.is_deleted == False]
        if keyword:
            conditions.append(
                or_(
                    PerformanceMetricMapping.hwinfo_key.ilike(f"%{keyword}%"),
                    PerformanceMetricMapping.display_name.ilike(f"%{keyword}%")
                )
            )
        if category:
            conditions.append(PerformanceMetricMapping.category == category)

        stmt = select(PerformanceMetricMapping).where(
            and_(*conditions)
        ).order_by(PerformanceMetricMapping.sort, PerformanceMetricMapping.hwinfo_key)
        result = await db.execute(stmt)
        return result.scalars().all()

    @classmethod
    async def create_mapping(cls, db: AsyncSession, request: MetricMappingCreate) -> str:
        """
        创建映射

        Args:
            db: 数据库会话
            request: 创建请求

        Returns:
            映射ID
        """
        mapping = PerformanceMetricMapping(
            hwinfo_key=request.hwinfo_key,
            display_name=request.display_name,
            category=request.category,
            is_primary=request.is_primary,
            unit=request.unit
        )
        db.add(mapping)
        await db.commit()
        await db.refresh(mapping)
        return mapping.id

    @classmethod
    async def update_mapping(
        cls, db: AsyncSession, mapping_id: str, request: MetricMappingUpdate
    ) -> bool:
        """
        更新映射

        Args:
            db: 数据库会话
            mapping_id: 映射ID
            request: 更新请求

        Returns:
            是否成功
        """
        mapping = await db.get(PerformanceMetricMapping, mapping_id)
        if not mapping:
            return False
        if request.display_name is not None:
            mapping.display_name = request.display_name
        if request.category is not None:
            mapping.category = request.category
        if request.is_primary is not None:
            mapping.is_primary = request.is_primary
        if request.unit is not None:
            mapping.unit = request.unit
        await db.commit()
        return True

    @classmethod
    async def delete_mapping(cls, db: AsyncSession, mapping_id: str) -> bool:
        """
        删除映射

        Args:
            db: 数据库会话
            mapping_id: 映射ID

        Returns:
            是否成功
        """
        mapping = await db.get(PerformanceMetricMapping, mapping_id)
        if not mapping:
            return False
        await db.delete(mapping)
        await db.commit()
        return True

    @classmethod
    async def batch_import(cls, db: AsyncSession, collect_id: str) -> Dict[str, Any]:
        """
        批量导入未映射传感器

        从指定采集记录的 hwinfo_raw 数据中发现未映射的传感器键名，
        自动创建映射记录。

        Args:
            db: 数据库会话
            collect_id: 采集记录ID

        Returns:
            导入结果，包含新增数量和已存在数量
        """
        # 查询该采集的所有数据
        stmt = select(PerformanceData).where(
            PerformanceData.collect_id == collect_id
        ).limit(1)
        result = await db.execute(stmt)
        first_data = result.scalar_one_or_none()
        if not first_data or not first_data.hwinfo_raw:
            return {"new": 0, "existing": 0, "message": "无 hwinfo_raw 数据"}

        # 获取所有已存在的映射键名
        existing_stmt = select(PerformanceMetricMapping.hwinfo_key)
        existing_result = await db.execute(existing_stmt)
        existing_keys = set(row[0] for row in existing_result.fetchall())

        # 从 hwinfo_raw 中提取新的键名
        hwinfo_raw = first_data.hwinfo_raw
        new_keys = []
        for key in hwinfo_raw.keys():
            if key not in existing_keys:
                new_keys.append(key)

        # 批量创建映射
        new_count = 0
        for key in new_keys:
            mapping = PerformanceMetricMapping(
                hwinfo_key=key,
                display_name=key,  # 默认使用原键名作为显示名称
                category="system",
                is_primary=False,
                unit=None
            )
            db.add(mapping)
            new_count += 1

        await db.commit()
        return {
            "new": new_count,
            "existing": len(existing_keys),
            "message": f"新增 {new_count} 个映射，已存在 {len(existing_keys)} 个"
        }


class MarkerService(BaseService):
    """标记服务"""
    model = PerformanceMarker

    @classmethod
    async def get_markers(cls, db: AsyncSession, collect_id: str) -> List[PerformanceMarker]:
        """
        获取标记列表

        Args:
            db: 数据库会话
            collect_id: 采集记录ID

        Returns:
            标记列表
        """
        stmt = select(PerformanceMarker).where(
            and_(
                PerformanceMarker.collect_id == collect_id,
                PerformanceMarker.is_deleted == False
            )
        ).order_by(PerformanceMarker.start_time)
        result = await db.execute(stmt)
        return result.scalars().all()

    @classmethod
    async def create_marker(cls, db: AsyncSession, request: MarkerCreate) -> str:
        """
        创建标记

        Args:
            db: 数据库会话
            request: 创建请求

        Returns:
            标记ID
        """
        marker = PerformanceMarker(
            collect_id=request.collect_id,
            name=request.name,
            start_time=request.start_time,
            end_time=request.end_time,
            color=request.color,
            note=request.note
        )
        db.add(marker)
        await db.commit()
        await db.refresh(marker)
        return marker.id

    @classmethod
    async def update_marker(
        cls, db: AsyncSession, marker_id: str, request: MarkerUpdate
    ) -> bool:
        """
        更新标记

        Args:
            db: 数据库会话
            marker_id: 标记ID
            request: 更新请求

        Returns:
            是否成功
        """
        marker = await db.get(PerformanceMarker, marker_id)
        if not marker:
            return False
        if request.name is not None:
            marker.name = request.name
        if request.start_time is not None:
            marker.start_time = request.start_time
        if request.end_time is not None:
            marker.end_time = request.end_time
        if request.color is not None:
            marker.color = request.color
        if request.note is not None:
            marker.note = request.note
        await db.commit()
        return True

    @classmethod
    async def delete_marker(cls, db: AsyncSession, marker_id: str) -> bool:
        """
        删除标记

        Args:
            db: 数据库会话
            marker_id: 标记ID

        Returns:
            是否成功
        """
        marker = await db.get(PerformanceMarker, marker_id)
        if not marker:
            return False
        await db.delete(marker)
        await db.commit()
        return True