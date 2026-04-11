#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time: 2026-04-10
@File: upgrade_api.py
@Desc: Worker 升级管理 API 路由
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from core.env_machine.service import EnvMachineService
from core.env_machine.upgrade_schema import (
    UpgradeConfigResponse,
    UpgradeConfigUpdateRequest,
    WorkerUpgradeInfo,
    StartUpgradeRequest,
    BatchUpgradeRequest,
    BatchUpgradeResponse,
    UpgradeQueueItem,
    UpgradePreviewResponse,
)
from core.env_machine.upgrade_service import (
    WorkerUpgradeConfigService,
    WorkerUpgradeQueueService,
    UpgradeService,
    send_upgrade_to_worker,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upgrade", tags=["Worker升级管理"])


@router.get("/config", response_model=List[UpgradeConfigResponse], summary="获取升级配置列表")
async def get_upgrade_configs(db: AsyncSession = Depends(get_db)) -> List[UpgradeConfigResponse]:
    """获取所有升级配置"""
    configs = await WorkerUpgradeConfigService.get_all(db)
    return [UpgradeConfigResponse.model_validate(c) for c in configs]


@router.put("/config/{config_id}", response_model=UpgradeConfigResponse, summary="更新升级配置")
async def update_upgrade_config(
    config_id: str,
    data: UpgradeConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> UpgradeConfigResponse:
    """更新升级配置"""
    config = await WorkerUpgradeConfigService.update(
        db, config_id, data.version, data.download_url, data.note
    )
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    return UpgradeConfigResponse.model_validate(config)


@router.get("/worker/info", response_model=WorkerUpgradeInfo, summary="Worker获取升级信息")
async def get_worker_upgrade_info(
    device_type: str,
    db: AsyncSession = Depends(get_db),
) -> WorkerUpgradeInfo:
    """Worker 获取最新版本信息"""
    config = await WorkerUpgradeConfigService.get_by_device_type(db, device_type)
    if not config:
        raise HTTPException(status_code=404, detail="未找到该设备类型的升级配置")
    return WorkerUpgradeInfo(
        version=config.version,
        download_url=config.download_url,
    )


@router.post("/worker/start", summary="Worker手动触发升级")
async def worker_start_upgrade(
    data: StartUpgradeRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Worker 手动触发升级，将状态置为 upgrading"""
    machine = await EnvMachineService.get_by_id(db, data.machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="机器不存在")

    if machine.status != "online":
        raise HTTPException(status_code=400, detail=f"机器状态为 {machine.status}，无法升级")

    # 更新状态
    machine.status = "upgrading"
    await db.commit()

    # 更新 Redis 缓存（标记不可申请）
    from core.env_machine.pool_manager import EnvPoolManager
    await EnvPoolManager.remove_machine_from_cache(machine.id, machine.namespace)

    logger.info(f"Worker 手动触发升级: machine_id={data.machine_id}, version={data.version}")

    return {"status": "success", "message": "状态已更新为升级中"}


@router.post("/batch", response_model=BatchUpgradeResponse, summary="批量升级")
async def batch_upgrade(
    data: BatchUpgradeRequest,
    db: AsyncSession = Depends(get_db),
) -> BatchUpgradeResponse:
    """批量升级机器"""
    # 参数校验
    if data.machine_ids and (data.namespace or data.device_type):
        raise HTTPException(status_code=400, detail="machine_ids 与 namespace/device_type 不能同时使用")

    if not data.machine_ids and not data.namespace and not data.device_type:
        raise HTTPException(status_code=400, detail="请指定升级范围")

    response = await UpgradeService.batch_upgrade(
        db,
        machine_ids=data.machine_ids,
        namespace=data.namespace,
        device_type=data.device_type,
    )

    logger.info(f"批量升级完成: upgraded={response.upgraded_count}, waiting={response.waiting_count}, failed={response.failed_count}")

    return response


@router.get("/preview", response_model=UpgradePreviewResponse, summary="升级预览")
async def get_upgrade_preview(
    namespace: Optional[str] = None,
    device_type: Optional[str] = None,
    ip: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> UpgradePreviewResponse:
    """获取升级预览信息"""
    preview = await UpgradeService.get_preview(db, namespace, device_type, ip)
    return UpgradePreviewResponse(**preview)


@router.get("/queue", summary="升级队列查询")
async def get_upgrade_queue(
    namespace: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """获取升级队列列表"""
    items, total = await WorkerUpgradeQueueService.get_list(db, namespace, status)

    # 补充 IP 信息
    result_list = []
    for item in items:
        machine = await EnvMachineService.get_by_id(db, item.machine_id)
        result_list.append(UpgradeQueueItem(
            id=item.id,
            machine_id=item.machine_id,
            ip=machine.ip if machine else "-",
            device_type=item.device_type,
            target_version=item.target_version,
            status=item.status,
            created_at=item.created_at,
        ))

    return {"items": result_list, "total": total}


@router.delete("/queue/{queue_id}", summary="移除升级队列")
async def remove_upgrade_queue(
    queue_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """移除升级队列项"""
    success = await WorkerUpgradeQueueService.delete_by_id(db, queue_id)
    if not success:
        raise HTTPException(status_code=400, detail="队列项不存在或状态非 waiting")
    return {"status": "success", "message": "队列项已移除"}