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
    WorkerReportRequest, TagCreateRequest, TagUpdateRequest,
    VersionCreateRequest
)
from core.performance_monitor.service import (
    PerformanceCollectService, PerformanceDataService,
    PerformanceTagService, PerformanceVersionService
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
        async with httpx.AsyncClient(timeout=10.0, trust_env=True, verify=False) as client:
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
    collect_id = await PerformanceCollectService.start_collect(db, request)
    return {"collect_id": collect_id, "status": "started"}


@router.post("/collect/stop")
async def stop_collect(request: CollectStopRequest, db: AsyncSession = Depends(get_db)):
    """停止采集"""
    success = await PerformanceCollectService.stop_collect(db, request.collect_id, request.device_id)
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
    return result


@router.get("/collect/{collect_id}")
async def get_collect_detail(collect_id: str, db: AsyncSession = Depends(get_db)):
    """获取采集详情"""
    collect = await db.get(PerformanceCollect, collect_id)
    return collect


@router.get("/collect/{collect_id}/data")
async def get_collect_data(
    collect_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    """获取采集数据"""
    result = await PerformanceDataService.get_collect_data(db, collect_id, page, page_size)
    return result


@router.get("/collect/{collect_id}/latest")
async def get_latest_data(collect_id: str, limit: int = Query(10, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    """获取最新数据"""
    items = await PerformanceDataService.get_latest_data(db, collect_id, limit)
    return {"items": items}


# ===== 数据上报 =====

@router.post("/report")
async def report_data(request: WorkerReportRequest, db: AsyncSession = Depends(get_db)):
    """Worker 上报数据"""
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
async def get_versions(device_id: str, db: AsyncSession = Depends(get_db)):
    """获取版本列表"""
    versions = await PerformanceVersionService.get_versions(db, device_id)
    return {"items": versions}


@router.get("/version/compare")
async def get_compare_data(version_ids: str, db: AsyncSession = Depends(get_db)):
    """获取版本对比数据"""
    ids = version_ids.split(",")
    result = await PerformanceVersionService.get_compare_data(db, ids)
    return result