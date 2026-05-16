#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控 API 路由
"""
import httpx
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from core.performance_monitor.model import PerformanceCollect
from core.env_machine.model import EnvMachine
from core.performance_monitor.schema import (
    CollectStartRequest, CollectStopRequest,
    TagCreateRequest, TagUpdateRequest,
    VersionCreateRequest,
    # Response Schema（用于正确序列化 datetime）
    CollectResponse, DataResponse, PaginatedResponse,
    # v0.3.1
    WorkerReportRequestV3, MetricMappingCreate, MetricMappingUpdate, MetricMappingResponse,
    MarkerCreate, MarkerUpdate, MarkerResponse, AdvancedMetricsQuery, AdvancedMetricsResponse
)
from core.performance_monitor.compare_schema import CompareTagCreate, CompareTagUpdate, CompareTagResponse
from core.performance_monitor.service import (
    PerformanceCollectService, PerformanceDataService,
    PerformanceTagService, PerformanceVersionService,
    # v0.3.0 新增
    MetricMappingService, MarkerService,
    # v0.3.2 新增
    CompareTagService
)

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
    """获取版本列表"""
    versions = await PerformanceVersionService.get_versions(db, device_id)
    return {"items": versions}


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


# ===== 版本导出（v0.3.0）=====

@router.get("/version/export/html")
async def export_html_report(
    version_ids: str = Query(..., description="版本ID列表，逗号分隔，最多6个"),
    db: AsyncSession = Depends(get_db)
):
    """
    导出HTML报告

    Args:
        version_ids: 版本ID列表，逗号分隔

    Returns:
        HTML文件下载响应
    """
    ids = version_ids.split(",")
    if len(ids) > 6:
        raise HTTPException(status_code=400, detail="最多支持6个版本对比")

    # TODO: 实现HTML报告生成逻辑
    # 1. 获取对比数据
    # 2. 使用模板引擎生成HTML
    # 3. 返回StreamingResponse

    raise HTTPException(status_code=501, detail="导出HTML功能待实现")


@router.get("/version/export/excel")
async def export_excel_data(
    version_ids: str = Query(..., description="版本ID列表，逗号分隔，最多6个"),
    db: AsyncSession = Depends(get_db)
):
    """
    导出Excel数据明细

    Args:
        version_ids: 版本ID列表，逗号分隔

    Returns:
        Excel文件下载响应
    """
    ids = version_ids.split(",")
    if len(ids) > 6:
        raise HTTPException(status_code=400, detail="最多支持6个版本对比")

    # TODO: 实现Excel数据导出逻辑
    # 1. 获取对比数据
    # 2. 使用pandas/openpyxl生成Excel
    # 3. 返回StreamingResponse

    raise HTTPException(status_code=501, detail="导出Excel功能待实现")
    return result


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