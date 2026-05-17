#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控 API 路由
"""
import httpx
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from core.performance_monitor.model import PerformanceCollect, PerformanceVersion, ExportTask
from core.env_machine.model import EnvMachine
from core.performance_monitor.schema import (
    CollectStartRequest, CollectStopRequest,
    TagCreateRequest, TagUpdateRequest,
    VersionCreateRequest,
    # Response Schema（用于正确序列化 datetime）
    CollectResponse, DataResponse, PaginatedResponse,
    # v0.3.1
    WorkerReportRequestV3, MetricMappingCreate, MetricMappingUpdate, MetricMappingResponse,
    MarkerCreate, MarkerUpdate, MarkerResponse, AdvancedMetricsQuery, AdvancedMetricsResponse,
    # 导出任务 Schema
    ExportTaskCreate, ExportTaskStatus, ExportTaskCreateResponse
)
from core.performance_monitor.compare_schema import CompareTagCreate, CompareTagUpdate, CompareTagResponse
from core.performance_monitor.service import (
    PerformanceCollectService, PerformanceDataService,
    PerformanceTagService, PerformanceVersionService,
    # v0.3.0 新增
    MetricMappingService, MarkerService,
    # v0.3.2 新增
    CompareTagService,
    # 导出任务服务
    ExportTaskService
)
from utils.excel import TEMP_EXPORTS_DIR

router = APIRouter(prefix="/performance-monitor", tags=["性能监控"])


# ===== 进程列表 =====

@router.get("/processes")
async def get_processes(
    device_id: str,
    search: Optional[str] = Query(None, description="模糊搜索进程名"),
    db: AsyncSession = Depends(get_db)
):
    """获取设备进程列表（代理 worker API）"""
    # 从数据库获取设备信息
    stmt = select(EnvMachine).where(EnvMachine.id == device_id, EnvMachine.is_deleted == False)
    result = await db.execute(stmt)
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    # 构建 worker URL
    worker_url = f"http://{device.ip}:{device.port}/api/worker/{device_id}/processes"

    # 调用 worker API
    try:
        async with httpx.AsyncClient(timeout=10.0, trust_env=False, verify=False) as client:
            params = {}
            if search:
                params["search"] = search
            resp = await client.get(worker_url, params=params)
            if resp.status_code == 200:
                return resp.json()
            else:
                raise HTTPException(status_code=resp.status_code, detail=f"Worker 返回错误: {resp.text}")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail=f"无法连接到 Worker: {device.ip}:{device.port}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Worker 响应超时")


# ===== 采集管理 =====

@router.post("/collect/start")
async def start_collect(request: CollectStartRequest, db: AsyncSession = Depends(get_db)):
    """开始采集"""
    # 1. 保存采集记录到数据库
    collect_id = await PerformanceCollectService.start_collect(db, request)

    # 2. 从数据库获取设备信息
    stmt = select(EnvMachine).where(EnvMachine.id == request.device_id, EnvMachine.is_deleted == False)
    result = await db.execute(stmt)
    device = result.scalar_one_or_none()

    if device:
        # 3. 转发采集请求给 worker
        worker_url = f"http://{device.ip}:{device.port}/api/worker/{request.device_id}/collect/start"
        try:
            async with httpx.AsyncClient(timeout=10.0, trust_env=False, verify=False) as client:
                # 构造 worker 请求参数（包含 collect_id）
                worker_request = {
                    "collect_id": collect_id,
                    "interval": request.interval,
                    "timeout": 43200,  # 默认12小时
                    "target_processes": request.target_processes or []
                }
                resp = await client.post(worker_url, json=worker_request)
                if resp.status_code != 200:
                    # worker 失败时更新状态
                    await PerformanceCollectService.stop_collect(db, collect_id, request.device_id)
                    raise HTTPException(status_code=resp.status_code, detail=f"Worker 返回错误: {resp.text}")
        except httpx.ConnectError:
            await PerformanceCollectService.stop_collect(db, collect_id, request.device_id)
            raise HTTPException(status_code=503, detail=f"无法连接到 Worker: {device.ip}:{device.port}")
        except httpx.TimeoutException:
            await PerformanceCollectService.stop_collect(db, collect_id, request.device_id)
            raise HTTPException(status_code=504, detail="Worker 响应超时")

    return {"collect_id": collect_id, "status": "started"}


@router.post("/collect/stop")
async def stop_collect(request: CollectStopRequest, db: AsyncSession = Depends(get_db)):
    """停止采集"""
    # 1. 更新数据库状态
    success = await PerformanceCollectService.stop_collect(db, request.collect_id, request.device_id)

    # 2. 从数据库获取设备信息
    stmt = select(EnvMachine).where(EnvMachine.id == request.device_id, EnvMachine.is_deleted == False)
    result = await db.execute(stmt)
    device = result.scalar_one_or_none()

    if device:
        # 3. 转发停止请求给 worker
        worker_url = f"http://{device.ip}:{device.port}/api/worker/{request.device_id}/collect/stop"
        try:
            async with httpx.AsyncClient(timeout=10.0, trust_env=False, verify=False) as client:
                worker_request = {"collect_id": request.collect_id} if request.collect_id else {}
                resp = await client.post(worker_url, json=worker_request)
                if resp.status_code != 200:
                    raise HTTPException(status_code=resp.status_code, detail=f"Worker 返回错误: {resp.text}")
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail=f"无法连接到 Worker: {device.ip}:{device.port}")
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Worker 响应超时")

    return {"status": "stopped" if success else "not_found"}


@router.get("/collect/status")
async def get_collect_status(device_id: str, db: AsyncSession = Depends(get_db)):
    """获取采集状态"""
    status = await PerformanceCollectService.get_collect_status(db, device_id)
    return status


@router.get("/collect/list")
async def get_collect_list(
    device_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """获取采集列表"""
    result = await PerformanceCollectService.get_collect_list(db, device_id, page, page_size)
    # 使用 Response Schema 包装数据，确保 datetime 序列化带 UTC 标识
    items = [CollectResponse.model_validate(item) for item in result["items"]]
    return {"total": result["total"], "items": items}


@router.get("/collect/{collect_id}")
async def get_collect_detail(collect_id: str, db: AsyncSession = Depends(get_db)):
    """获取采集详情"""
    collect = await db.get(PerformanceCollect, collect_id)
    if collect:
        return CollectResponse.model_validate(collect)
    return None


@router.get("/collect/{collect_id}/data")
async def get_collect_data(
    collect_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    """获取采集数据（分页，从最老数据开始）"""
    result = await PerformanceDataService.get_collect_data(db, collect_id, page, page_size)
    # 使用 Response Schema 包装数据，确保 datetime 序列化带 UTC 标识
    items = [DataResponse.model_validate(item) for item in result["items"]]
    return {"total": result["total"], "items": items}


@router.get("/collect/{collect_id}/data/range")
async def get_collect_data_by_range(
    collect_id: str,
    start_time: int = Query(0, ge=0, description="开始时间（相对秒数）"),
    end_time: int = Query(0, ge=0, description="结束时间（相对秒数）"),
    db: AsyncSession = Depends(get_db)
):
    """按时间范围获取采集数据（用于查看特定时间窗口，如最近15分钟）"""
    items = await PerformanceDataService.get_collect_data_by_range(db, collect_id, start_time, end_time)
    validated_items = [DataResponse.model_validate(item) for item in items]
    return {"items": validated_items}


@router.get("/collect/{collect_id}/latest")
async def get_latest_data(collect_id: str, limit: int = Query(10, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    """获取最新数据"""
    items = await PerformanceDataService.get_latest_data(db, collect_id, limit)
    # 使用 Response Schema 包装数据，确保 datetime 序列化带 UTC 标识
    validated_items = [DataResponse.model_validate(item) for item in items]
    return {"items": validated_items}


@router.delete("/collect/{collect_id}")
async def delete_collect(collect_id: str, db: AsyncSession = Depends(get_db)):
    """删除采集记录及其所有数据"""
    success = await PerformanceCollectService.delete_collect(db, collect_id)
    return {"status": "deleted" if success else "not_found"}


@router.put("/collect/{collect_id}/protected")
async def set_collect_protected(
    collect_id: str,
    request: dict,
    db: AsyncSession = Depends(get_db)
):
    """设置采集记录保护状态"""
    is_protected = request.get("is_protected", False)
    success = await PerformanceCollectService.set_protected(db, collect_id, is_protected)
    return {"status": "updated" if success else "not_found"}


# ===== 数据上报 =====

@router.post("/report")
async def report_data(request: WorkerReportRequestV3, db: AsyncSession = Depends(get_db)):
    """Worker 上报数据（v0.3.1）"""
    success = await PerformanceDataService.report_data(db, request)
    return {"status": "success" if success else "failed"}


# ===== 标签管理 =====

@router.post("/tag/create")
async def create_tag(request: TagCreateRequest, db: AsyncSession = Depends(get_db)):
    """创建标签"""
    tag_id = await PerformanceTagService.create_tag(db, request)
    return {"tag_id": tag_id, "status": "created"}


@router.get("/tag/list")
async def get_tags(collect_id: str, db: AsyncSession = Depends(get_db)):
    """获取标签列表"""
    tags = await PerformanceTagService.get_tags(db, collect_id)
    return {"items": tags}


@router.put("/tag/update")
async def update_tag(tag_id: str, request: TagUpdateRequest, db: AsyncSession = Depends(get_db)):
    """更新标签"""
    success = await PerformanceTagService.update_tag(db, tag_id, name=request.name,
                                       start_relative_time=request.start_relative_time,
                                       duration=request.duration, type=request.type)
    return {"status": "updated" if success else "not_found"}


@router.delete("/tag/delete")
async def delete_tag(tag_id: str, db: AsyncSession = Depends(get_db)):
    """删除标签"""
    success = await PerformanceTagService.delete_tag(db, tag_id)
    return {"status": "deleted" if success else "not_found"}


# ===== 版本对比 =====

@router.post("/version/create")
async def create_version(request: VersionCreateRequest, db: AsyncSession = Depends(get_db)):
    """创建版本"""
    version_id = await PerformanceVersionService.create_version(db, request)
    return {"version_id": version_id, "status": "created"}


@router.get("/version/list")
async def get_versions(
    device_id: Optional[str] = Query(None, description="设备ID（可选，不传则返回所有）"),
    db: AsyncSession = Depends(get_db)
):
    """获取版本列表（包含时间区间）"""
    versions = await PerformanceVersionService.get_versions(db, device_id)

    # 计算每个版本的时间区间
    items = []
    for v in versions:
        start_time = None
        end_time = None

        # 如果有 time_ranges，根据标记的相对时间计算绝对时间
        if v.time_ranges:
            for cid, range_info in v.time_ranges.items():
                collect = await db.get(PerformanceCollect, cid)
                if collect and collect.start_time:
                    # 根据采集开始时间 + 相对时间偏移计算绝对时间
                    rel_start = range_info.get("start", 0)
                    rel_end = range_info.get("end")

                    abs_start = datetime.fromtimestamp(
                        collect.start_time.timestamp() + rel_start
                    )
                    if start_time is None or abs_start < start_time:
                        start_time = abs_start

                    if rel_end is not None:
                        abs_end = datetime.fromtimestamp(
                            collect.start_time.timestamp() + rel_end
                        )
                        if end_time is None or abs_end > end_time:
                            end_time = abs_end
        else:
            # 没有 time_ranges，使用采集记录的时间范围
            for cid in v.collect_ids:
                collect = await db.get(PerformanceCollect, cid)
                if collect:
                    if start_time is None or collect.start_time < start_time:
                        start_time = collect.start_time
                    if collect.end_time and (end_time is None or collect.end_time > end_time):
                        end_time = collect.end_time

        items.append({
            "id": v.id,
            "device_id": v.device_id,
            "name": v.name,
            "collect_ids": v.collect_ids,
            "is_protected": v.is_protected,
            "sys_create_datetime": v.sys_create_datetime,
            "start_time": start_time,
            "end_time": end_time,
            "time_ranges": v.time_ranges,
        })

    return {"items": items}


@router.get("/version/compare")
async def get_compare_data(version_ids: str, db: AsyncSession = Depends(get_db)):
    """获取版本对比数据"""
    ids = version_ids.split(",")
    result = await PerformanceVersionService.get_compare_data(db, ids)
    return result


# ===== 指标映射管理（v0.3.0）=====

@router.get("/metric-mapping/list")
async def get_metric_mappings(
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取指标映射列表"""
    mappings = await MetricMappingService.get_mappings(db, keyword, category)
    return {"items": [MetricMappingResponse.model_validate(m) for m in mappings]}


@router.post("/metric-mapping")
async def create_metric_mapping(request: MetricMappingCreate, db: AsyncSession = Depends(get_db)):
    """创建指标映射"""
    mapping_id = await MetricMappingService.create_mapping(db, request)
    return {"id": mapping_id, "status": "created"}


@router.put("/metric-mapping/{mapping_id}")
async def update_metric_mapping(mapping_id: str, request: MetricMappingUpdate, db: AsyncSession = Depends(get_db)):
    """更新指标映射"""
    success = await MetricMappingService.update_mapping(db, mapping_id, request)
    return {"status": "updated" if success else "not_found"}


@router.delete("/metric-mapping/{mapping_id}")
async def delete_metric_mapping(mapping_id: str, db: AsyncSession = Depends(get_db)):
    """删除指标映射"""
    success = await MetricMappingService.delete_mapping(db, mapping_id)
    return {"status": "deleted" if success else "not_found"}


@router.post("/metric-mapping/batch-import")
async def batch_import_mappings(
    collect_id: str = Query(..., description="采集记录ID"),
    db: AsyncSession = Depends(get_db)
):
    """批量导入未映射的传感器"""
    result = await MetricMappingService.batch_import(db, collect_id)
    return result


# ===== 标记管理（v0.3.0）=====

@router.get("/marker/list")
async def get_markers(collect_id: str, db: AsyncSession = Depends(get_db)):
    """获取标记列表"""
    markers = await MarkerService.get_markers(db, collect_id)
    return {"items": [MarkerResponse.model_validate(m) for m in markers]}


@router.post("/marker")
async def create_marker(request: MarkerCreate, db: AsyncSession = Depends(get_db)):
    """创建标记"""
    marker_id = await MarkerService.create_marker(db, request)
    return {"id": marker_id, "status": "created"}


@router.put("/marker/{marker_id}")
async def update_marker(marker_id: str, request: MarkerUpdate, db: AsyncSession = Depends(get_db)):
    """更新标记"""
    success = await MarkerService.update_marker(db, marker_id, request)
    return {"status": "updated" if success else "not_found"}


@router.delete("/marker/{marker_id}")
async def delete_marker(marker_id: str, db: AsyncSession = Depends(get_db)):
    """删除标记"""
    success = await MarkerService.delete_marker(db, marker_id)
    return {"status": "deleted" if success else "not_found"}


# ===== 高级指标查询 =====

@router.get("/metrics/list")
async def get_available_metrics(collect_id: str, db: AsyncSession = Depends(get_db)):
    """
    获取采集记录可用的指标列表

    从 hwinfo_raw 中动态提取所有键名，加上固定的非 HWiNFO 指标
    """
    metrics = await PerformanceDataService.get_available_metrics(db, collect_id)
    return {"items": metrics}


@router.post("/metrics/query")
async def query_advanced_metrics(request: AdvancedMetricsQuery, db: AsyncSession = Depends(get_db)):
    """查询高级指标"""
    result = await PerformanceDataService.query_advanced_metrics(db, request)
    return {"metrics": result}


# ===== 版本导出 =====

@router.post("/version/export/create")
async def create_export_task(
    request: ExportTaskCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """创建导出任务"""
    # 1. 验证版本数量
    version_ids = request.version_ids.split(",")
    if len(version_ids) > 6:
        raise HTTPException(status_code=400, detail="最多支持6个版本对比")

    # 2. 验证 HWiNFO 参数
    if request.metric == "hwinfo" and not request.hwinfo_key:
        raise HTTPException(status_code=400, detail="请指定 HWiNFO 指标")

    # 3. 验证版本存在
    for vid in version_ids:
        version = await db.get(PerformanceVersion, vid)
        if not version:
            raise HTTPException(status_code=404, detail=f"版本 {vid} 不存在")

    # 4. 检查重复任务
    existing = await ExportTaskService.get_pending_task(db, request)
    if existing:
        return ExportTaskStatus(
            task_id=existing.id,
            status=existing.status,
            progress=existing.progress,
            message="已有相同任务正在进行"
        )

    # 5. 创建任务（TODO: 从认证获取用户ID，暂时使用 system）
    task = await ExportTaskService.create_task(db, request, "system")

    # 6. 启动后台任务
    background_tasks.add_task(ExportTaskService.process_export_task, task.id)

    return ExportTaskCreateResponse(
        task_id=task.id,
        status="pending",
        message="任务已创建"
    )


@router.get("/version/export/status/{task_id}")
async def get_export_status(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    """查询任务状态

    权限验证：仅任务创建者可查询（暂时跳过，后续添加认证）
    """
    task = await db.get(ExportTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # TODO: 添加权限验证
    # if task.sys_creator_id != current_user.id and not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="无权访问该任务")

    return ExportTaskStatus(
        task_id=task.id,
        status=task.status,
        progress=task.progress,
        message=task.message or ""
    )


@router.get("/version/export/download/{task_id}")
async def download_export_file(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    """下载导出文件

    权限验证：仅任务创建者可下载（暂时跳过，后续添加认证）
    """
    task = await db.get(ExportTask, task_id)

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status != "completed":
        raise HTTPException(status_code=400, detail="任务未完成")

    # TODO: 添加权限验证
    # if task.sys_creator_id != current_user.id and not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="无权下载该文件")

    # 处理文件路径（确保是绝对路径）
    raw_path = task.file_path
    if not raw_path:
        raise HTTPException(status_code=404, detail="文件路径为空，导出可能失败")

    # 如果是相对路径，转换为绝对路径（相对于 TEMP_EXPORTS_DIR）
    file_path = Path(raw_path)
    if not file_path.is_absolute():
        file_path = TEMP_EXPORTS_DIR / raw_path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_path}")

    filename = quote(file_path.name)

    return StreamingResponse(
        file_path.open("rb"),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    )


# ===== 对比标签管理（v0.3.2）=====

@router.post("/compare/tag")
async def create_compare_tag(
    request: CompareTagCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建对比标签"""
    tag_id = await CompareTagService.create_tag(db, request)
    return {"id": tag_id, "status": "created"}


@router.get("/compare/tags")
async def get_compare_tags(db: AsyncSession = Depends(get_db)):
    """获取对比标签列表"""
    tags = await CompareTagService.get_tags(db)
    items = []
    for t in tags:
        item = CompareTagResponse.model_validate(t)
        item.type_display = t.get_type_display()
        items.append(item)
    return {"items": items}


@router.put("/compare/tag/{tag_id}")
async def update_compare_tag(
    tag_id: str,
    request: CompareTagUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新对比标签"""
    success = await CompareTagService.update_tag(db, tag_id, request)
    return {"status": "updated" if success else "not_found"}


@router.delete("/compare/tag/{tag_id}")
async def delete_compare_tag(
    tag_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除对比标签"""
    success = await CompareTagService.delete_tag(db, tag_id)
    return {"status": "deleted" if success else "not_found"}