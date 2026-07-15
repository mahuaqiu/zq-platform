#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控业务逻辑
"""
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Type

from sqlalchemy import select, and_, desc, func, or_, update, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_service import BaseService
from core.performance_monitor.model import (
    PerformanceCollect, PerformanceData, PerformanceTag, PerformanceVersion,
    PerformanceMetricMapping, PerformanceMarker, ExportTask
)
from core.performance_monitor.compare_model import CompareTag
from core.performance_monitor.utils import (
    extract_core_metrics,
    convert_aggregated_to_target_processes,
    convert_top_n_to_top10
)
from core.performance_monitor.schema import (
    CollectStartRequest, CollectStopRequest,
    TagCreateRequest, TagUpdateRequest, VersionCreateRequest,
    WorkerReportRequestV3, MetricMappingCreate, MetricMappingUpdate,
    MarkerCreate, MarkerUpdate, AdvancedMetricsQuery,
    DataResponse, CollectResponse, ExportTaskCreate
)
from core.performance_monitor.compare_schema import CompareTagCreate, CompareTagUpdate
from utils.excel import SummaryData, DetailData, ExcelHandler, TEMP_EXPORTS_DIR

# 配置常量
EXPORT_TASK_TIMEOUT = 600  # 任务执行超时：10分钟

logger = logging.getLogger(__name__)


class PerformanceCollectService(BaseService):
    """采集记录服务"""
    model = PerformanceCollect

    # 活跃状态：前端会据此禁用“开始采集”
    ACTIVE_STATUSES = ("pending", "starting", "running", "stopping")
    TERMINAL_STATUSES = ("stopped", "failed", "timed_out", "interrupted")
    # Worker 重启后若未回传终态，这些状态会卡住；按心跳/启动时间做对账
    STALE_STARTING_SECONDS = 60
    STALE_STOPPING_SECONDS = 90
    STALE_RUNNING_MIN_SECONDS = 60

    @classmethod
    def _stale_threshold_seconds(cls, collect: PerformanceCollect) -> int:
        """计算僵尸采集判定阈值（秒）。"""
        interval = max(int(collect.interval or 5), 1)
        if collect.status == "stopping":
            return max(cls.STALE_STOPPING_SECONDS, interval * 6)
        if collect.status in ("pending", "starting"):
            return max(cls.STALE_STARTING_SECONDS, interval * 4)
        # running：允许短暂网络抖动，但心跳断流过久视为中断
        return max(cls.STALE_RUNNING_MIN_SECONDS, interval * 6)

    @classmethod
    def _reference_time(cls, collect: PerformanceCollect) -> Optional[datetime]:
        """僵尸判定参考时间：优先心跳，其次更新时间，最后启动时间。"""
        return collect.last_heartbeat_at or collect.sys_update_datetime or collect.start_time

    @classmethod
    async def reconcile_stale_collects(
        cls, db: AsyncSession, device_id: Optional[str] = None
    ) -> int:
        """将对账超时的活跃采集标记为 interrupted，返回处理条数。

        Worker 重启/进程被杀时可能来不及上报终态，平台侧会长期卡在
        starting/running/stopping，导致前端 is_collecting=true 无法重新开始。
        """
        conditions = [PerformanceCollect.status.in_(list(cls.ACTIVE_STATUSES))]
        if device_id:
            conditions.append(PerformanceCollect.device_id == device_id)

        result = await db.execute(select(PerformanceCollect).where(and_(*conditions)))
        collects = result.scalars().all()
        if not collects:
            return 0

        now = datetime.utcnow()
        fixed = 0
        for collect in collects:
            ref = cls._reference_time(collect)
            if not ref:
                continue
            age = (now - ref).total_seconds()
            if age < cls._stale_threshold_seconds(collect):
                continue
            prev_status = collect.status
            collect.status = "interrupted"
            collect.end_time = now
            collect.end_reason = "stale_reconcile"
            collect.failure_code = collect.failure_code or "WORKER_STALE"
            collect.failure_message = (
                collect.failure_message
                or f"Worker 长时间无心跳/终态（状态={prev_status}，参考时间距今 {int(age)}s），自动中断"
            )
            fixed += 1

        if fixed:
            await db.commit()
            logger.warning("对账中断僵尸采集 %s 条, device_id=%s", fixed, device_id)
        return fixed

    @classmethod
    async def start_collect(cls, db: AsyncSession, request: CollectStartRequest) -> str:
        """开始采集"""
        # Worker 重启后可能残留 starting/stopping，先对账再创建
        await cls.reconcile_stale_collects(db, request.device_id)

        active = await db.execute(
            select(PerformanceCollect).where(
                and_(
                    PerformanceCollect.device_id == request.device_id,
                    PerformanceCollect.status.in_(list(cls.ACTIVE_STATUSES)),
                )
            ).order_by(desc(PerformanceCollect.start_time)).limit(1)
        )
        existing = active.scalar_one_or_none()
        if existing:
            raise ValueError(
                f"设备已有采集任务（{existing.id}, status={existing.status}），请先停止"
            )

        # 使用 timezone-aware UTC 时间
        start_time_utc = datetime.now(timezone.utc)
        collect = PerformanceCollect(
            device_id=request.device_id,
            start_time=start_time_utc.replace(tzinfo=None),  # 存储为 naive datetime（UTC）
            interval=request.interval,
            target_processes=request.target_processes,
            status="starting"
        )
        db.add(collect)
        await db.commit()
        await db.refresh(collect)
        return collect.id

    @classmethod
    async def stop_collect(cls, db: AsyncSession, collect_id: Optional[str], device_id: str) -> bool:
        """请求停止采集，最终状态由 Worker 终态事件确认。"""
        if collect_id:
            collect = await db.get(PerformanceCollect, collect_id)
            if collect and collect.device_id == device_id:
                if collect.status not in cls.TERMINAL_STATUSES:
                    collect.status = "stopping"
                collect.end_reason = "user_stop"
                await db.commit()
                return True
            return False
        stmt = select(PerformanceCollect).where(
            and_(
                PerformanceCollect.device_id == device_id,
                PerformanceCollect.status.in_(list(cls.ACTIVE_STATUSES)),
            )
        )
        result = await db.execute(stmt)
        collects = result.scalars().all()
        for collect in collects:
            collect.status = "stopping"
            collect.end_reason = "user_stop"
        await db.commit()
        return len(collects) > 0

    @classmethod
    async def get_collect_status(cls, db: AsyncSession, device_id: str) -> Optional[Dict[str, Any]]:
        """获取采集状态"""
        # 查询前先清理僵尸状态，避免前端长期禁用开始按钮
        await cls.reconcile_stale_collects(db, device_id)

        stmt = select(PerformanceCollect).where(
            and_(
                PerformanceCollect.device_id == device_id,
                PerformanceCollect.status.in_(list(cls.ACTIVE_STATUSES)),
            )
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
                "elapsed_seconds": int((datetime.utcnow() - collect.start_time).total_seconds()),
                "last_heartbeat_at": collect.last_heartbeat_at,
                "last_sequence": collect.last_sequence,
                "last_elapsed_ms": collect.last_elapsed_ms,
                "status": collect.status
            }
        return {"is_collecting": False, "state": "idle"}

    @classmethod
    async def handle_worker_event(cls, db: AsyncSession, request) -> bool:
        """处理 Worker 的终态通知，重复通知保持幂等。"""
        collect = await db.get(PerformanceCollect, request.collect_id)
        if not collect or collect.device_id != request.device_id:
            return False
        allowed = {"stopped", "failed", "timed_out", "interrupted"}
        if request.status not in allowed:
            return False
        if collect.status in allowed:
            return True
        collect.status = request.status
        collect.end_time = datetime.utcnow()
        collect.end_reason = request.status
        collect.failure_message = request.message if request.status in ("failed", "interrupted") else None
        if request.last_sequence is not None:
            collect.last_sequence = request.last_sequence
        if request.last_elapsed_ms is not None:
            collect.last_elapsed_ms = request.last_elapsed_ms
        await db.commit()
        return True

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
        from sqlalchemy import delete

        collect = await db.get(PerformanceCollect, collect_id)
        if not collect:
            return False

        # 批量删除关联的性能数据
        await db.execute(delete(PerformanceData).where(PerformanceData.collect_id == collect_id))

        # 批量删除关联的标签
        await db.execute(delete(PerformanceTag).where(PerformanceTag.collect_id == collect_id))

        # 批量删除关联的标记
        await db.execute(delete(PerformanceMarker).where(PerformanceMarker.collect_id == collect_id))

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
    async def report_data(cls, db: AsyncSession, request) -> Dict[str, Any]:
        """接收 Worker 批量样本，使用 Rust 单调时间并按 sample_key 幂等入库。"""
        collect = await db.get(PerformanceCollect, request.collect_id)
        if not collect:
            logger.warning("采集记录不存在: %s", request.collect_id)
            return {"status": "failed", "accepted_count": 0}
        if collect.device_id != request.device_id:
            logger.warning("设备与采集记录不匹配: collect=%s device=%s", request.collect_id, request.device_id)
            return {"status": "failed", "accepted_count": 0}

        sample_keys = [sample.sample_key for sample in request.samples if sample.sample_key]
        existing_keys: set[str] = set()
        if sample_keys:
            result = await db.execute(
                select(PerformanceData.sample_key).where(
                    PerformanceData.sample_key.in_(sample_keys)
                )
            )
            existing_keys = {key for key in result.scalars().all() if key}
        batch_keys: set[str] = set()

        for sample in request.samples:
            if sample.sample_key and (
                sample.sample_key in existing_keys or sample.sample_key in batch_keys
            ):
                continue
            if sample.sample_key:
                batch_keys.add(sample.sample_key)

            if sample.timestamp is None:
                logger.warning("样本缺少 timestamp，跳过")
                continue

            if sample.timestamp.tzinfo is not None:
                timestamp_naive = sample.timestamp.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                timestamp_naive = sample.timestamp

            # Rust Instant 产生的毫秒时间是主时间轴，relative_time 只用于兼容旧查询。
            if sample.elapsed_ms is not None:
                elapsed_ms = max(0, sample.elapsed_ms)
                relative_time = elapsed_ms // 1000
            elif sample.relative_time is not None:
                elapsed_ms = max(0, sample.relative_time * 1000)
                relative_time = max(0, sample.relative_time)
            else:
                elapsed_ms = 0
                relative_time = 0

            hwinfo_raw = sample.hwinfo_raw
            system_metrics = sample.system or {}
            aggregated = sample.aggregated
            processes = sample.processes
            top_n_cpu = sample.top_n_cpu
            top_n_gpu = sample.top_n_gpu

            aggregated_dict = [p.model_dump() for p in aggregated] if aggregated else []
            processes_dict = [p.model_dump() for p in processes] if processes else []
            top_n_cpu_dict = [p.model_dump() for p in top_n_cpu] if top_n_cpu else []
            top_n_gpu_dict = [p.model_dump() for p in top_n_gpu] if top_n_gpu else []

            # 系统 CPU 优先 Rust；GPU 在 PDH 空/假 0 时回退 HWiNFO。
            process_metrics = extract_core_metrics(hwinfo_raw, aggregated_dict)
            cpu_usage = system_metrics.get("cpu_percent")
            gpu_usage = system_metrics.get("gpu_percent")
            gpu_adapters = system_metrics.get("gpu_adapters") or []
            if (
                (gpu_usage is None or (gpu_usage == 0 and not gpu_adapters))
                and process_metrics.get("gpu_usage") is not None
            ):
                gpu_usage = process_metrics["gpu_usage"]
                system_metrics = dict(system_metrics)
                system_metrics["gpu_percent"] = gpu_usage
                system_metrics["gpu_source"] = "hwinfo_fallback"
            process_memory = process_metrics.get("process_memory")
            process_committed_memory = process_metrics.get("process_committed_memory")

            total_handles = sum(
                int(proc.get("handle_count_total", 0) or 0)
                for proc in aggregated_dict
            )
            target_processes_raw = convert_aggregated_to_target_processes(
                aggregated_dict, processes_dict
            )
            top10_cpu_raw = convert_top_n_to_top10(top_n_cpu_dict, "cpu")
            top10_gpu_raw = convert_top_n_to_top10(top_n_gpu_dict, "gpu")

            db.add(PerformanceData(
                collect_id=request.collect_id,
                sample_key=sample.sample_key,
                sequence=sample.sequence,
                elapsed_ms=elapsed_ms,
                timestamp=timestamp_naive,
                relative_time=relative_time,
                cpu_usage=cpu_usage,
                gpu_usage=gpu_usage,
                commit_memory=process_committed_memory / 1024 if process_committed_memory else None,
                memory_usage=process_memory / 1024 if process_memory else None,
                process_handles=total_handles if total_handles > 0 else None,
                target_processes=target_processes_raw,
                top10_cpu=top10_cpu_raw,
                top10_gpu=top10_gpu_raw,
                hwinfo_raw=hwinfo_raw,
                system_metrics=system_metrics,
            ))

        if request.samples:
            last_sample = max(request.samples, key=lambda item: item.sequence)
            collect.last_heartbeat_at = datetime.utcnow()
            if collect.last_sequence is None or last_sample.sequence > collect.last_sequence:
                collect.last_sequence = last_sample.sequence
                collect.last_elapsed_ms = last_sample.elapsed_ms
            if collect.status == "starting":
                collect.status = "running"
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        return {"status": "success", "accepted_through_sequence": collect.last_sequence}
    @classmethod
    async def get_collect_data(cls, db: AsyncSession, collect_id: str, page: int, page_size: int) -> Dict[str, Any]:
        """获取采集数据"""
        stmt = select(PerformanceData).where(
            PerformanceData.collect_id == collect_id
        ).order_by(func.coalesce(PerformanceData.elapsed_ms, PerformanceData.relative_time * 1000), PerformanceData.sequence, PerformanceData.relative_time)

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
        ).order_by(desc(func.coalesce(PerformanceData.elapsed_ms, PerformanceData.relative_time * 1000)), desc(PerformanceData.sequence), desc(PerformanceData.relative_time)).limit(limit)
        result = await db.execute(stmt)
        items = result.scalars().all()
        return list(reversed(items))

    @classmethod
    async def get_collect_data_by_range(
        cls, db: AsyncSession, collect_id: str, start_time: float, end_time: float
    ) -> List[PerformanceData]:
        """按时间范围获取采集数据（用于查看特定时间窗口）

        start_time/end_time 为相对秒数，支持毫秒精度（如 10.022）。
        过滤优先使用 elapsed_ms（毫秒），旧数据回退到 relative_time（秒）。
        """
        conditions = [PerformanceData.collect_id == collect_id]
        if start_time > 0:
            conditions.append(or_(
                PerformanceData.elapsed_ms >= int(start_time * 1000),
                and_(PerformanceData.elapsed_ms.is_(None), PerformanceData.relative_time >= int(start_time)),
            ))
        if end_time > 0:
            conditions.append(or_(
                PerformanceData.elapsed_ms <= int(end_time * 1000),
                and_(PerformanceData.elapsed_ms.is_(None), PerformanceData.relative_time <= int(end_time)),
            ))

        stmt = select(PerformanceData).where(
            and_(*conditions)
        ).order_by(func.coalesce(PerformanceData.elapsed_ms, PerformanceData.relative_time * 1000), PerformanceData.sequence, PerformanceData.relative_time)
        result = await db.execute(stmt)
        items = result.scalars().all()
        return items

    @classmethod
    async def get_available_metrics(cls, db: AsyncSession, collect_id: str) -> List[Dict[str, Any]]:
        """
        获取采集记录可用的指标列表

        Args:
            db: 数据库会话
            collect_id: 采集记录ID

        Returns:
            指标列表 [{"key": "键名", "label": "显示名称", "source": "hwinfo/system"}]
        """
        metrics = []

        # 进程指标：只有 process_handles 是数据库字段，其他指标都从 hwinfo_raw 动态获取
        system_metric_fields = {
            "process_handles": {"label": "进程句柄数", "source": "system", "unit": "个"},
        }

        # 检查是否有 process_handles 数据
        stmt = select(PerformanceData).where(
            PerformanceData.collect_id == collect_id,
            PerformanceData.process_handles.isnot(None)
        ).limit(1)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            metric_info = system_metric_fields["process_handles"]
            metrics.append({
                "key": "process_handles",
                "label": metric_info["label"],
                "source": metric_info["source"],
                "unit": metric_info["unit"]
            })

        # 从 hwinfo_raw 中动态提取键名
        hwinfo_stmt = select(PerformanceData).where(
            PerformanceData.collect_id == collect_id,
            PerformanceData.hwinfo_raw.isnot(None)
        ).limit(1)
        hwinfo_result = await db.execute(hwinfo_stmt)
        hwinfo_data = hwinfo_result.scalar_one_or_none()

        if hwinfo_data and hwinfo_data.hwinfo_raw:
            for key in sorted(hwinfo_data.hwinfo_raw.keys()):
                # Linux 指标（以 "Linux " 开头）分类为 linux 源，不是 hwinfo
                source = "linux" if key.startswith("Linux ") else "hwinfo"
                metrics.append({
                    "key": key,
                    "label": key,  # 默认使用原键名，前端可以翻译
                    "source": source
                })

        return metrics

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
            conditions.append(or_(
                PerformanceData.elapsed_ms >= request.start_time * 1000,
                and_(PerformanceData.elapsed_ms.is_(None), PerformanceData.relative_time >= request.start_time),
            ))
        if request.end_time is not None:
            conditions.append(or_(
                PerformanceData.elapsed_ms <= request.end_time * 1000,
                and_(PerformanceData.elapsed_ms.is_(None), PerformanceData.relative_time <= request.end_time),
            ))

        # 查询数据
        stmt = select(PerformanceData).where(
            and_(*conditions)
        ).order_by(func.coalesce(PerformanceData.elapsed_ms, PerformanceData.relative_time * 1000), PerformanceData.sequence, PerformanceData.relative_time)
        result = await db.execute(stmt)
        items = result.scalars().all()

        # 构建指标映射字典（用于获取 display_name 和 unit）
        mapping_stmt = select(PerformanceMetricMapping).where(
            PerformanceMetricMapping.hwinfo_key.in_(request.metric_keys)
        )
        mapping_result = await db.execute(mapping_stmt)
        mappings = {m.hwinfo_key: m for m in mapping_result.scalars().all()}

        # 进程指标字段映射（只有 process_handles 是数据库字段）
        system_metric_fields = {
            "process_handles": ("process_handles", "进程句柄数", "个"),
        }

        # 按指标键名分组数据
        metrics_data: Dict[str, Dict[str, Any]] = {}
        for key in request.metric_keys:
            # 检查是否是系统指标
            if key in system_metric_fields:
                field_name, display_name, unit = system_metric_fields[key]
                metrics_data[key] = {
                    "hwinfo_key": key,
                    "display_name": display_name,
                    "unit": unit,
                    "data": []
                }
            else:
                # HWiNFO 指标
                mapping = mappings.get(key)
                metrics_data[key] = {
                    "hwinfo_key": key,
                    "display_name": mapping.display_name if mapping else key,
                    "unit": mapping.unit if mapping else None,
                    "data": []
                }

        # 遍历数据，提取每个指标的值
        for item in items:
            for key in request.metric_keys:
                # 系统指标从数据库字段获取
                if key in system_metric_fields:
                    field_name = system_metric_fields[key][0]
                    value = getattr(item, field_name, None)
                    if value is not None:
                        metrics_data[key]["data"].append({
                            "relative_time": item.relative_time,
                            "value": value
                        })
                else:
                    # HWiNFO 指标从 hwinfo_raw 获取
                    hwinfo_raw = item.hwinfo_raw or {}
                    if key in hwinfo_raw:
                        value_info = hwinfo_raw.get(key, {})
                        if isinstance(value_info, dict):
                            value = value_info.get("value")
                            # 从原始数据中提取单位（如果 mapping 中没有配置）
                            raw_unit = value_info.get("unit")
                            if raw_unit and not metrics_data[key]["unit"]:
                                metrics_data[key]["unit"] = raw_unit
                        else:
                            value = value_info
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
    async def get_versions(cls, db: AsyncSession, device_id: Optional[str] = None) -> List[PerformanceVersion]:
        """获取版本列表"""
        stmt = select(PerformanceVersion).where(PerformanceVersion.is_deleted == False)
        if device_id:
            stmt = stmt.where(PerformanceVersion.device_id == device_id)
        stmt = stmt.order_by(PerformanceVersion.sys_create_datetime.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def get_compare_data(cls, db: AsyncSession, version_ids: List[str]) -> Dict[str, Any]:
        """获取对比数据（根据版本的时间范围筛选数据）"""
        versions_data = []
        for vid in version_ids:
            version = await db.get(PerformanceVersion, vid)
            if version:
                collect_ids = version.collect_ids  # 已经是字符串列表
                time_ranges = version.time_ranges or {}  # 时间范围映射
                collects = []
                for cid in collect_ids:
                    collect = await db.get(PerformanceCollect, cid)
                    if collect:
                        # 获取该采集的数据，并根据时间范围筛选
                        stmt = select(PerformanceData).where(PerformanceData.collect_id == cid).order_by(func.coalesce(PerformanceData.elapsed_ms, PerformanceData.relative_time * 1000), PerformanceData.sequence, PerformanceData.relative_time)
                        result = await db.execute(stmt)
                        all_data = result.scalars().all()

                        # 如果有时间范围，筛选数据
                        if cid in time_ranges:
                            range_info = time_ranges[cid]
                            start_time = range_info.get("start", 0)
                            end_time = range_info.get("end")
                            if end_time:
                                # 筛选时间范围内的数据
                                filtered_data = [d for d in all_data if start_time <= d.relative_time <= end_time]
                            else:
                                # 只有开始时间，从开始时间到结束
                                filtered_data = [d for d in all_data if d.relative_time >= start_time]
                        else:
                            # 没有时间范围，使用全部数据
                            filtered_data = all_data

                        # 序列化数据
                        serialized_data = [DataResponse.model_validate(d) for d in filtered_data]

                        # 获取标签
                        tags = await PerformanceTagService.get_tags(db, cid)
                        collects.append({
                            "collect": CollectResponse.model_validate(collect),
                            "data": serialized_data,
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
        创建标记（同时创建对应的版本记录）

        Args:
            db: 数据库会话
            request: 创建请求

        Returns:
            标记ID
        """
        # 获取采集记录以获取 device_id
        collect = await db.get(PerformanceCollect, request.collect_id)
        if not collect:
            raise ValueError(f"采集记录不存在: {request.collect_id}")

        # 创建标记
        marker = PerformanceMarker(
            collect_id=request.collect_id,
            name=request.name,
            start_time=request.start_time,
            end_time=request.end_time,
            color=request.color,
            note=request.note
        )
        db.add(marker)

        # 同时创建版本记录（使用标记名称作为版本名称）
        # 构造 time_ranges: {collect_id: {start: start_time, end: end_time}}
        time_ranges = {
            request.collect_id: {
                "start": request.start_time,
                "end": request.end_time if request.end_time else request.start_time
            }
        }
        version = PerformanceVersion(
            device_id=collect.device_id,
            name=request.name,
            collect_ids=[request.collect_id],
            time_ranges=time_ranges,
            is_protected=False
        )
        db.add(version)

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
        删除标记（同时删除对应的版本记录）

        Args:
            db: 数据库会话
            marker_id: 标记ID

        Returns:
            是否成功
        """
        marker = await db.get(PerformanceMarker, marker_id)
        if not marker:
            return False

        # 同时删除对应的版本记录（通过名称匹配）
        stmt = select(PerformanceVersion).where(
            and_(
                PerformanceVersion.name == marker.name,
                PerformanceVersion.is_deleted == False
            )
        )
        result = await db.execute(stmt)
        version = result.scalar_one_or_none()
        if version:
            await db.delete(version)

        await db.delete(marker)
        await db.commit()
        return True


class CompareTagService(BaseService):
    """对比标签服务"""
    model = CompareTag

    @classmethod
    async def create_tag(cls, db: AsyncSession, request: CompareTagCreate) -> str:
        """创建对比标签"""
        tag = CompareTag(
            name=request.name,
            type=request.type,
            start_time=request.start_time,
            end_time=request.end_time,
            note=request.note,
        )
        db.add(tag)
        await db.commit()
        await db.refresh(tag)
        return str(tag.id)

    @classmethod
    async def get_tags(cls, db: AsyncSession) -> List[CompareTag]:
        """获取所有对比标签"""
        stmt = select(CompareTag).where(CompareTag.is_deleted == False).order_by(CompareTag.sys_create_datetime.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def update_tag(cls, db: AsyncSession, tag_id: str, request: CompareTagUpdate) -> bool:
        """更新对比标签"""
        tag = await db.get(CompareTag, tag_id)
        if not tag or tag.is_deleted:
            return False
        if request.name is not None:
            tag.name = request.name
        if request.type is not None:
            tag.type = request.type
        if request.start_time is not None:
            tag.start_time = request.start_time
        if request.end_time is not None:
            tag.end_time = request.end_time
        if request.note is not None:
            tag.note = request.note
        await db.commit()
        return True

    @classmethod
    async def delete_tag(cls, db: AsyncSession, tag_id: str) -> bool:
        """删除对比标签（软删除）"""
        tag = await db.get(CompareTag, tag_id)
        if not tag or tag.is_deleted:
            return False
        tag.is_deleted = True
        await db.commit()
        return True


class ExportTaskService(BaseService):
    """导出任务服务"""
    model = ExportTask

    @classmethod
    async def create_task(cls, db: AsyncSession, params: ExportTaskCreate, user_id: str) -> ExportTask:
        """创建导出任务"""
        task = ExportTask(
            task_type="compare_export",
            params=params.model_dump(),
            status="pending",
            progress=0,
            message="任务已创建",
            sys_creator_id=user_id
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task

    @classmethod
    async def get_pending_task(cls, db: AsyncSession, params: ExportTaskCreate) -> Optional[ExportTask]:
        """获取相同参数的进行中任务"""
        import json
        from sqlalchemy import func

        # PostgreSQL JSON 类型不能直接使用 = 比较，需要转换为文本
        params_json = json.dumps(params.model_dump(), sort_keys=True)
        stmt = select(ExportTask).where(
            ExportTask.task_type == "compare_export",
            func.cast(ExportTask.params, String) == params_json,
            ExportTask.status.in_(["pending", "processing"]),
            ExportTask.is_deleted == False
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def update_progress(cls, db: AsyncSession, task_id: str, progress: int, message: str):
        """更新任务进度"""
        task = await db.get(ExportTask, task_id)
        if task:
            task.progress = progress
            task.message = message
            await db.commit()

    @classmethod
    async def update_status(cls, db: AsyncSession, task_id: str, status: str, message: str, file_path: str = None):
        """更新任务状态"""
        task = await db.get(ExportTask, task_id)
        if task:
            task.status = status
            task.message = message
            if file_path:
                task.file_path = file_path
            if status == "completed":
                task.completed_at = datetime.utcnow()
                task.progress = 100  # 完成时设置进度为100%
            await db.commit()

    @classmethod
    async def delete_old_tasks(cls, db: AsyncSession, older_than: datetime):
        """清理过期任务记录（软删除）"""
        stmt = update(ExportTask).where(
            ExportTask.completed_at < older_than,
            ExportTask.is_deleted == False
        ).values(is_deleted=True)
        await db.execute(stmt)
        await db.commit()

    @classmethod
    async def cleanup_export_files(cls):
        """清理过期导出文件和记录（定时任务）
        文件保留7天，记录保留7天后软删除
        """
        from app.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            # 清理文件（超过7天）
            cutoff_files = datetime.now() - timedelta(days=7)
            for file in TEMP_EXPORTS_DIR.glob("*.xlsx"):
                mtime = datetime.fromtimestamp(file.stat().st_mtime)
                if mtime < cutoff_files:
                    file.unlink()

            # 清理记录（超过7天）
            cutoff_tasks = datetime.utcnow() - timedelta(days=7)
            await cls.delete_old_tasks(db, cutoff_tasks)

    @classmethod
    async def process_export_task(cls, task_id: str):
        """后台任务执行（带超时检查）"""
        from app.database import AsyncSessionLocal

        start_time = time.time()

        async with AsyncSessionLocal() as db:
            try:
                await cls.update_progress(db, task_id, 0, "开始处理...")

                # 1. 解析参数
                task = await db.get(ExportTask, task_id)
                if not task:
                    return

                params = ExportTaskCreate.model_validate(task.params)
                version_ids = params.version_ids.split(",")

                # 超时检查
                if time.time() - start_time > EXPORT_TASK_TIMEOUT:
                    await cls.update_status(db, task_id, "failed", "导出超时")
                    return

                # 2. 获取对比数据（字典格式）
                await cls.update_progress(db, task_id, 10, "获取版本数据...")
                compare_data = await PerformanceVersionService.get_compare_data(db, version_ids)

                # 3. 获取对比标签（ORM 对象列表）
                compare_tags = await CompareTagService.get_tags(db)
                peak_tag = next((t for t in compare_tags if t.type == 'peak'), None)
                stable_tag = next((t for t in compare_tags if t.type == 'stable'), None)

                if time.time() - start_time > EXPORT_TASK_TIMEOUT:
                    await cls.update_status(db, task_id, "failed", "导出超时")
                    return

                # 4. 组织摘要数据
                await cls.update_progress(db, task_id, 30, "计算摘要数据...")
                summary_data = await ExportReportService.get_summary_data(
                    db, compare_data, peak_tag, stable_tag, params.metric, params.hwinfo_key
                )

                if time.time() - start_time > EXPORT_TASK_TIMEOUT:
                    await cls.update_status(db, task_id, "failed", "导出超时")
                    return

                # 5. 组织详细数据
                await cls.update_progress(db, task_id, 50, "组织详细数据...")
                detail_data = await ExportReportService.get_detail_data(
                    db, compare_data, params.metric, params.hwinfo_key
                )

                if time.time() - start_time > EXPORT_TASK_TIMEOUT:
                    await cls.update_status(db, task_id, "failed", "导出超时")
                    return

                # 6. 生成 Excel 文件
                await cls.update_progress(db, task_id, 70, "生成Excel文件...")
                file_path = ExcelHandler.create_compare_excel(
                    summary_data, detail_data, params.metric, params.hwinfo_key
                )

                # 7. 完成
                await cls.update_status(db, task_id, "completed", "导出完成", file_path)

            except Exception as e:
                logger.error(f"导出任务执行失败: {e}")
                await cls.update_status(db, task_id, "failed", str(e))


class ExportReportService:
    """导出报告数据组织服务"""

    @classmethod
    async def _get_hwinfo_unit(cls, db: AsyncSession, collect_id: str, hwinfo_key: str) -> str:
        """获取 HWiNFO 指标单位"""
        result = await PerformanceDataService.query_advanced_metrics(
            db, AdvancedMetricsQuery(collect_id=collect_id, metric_keys=[hwinfo_key])
        )
        return result.get("metrics", {}).get(hwinfo_key, {}).get("unit", "")

    @classmethod
    async def get_summary_data(
        cls,
        db: AsyncSession,
        compare_data: Dict,
        peak_tag,  # CompareTag ORM 对象或 None
        stable_tag,  # CompareTag ORM 对象或 None
        metric: str,
        hwinfo_key: Optional[str]
    ) -> SummaryData:
        """组织摘要数据

        注意：compare_data 是字典格式，使用字典访问方式
        peak_tag/stable_tag 是 ORM 对象，使用属性访问方式
        """
        basic_info = []
        peak_range = []
        steady_range = []

        # 根据指标确定列名和单位
        if metric == "cpu_usage":
            metric_columns = ["系统CPU峰值(%)", "进程CPU峰值(%)"]
            metric_unit = "%"
        elif metric == "gpu_usage":
            metric_columns = ["系统GPU峰值(%)", "进程GPU峰值(%)"]
            metric_unit = "%"
        elif metric == "memory_usage":
            metric_columns = ["内存峰值(GB)"]
            metric_unit = "GB"
        elif metric == "commit_memory":
            metric_columns = ["提交内存峰值(GB)"]
            metric_unit = "GB"
        elif metric == "process_handles":
            metric_columns = ["进程句柄峰值(个)"]
            metric_unit = "个"
        elif metric == "hwinfo":
            # 特殊处理：process_handles 是数据库字段，不是 HWiNFO 数据
            if hwinfo_key == "process_handles":
                metric_columns = ["进程句柄峰值(个)"]
                metric_unit = "个"
            else:
                # 直接从第一条数据的 hwinfo_raw 获取单位
                unit = ""
                if compare_data.get("versions") and compare_data["versions"][0].get("collects"):
                    first_data_points = compare_data["versions"][0]["collects"][0].get("data", [])
                    if first_data_points:
                        first_data = first_data_points[0]
                        hwinfo_raw = first_data.hwinfo_raw or {}
                        value_info = hwinfo_raw.get(hwinfo_key)
                        if value_info is not None and isinstance(value_info, dict):
                            unit = value_info.get("unit", "")
                metric_columns = [f"{hwinfo_key}峰值({unit})"]
                metric_unit = unit
        else:
            metric_columns = []
            metric_unit = ""

        for v in compare_data.get("versions", []):
            version_name = v["version"].name  # version 是 ORM 对象

            # 获取所有数据点
            all_data = []
            start_time = None
            end_time = None

            for c in v.get("collects", []):
                collect_start = c["collect"].start_time  # CollectResponse 是 Pydantic 对象
                if start_time is None or collect_start < start_time:
                    start_time = collect_start
                if c["collect"].end_time:
                    collect_end = c["collect"].end_time
                    if end_time is None or collect_end > end_time:
                        end_time = collect_end

                for d in c.get("data", []):
                    all_data.append(d)

            # 基本信息
            duration = 0
            if start_time and end_time:
                duration = int((end_time - start_time).total_seconds())

            basic_info.append({
                "版本名称": version_name,
                "采集开始时间": start_time.strftime("%Y-%m-%d %H:%M:%S") if start_time else "",
                "采集结束时间": end_time.strftime("%Y-%m-%d %H:%M:%S") if end_time else "",
                "采集时长(秒)": duration
            })

            # 计算峰值数据（冲高区间）- peak_tag 是 ORM 对象
            if peak_tag and all_data:
                version_start_rel = min(d.relative_time for d in all_data)  # DataResponse 是 Pydantic 对象
                peak_start_orig = peak_tag.start_time + version_start_rel
                peak_end_orig = peak_tag.end_time + version_start_rel

                peak_data = [d for d in all_data if peak_start_orig <= d.relative_time <= peak_end_orig]

                peak_abs_start = (start_time + timedelta(seconds=peak_start_orig)).strftime("%Y-%m-%d %H:%M:%S")
                peak_abs_end = (start_time + timedelta(seconds=peak_end_orig)).strftime("%Y-%m-%d %H:%M:%S")

                peak_row = {
                    "版本名称": version_name,
                    "冲高区间开始时间": peak_abs_start,
                    "冲高区间结束时间": peak_abs_end
                }

                if metric == "cpu_usage":
                    peak_row["系统CPU峰值(%)"] = max((float(d.cpu_usage or 0)) for d in peak_data) if peak_data else 0
                    peak_row["进程CPU峰值(%)"] = cls._calc_process_peak(peak_data, "cpu_usage")
                elif metric == "gpu_usage":
                    peak_row["系统GPU峰值(%)"] = max((float(d.gpu_usage or 0)) for d in peak_data) if peak_data else 0
                    peak_row["进程GPU峰值(%)"] = cls._calc_process_peak(peak_data, "gpu_usage")
                elif metric == "memory_usage":
                    peak_row["内存峰值(GB)"] = max((float(d.memory_usage or 0)) for d in peak_data) if peak_data else 0
                elif metric == "commit_memory":
                    peak_row["提交内存峰值(GB)"] = max((float(d.commit_memory or 0)) for d in peak_data) if peak_data else 0
                elif metric == "process_handles":
                    peak_row["进程句柄峰值(个)"] = max((int(d.process_handles or 0)) for d in peak_data) if peak_data else 0
                elif metric == "hwinfo" and hwinfo_key == "process_handles":
                    peak_row["进程句柄峰值(个)"] = max((int(d.process_handles or 0)) for d in peak_data) if peak_data else 0
                elif metric == "hwinfo":
                    # 从 hwinfo_raw 中获取峰值
                    col_name = f"{hwinfo_key}峰值({metric_unit})"
                    values = []
                    for d in peak_data:
                        hwinfo_raw = d.hwinfo_raw or {}
                        value_info = hwinfo_raw.get(hwinfo_key)
                        if value_info is not None:
                            if isinstance(value_info, dict):
                                v = value_info.get("value")
                            else:
                                v = value_info
                            if v is not None:
                                values.append(float(v))
                    peak_row[col_name] = max(values) if values else 0

                peak_range.append(peak_row)

            # 计算稳态数据（平均值）- stable_tag 是 ORM 对象
            if stable_tag and all_data:
                version_start_rel = min(d.relative_time for d in all_data)  # DataResponse 是 Pydantic 对象
                steady_start_orig = stable_tag.start_time + version_start_rel
                steady_end_orig = stable_tag.end_time + version_start_rel

                steady_data = [d for d in all_data if steady_start_orig <= d.relative_time <= steady_end_orig]

                steady_abs_start = (start_time + timedelta(seconds=steady_start_orig)).strftime("%Y-%m-%d %H:%M:%S")
                steady_abs_end = (start_time + timedelta(seconds=steady_end_orig)).strftime("%Y-%m-%d %H:%M:%S")

                steady_row = {
                    "版本名称": version_name,
                    "稳态区间开始时间": steady_abs_start,
                    "稳态区间结束时间": steady_abs_end
                }

                if metric == "cpu_usage":
                    steady_row["系统CPU峰值(%)"] = sum((float(d.cpu_usage or 0)) for d in steady_data) / len(steady_data) if steady_data else 0
                    steady_row["进程CPU峰值(%)"] = cls._calc_process_mean(steady_data, "cpu_usage")
                elif metric == "gpu_usage":
                    steady_row["系统GPU峰值(%)"] = sum((float(d.gpu_usage or 0)) for d in steady_data) / len(steady_data) if steady_data else 0
                    steady_row["进程GPU峰值(%)"] = cls._calc_process_mean(steady_data, "gpu_usage")
                elif metric == "memory_usage":
                    steady_row["内存峰值(GB)"] = sum((float(d.memory_usage or 0)) for d in steady_data) / len(steady_data) if steady_data else 0
                elif metric == "commit_memory":
                    steady_row["提交内存峰值(GB)"] = sum((float(d.commit_memory or 0)) for d in steady_data) / len(steady_data) if steady_data else 0
                elif metric == "process_handles":
                    steady_row["进程句柄峰值(个)"] = sum((int(d.process_handles or 0)) for d in steady_data) / len(steady_data) if steady_data else 0
                elif metric == "hwinfo" and hwinfo_key == "process_handles":
                    steady_row["进程句柄峰值(个)"] = sum((int(d.process_handles or 0)) for d in steady_data) / len(steady_data) if steady_data else 0
                elif metric == "hwinfo":
                    # 从 hwinfo_raw 中获取平均值
                    col_name = f"{hwinfo_key}峰值({metric_unit})"
                    values = []
                    for d in steady_data:
                        hwinfo_raw = d.hwinfo_raw or {}
                        value_info = hwinfo_raw.get(hwinfo_key)
                        if value_info is not None:
                            if isinstance(value_info, dict):
                                v = value_info.get("value")
                            else:
                                v = value_info
                            if v is not None:
                                values.append(float(v))
                    steady_row[col_name] = sum(values) / len(values) if values else 0

                steady_range.append(steady_row)

        return SummaryData(
            basic_info=basic_info,
            peak_range=peak_range,
            steady_range=steady_range,
            metric_unit=metric_unit,
            metric_columns=metric_columns
        )

    @staticmethod
    def _calc_process_peak(data, metric_type: str) -> float:
        """计算进程峰值"""
        if not data:
            return 0
        peaks = []
        for d in data:
            processes = d.target_processes or []  # DataResponse 是 Pydantic 对象
            total = sum(
                float(p.get("total_cpu" if metric_type == "cpu_usage" else "total_gpu", 0) or 0)
                for p in processes
            )
            peaks.append(total)
        return max(peaks) if peaks else 0

    @staticmethod
    def _calc_process_mean(data, metric_type: str) -> float:
        """计算进程平均值"""
        if not data:
            return 0
        totals = []
        for d in data:
            processes = d.target_processes or []  # DataResponse 是 Pydantic 对象
            total = sum(
                float(p.get("total_cpu" if metric_type == "cpu_usage" else "total_gpu", 0) or 0)
                for p in processes
            )
            totals.append(total)
        return sum(totals) / len(totals) if totals else 0

    @classmethod
    async def get_detail_data(
        cls,
        db: AsyncSession,
        compare_data: Dict,
        metric: str,
        hwinfo_key: Optional[str]
    ) -> Dict[str, DetailData]:
        """组织详细数据

        注意：compare_data 是字典格式，使用字典访问方式
        """
        detail_data = {}

        for v in compare_data.get("versions", []):
            version_name = v["version"].name  # version 是 ORM 对象

            for c in v.get("collects", []):
                collect_start = c["collect"].start_time  # CollectResponse 是 Pydantic 对象
                collect_id = c["collect"].id

                # CPU/GPU 需要系统页、进程汇总页和进程PID明细页
                if metric in ["cpu_usage", "gpu_usage"]:
                    metric_label = metric.split('_')[0].upper()

                    # 系统详细页
                    system_columns = ["相对时间(秒)", "绝对时间", f"系统{metric_label}使用率(%)"]
                    system_data = []
                    for d in c.get("data", []):
                        rel_time = d.relative_time  # DataResponse 是 Pydantic 对象
                        abs_time = (collect_start + timedelta(seconds=rel_time)).strftime("%Y-%m-%d %H:%M:%S")
                        value = float(getattr(d, metric, None) or 0)
                        system_data.append([rel_time, abs_time, value])

                    detail_data[f"{version_name}-系统{metric_label}详情"] = DetailData(
                        sheet_name=f"{version_name}-系统{metric_label}详情",
                        columns=system_columns,
                        data=system_data
                    )

                    # 进程汇总详细页
                    process_columns = ["相对时间(秒)", "绝对时间", f"进程{metric_label}使用率(%)"]
                    process_data = []
                    for d in c.get("data", []):
                        rel_time = d.relative_time  # DataResponse 是 Pydantic 对象
                        abs_time = (collect_start + timedelta(seconds=rel_time)).strftime("%Y-%m-%d %H:%M:%S")
                        processes = d.target_processes or []  # target_processes 是字典列表
                        total = sum(
                            float(p.get("total_cpu" if metric == "cpu_usage" else "total_gpu", 0) or 0)
                            for p in processes
                        )
                        process_data.append([rel_time, abs_time, total])

                    detail_data[f"{version_name}-进程{metric_label}详情"] = DetailData(
                        sheet_name=f"{version_name}-进程{metric_label}详情",
                        columns=process_columns,
                        data=process_data
                    )

                    # 进程PID明细页（每个时间点展开为多行，每行一个PID）
                    pid_columns = ["相对时间(秒)", "绝对时间", "进程名", "PID", f"{metric_label}使用率(%)"]
                    pid_data = []
                    for d in c.get("data", []):
                        rel_time = d.relative_time
                        abs_time = (collect_start + timedelta(seconds=rel_time)).strftime("%Y-%m-%d %H:%M:%S")
                        processes = d.target_processes or []
                        for proc in processes:
                            proc_name = proc.get("name", "")
                            instances = proc.get("instances", [])
                            for inst in instances:
                                pid = inst.get("pid", 0)
                                value = float(inst.get("cpu" if metric == "cpu_usage" else "gpu", 0) or 0)
                                pid_data.append([rel_time, abs_time, proc_name, pid, value])

                    detail_data[f"{version_name}-进程PID明细"] = DetailData(
                        sheet_name=f"{version_name}-进程PID明细",
                        columns=pid_columns,
                        data=pid_data
                    )

                # 内存/提交内存需要详情页和进程PID明细页
                elif metric in ["memory_usage", "commit_memory"]:
                    label = "内存" if metric == "memory_usage" else "提交内存"
                    unit = "GB"

                    # 详情页
                    columns = ["相对时间(秒)", "绝对时间", f"{label}({unit})"]
                    data_rows = []
                    for d in c.get("data", []):
                        rel_time = d.relative_time  # DataResponse 是 Pydantic 对象
                        abs_time = (collect_start + timedelta(seconds=rel_time)).strftime("%Y-%m-%d %H:%M:%S")
                        value = float(getattr(d, metric, None) or 0)
                        data_rows.append([rel_time, abs_time, value])

                    detail_data[f"{version_name}-{label}详情"] = DetailData(
                        sheet_name=f"{version_name}-{label}详情",
                        columns=columns,
                        data=data_rows
                    )

                    # 进程PID明细页（物理内存或虚拟内存）
                    pid_columns = ["相对时间(秒)", "绝对时间", "进程名", "PID", f"{label}(MB)"]
                    pid_data = []
                    value_key = "memory" if metric == "memory_usage" else "committed_memory"
                    for d in c.get("data", []):
                        rel_time = d.relative_time
                        abs_time = (collect_start + timedelta(seconds=rel_time)).strftime("%Y-%m-%d %H:%M:%S")
                        processes = d.target_processes or []
                        for proc in processes:
                            proc_name = proc.get("name", "")
                            instances = proc.get("instances", [])
                            for inst in instances:
                                pid = inst.get("pid", 0)
                                value = float(inst.get(value_key, 0) or 0)
                                pid_data.append([rel_time, abs_time, proc_name, pid, value])

                    detail_data[f"{version_name}-进程PID明细"] = DetailData(
                        sheet_name=f"{version_name}-进程PID明细",
                        columns=pid_columns,
                        data=pid_data
                    )

                # 进程句柄数需要详情页和进程PID明细页
                elif metric == "process_handles":
                    # 详情页
                    columns = ["相对时间(秒)", "绝对时间", "进程句柄数(个)"]
                    data_rows = []
                    for d in c.get("data", []):
                        rel_time = d.relative_time  # DataResponse 是 Pydantic 对象
                        abs_time = (collect_start + timedelta(seconds=rel_time)).strftime("%Y-%m-%d %H:%M:%S")
                        value = int(d.process_handles or 0)
                        data_rows.append([rel_time, abs_time, value])

                    detail_data[f"{version_name}-进程句柄详情"] = DetailData(
                        sheet_name=f"{version_name}-进程句柄详情",
                        columns=columns,
                        data=data_rows
                    )

                    # 进程PID明细页（每个进程的句柄数）
                    pid_columns = ["相对时间(秒)", "绝对时间", "进程名", "PID", "句柄数(个)"]
                    pid_data = []
                    for d in c.get("data", []):
                        rel_time = d.relative_time
                        abs_time = (collect_start + timedelta(seconds=rel_time)).strftime("%Y-%m-%d %H:%M:%S")
                        processes = d.target_processes or []
                        for proc in processes:
                            proc_name = proc.get("name", "")
                            instances = proc.get("instances", [])
                            for inst in instances:
                                pid = inst.get("pid", 0)
                                value = int(inst.get("handles", 0) or 0)
                                pid_data.append([rel_time, abs_time, proc_name, pid, value])

                    detail_data[f"{version_name}-进程PID明细"] = DetailData(
                        sheet_name=f"{version_name}-进程PID明细",
                        columns=pid_columns,
                        data=pid_data
                    )

                # HWiNFO 需单独查询（特殊处理 process_handles）
                elif metric == "hwinfo" and hwinfo_key:
                    # process_handles 是数据库字段，不是 HWiNFO 数据
                    if hwinfo_key == "process_handles":
                        # 详情页
                        columns = ["相对时间(秒)", "绝对时间", "进程句柄数(个)"]
                        data_rows = []
                        for d in c.get("data", []):
                            rel_time = d.relative_time
                            abs_time = (collect_start + timedelta(seconds=rel_time)).strftime("%Y-%m-%d %H:%M:%S")
                            value = int(d.process_handles or 0)
                            data_rows.append([rel_time, abs_time, value])

                        detail_data[f"{version_name}-进程句柄详情"] = DetailData(
                            sheet_name=f"{version_name}-进程句柄详情",
                            columns=columns,
                            data=data_rows
                        )

                        # 进程PID明细页（每个进程的句柄数）
                        pid_columns = ["相对时间(秒)", "绝对时间", "进程名", "PID", "句柄数(个)"]
                        pid_data = []
                        for d in c.get("data", []):
                            rel_time = d.relative_time
                            abs_time = (collect_start + timedelta(seconds=rel_time)).strftime("%Y-%m-%d %H:%M:%S")
                            processes = d.target_processes or []
                            for proc in processes:
                                proc_name = proc.get("name", "")
                                instances = proc.get("instances", [])
                                for inst in instances:
                                    pid = inst.get("pid", 0)
                                    value = int(inst.get("handles", 0) or 0)
                                    pid_data.append([rel_time, abs_time, proc_name, pid, value])

                        detail_data[f"{version_name}-进程PID明细"] = DetailData(
                            sheet_name=f"{version_name}-进程PID明细",
                            columns=pid_columns,
                            data=pid_data
                        )
                    else:
                        # 真正的 HWiNFO 数据 - 从第一条数据获取单位
                        unit = ""
                        first_data_points = c.get("data", [])
                        if first_data_points:
                            first_data = first_data_points[0]
                            hwinfo_raw = first_data.hwinfo_raw or {}
                            value_info = hwinfo_raw.get(hwinfo_key)
                            if value_info is not None and isinstance(value_info, dict):
                                unit = value_info.get("unit", "")
                        columns = ["相对时间(秒)", "绝对时间", f"{hwinfo_key}({unit})"]
                        data_rows = []

                        for d in c.get("data", []):
                            rel_time = d.relative_time
                            abs_time = (collect_start + timedelta(seconds=rel_time)).strftime("%Y-%m-%d %H:%M:%S")
                            # 从 hwinfo_raw 中获取值
                            hwinfo_raw = d.hwinfo_raw or {}
                            value_info = hwinfo_raw.get(hwinfo_key)
                            if value_info is not None:
                                # 处理两种格式：字典格式 {value: xxx, unit: xxx} 或直接值
                                if isinstance(value_info, dict):
                                    value = value_info.get("value")
                                else:
                                    value = value_info
                                if value is not None:
                                    data_rows.append([rel_time, abs_time, float(value)])

                        detail_data[f"{version_name}-{hwinfo_key}详情"] = DetailData(
                            sheet_name=f"{version_name}-{hwinfo_key}详情",
                            columns=columns,
                            data=data_rows
                        )

        return detail_data
