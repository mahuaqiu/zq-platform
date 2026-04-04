#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2025-03-25
@File: api.py
@Desc: 执行机管理 API - 注册、申请、保持使用、释放、CRUD 接口
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_schema import PaginatedResponse
from app.database import get_db
from core.env_machine.model import EnvMachine
from core.env_machine.schema import (
    EnvRegisterRequest,
    EnvMachineIdItem,
    EnvSuccessResponse,
    EnvFailResponse,
    EnvMachineListRequest,
    EnvMachineCreateRequest,
    EnvMachineUpdateRequest,
    EnvMachineResponse,
)
from core.env_machine.service import EnvMachineService
from core.env_machine.pool_manager import EnvPoolManager
from core.env_machine.scheduler import modify_release_job, remove_release_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/env", tags=["执行机管理"])


@router.post("/register", response_model=EnvSuccessResponse, summary="执行机注册")
async def register_env_machine(
    data: EnvRegisterRequest,
    db: AsyncSession = Depends(get_db)
) -> EnvSuccessResponse:
    """
    执行机注册接口

    执行机启动时调用此接口注册自身信息。

    逻辑：
    1. 遍历 devices 字典
    2. 对于每个 device_type：
       - windows/mac：device_sn 为 null，每个 IP 插入一条记录
       - android/ios：根据 device_sn 列表，每个 sn 插入一条记录
    3. 查询条件：namespace + ip + device_type + device_sn
    4. 不存在则插入：状态设为 online，available 设为 False
    5. 存在则更新 sync_time、status=online
    6. 同步更新 Redis 缓存
    """
    now = datetime.now()

    try:
        # 遍历 devices 字典
        for device_type, device_sns in data.devices.items():
            if device_type in ("windows", "mac"):
                # Windows/Mac：device_sn 为 null，每个 IP 插入一条记录
                existing_machine = await EnvMachineService.get_by_namespace_and_device(
                    db,
                    namespace=data.namespace,
                    ip=data.ip,
                    device_type=device_type,
                    device_sn=None
                )

                if existing_machine:
                    # 存在则更新 sync_time 和 status
                    existing_machine.sync_time = now
                    existing_machine.status = "online"
                    existing_machine.port = data.port
                    if data.version:
                        existing_machine.version = data.version
                else:
                    # 不存在则插入
                    new_machine = EnvMachine(
                        namespace=data.namespace,
                        ip=data.ip,
                        port=data.port,
                        device_type=device_type,
                        device_sn=None,
                        status="online",
                        available=False,
                        sync_time=now,
                        version=data.version,
                    )
                    db.add(new_machine)

            elif device_type in ("android", "ios"):
                # Android/iOS：根据 device_sn 列表，每个 sn 插入一条记录
                for device_sn in device_sns:
                    if not device_sn:
                        continue

                    existing_machine = await EnvMachineService.get_by_namespace_and_device(
                        db,
                        namespace=data.namespace,
                        ip=data.ip,
                        device_type=device_type,
                        device_sn=device_sn
                    )

                    if existing_machine:
                        # 存在则更新 sync_time 和 status
                        existing_machine.sync_time = now
                        existing_machine.status = "online"
                        existing_machine.port = data.port
                        if data.version:
                            existing_machine.version = data.version
                    else:
                        # 不存在则插入
                        new_machine = EnvMachine(
                            namespace=data.namespace,
                            ip=data.ip,
                            port=data.port,
                            device_type=device_type,
                            device_sn=device_sn,
                            status="online",
                            available=False,
                            sync_time=now,
                            version=data.version,
                        )
                        db.add(new_machine)

        # 提交数据库更改
        await db.commit()

        # 同步更新 Redis 缓存（查询所有相关的机器）
        # 注意：注册时 available=False，所以不会加入缓存，但如果之前 available=True，需要从缓存移除
        # 这里统一刷新缓存状态
        machines, _ = await EnvMachineService.get_by_namespace(db, data.namespace, page=1, page_size=1000)
        for machine in machines:
            if machine.ip == data.ip:
                await EnvPoolManager.sync_machine_to_cache(machine)

        logger.info(f"执行机注册成功: namespace={data.namespace}, ip={data.ip}")

        return EnvSuccessResponse(status="success", data=None)
    except Exception as e:
        await db.rollback()
        logger.error(f"执行机注册失败: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@router.post(
    "/{namespace}/application",
    summary="申请执行机"
)
async def apply_env_machines(
    namespace: str,
    data: Dict[str, str],
    db: AsyncSession = Depends(get_db)
) -> Union[EnvSuccessResponse, EnvFailResponse]:
    """
    申请执行机接口

    从指定 namespace 的机器池中申请机器。

    请求：
    ```json
    {
        "userA": "windows",
        "userB": "web"
    }
    ```

    成功响应：
    ```json
    {
        "status": "success",
        "data": {
            "userA": {
                "id": "xxx",
                "ip": "10.173.94.49",
                "port": "8088",
                "device_type": "windows",
                "device_sn": null,
                ...
            },
            "userB": {...}
        }
    }
    ```

    失败响应：
    ```json
    {
        "status": "fail",
        "result": "env not enough"
    }
    ```
    """
    try:
        # 调用池管理器分配机器
        success, result = await EnvPoolManager.allocate_machines(db, namespace, data)

        if success:
            logger.info(f"执行机申请成功: namespace={namespace}, allocations={list(result.keys())}")
            return EnvSuccessResponse(status="success", data=result)
        else:
            logger.warning(f"执行机申请失败: namespace={namespace}, reason={result}")
            return EnvFailResponse(status="fail", result=result)
    except Exception as e:
        await db.rollback()
        logger.error(f"执行机申请失败: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@router.post("/keepusing", response_model=EnvSuccessResponse, summary="保持使用执行机")
async def keepusing_env_machines(
    data: List[EnvMachineIdItem],
    db: AsyncSession = Depends(get_db)
) -> EnvSuccessResponse:
    """
    保持使用执行机接口

    延长执行机的使用时间，防止被自动释放。

    逻辑：
    1. 遍历请求中的机器 ID
    2. 对于每台机器：更新 last_keepusing_time，延迟释放任务执行时间
    3. 忽略不存在或非 using 状态的机器
    """
    now = datetime.now()

    try:
        for item in data:
            machine = await EnvMachineService.get_by_id(db, item.id)

            if not machine:
                logger.debug(f"机器不存在，忽略: {item.id}")
                continue

            if machine.status != "using":
                logger.debug(f"机器状态非 using，忽略: {item.id}, status={machine.status}")
                continue

            # 更新最后保持使用时间
            machine.last_keepusing_time = now

            # 延迟释放任务执行时间
            await modify_release_job(item.id)

        # 提交数据库更改
        await db.commit()

        logger.info(f"保持使用执行机成功: count={len(data)}")

        return EnvSuccessResponse(status="success", data=None)
    except Exception as e:
        await db.rollback()
        logger.error(f"保持使用执行机失败: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@router.post("/release", response_model=EnvSuccessResponse, summary="释放执行机")
async def release_env_machines(
    data: List[EnvMachineIdItem],
    db: AsyncSession = Depends(get_db)
) -> EnvSuccessResponse:
    """
    释放执行机接口

    释放已申请的执行机，使其重新可用。

    逻辑：
    1. 遍历请求中的机器 ID
    2. 对于每台机器：取消延迟释放任务，更新状态为 online
    3. 同步 Redis 缓存
    4. 忽略不存在的机器
    """
    try:
        for item in data:
            machine = await EnvMachineService.get_by_id(db, item.id)

            if not machine:
                logger.debug(f"机器不存在，忽略: {item.id}")
                continue

            # 取消延迟释放任务
            await remove_release_job(item.id)

            # 更新状态为 online
            machine.status = "online"
            machine.last_keepusing_time = None

            # 同步 Redis 缓存
            await EnvPoolManager.sync_machine_to_cache(machine)

        # 提交数据库更改
        await db.commit()

        logger.info(f"释放执行机成功: count={len(data)}")

        return EnvSuccessResponse(status="success", data=None)
    except Exception as e:
        await db.rollback()
        logger.error(f"释放执行机失败: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@router.get("", response_model=PaginatedResponse[EnvMachineResponse], summary="查询执行机列表")
async def list_env_machines(
    namespace: str,
    device_type: Optional[str] = None,
    ip: Optional[str] = None,
    asset_number: Optional[str] = None,
    mark: Optional[str] = None,
    available: Optional[bool] = None,
    note: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db)
) -> PaginatedResponse[EnvMachineResponse]:
    """
    查询执行机列表

    支持 namespace 必填筛选，其他条件可选。
    """
    machines, total = await EnvMachineService.get_list_with_filters(
        db,
        namespace=namespace,
        device_type=device_type,
        ip=ip,
        asset_number=asset_number,
        mark=mark,
        available=available,
        note=note,
        page=page,
        page_size=page_size,
    )

    return PaginatedResponse(
        items=[EnvMachineResponse.model_validate(m) for m in machines],
        total=total,
    )


@router.post("", response_model=EnvMachineResponse, summary="新增执行机")
async def create_env_machine(
    data: EnvMachineCreateRequest,
    db: AsyncSession = Depends(get_db)
) -> EnvMachineResponse:
    """
    新增执行机（手工使用场景）

    根据设备类型自动处理：
    - Windows/Mac：填写 IP
    - iOS/Android：填写 device_sn
    """
    # 构建端口默认值
    port = data.ip.split(":")[1] if data.ip and ":" in data.ip else "8088"
    ip = data.ip.split(":")[0] if data.ip and ":" in data.ip else data.ip

    machine = EnvMachine(
        namespace=data.namespace,
        device_type=data.device_type,
        asset_number=data.asset_number,
        ip=ip or "",
        port=port,
        device_sn=data.device_sn,
        note=data.note,
        status="offline",
        available=False,
    )
    db.add(machine)
    await db.commit()
    await db.refresh(machine)

    return EnvMachineResponse.model_validate(machine)


@router.put("/{machine_id}", response_model=EnvMachineResponse, summary="更新执行机")
async def update_env_machine(
    machine_id: str,
    data: EnvMachineUpdateRequest,
    db: AsyncSession = Depends(get_db)
) -> EnvMachineResponse:
    """更新执行机信息"""
    machine = await EnvMachineService.get_by_id(db, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="执行机不存在")

    # 校验 mark 字段中的每个标签
    if data.mark:
        is_valid, error_msg = EnvPoolManager.validate_mark_field(data.mark)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(machine, key, value)

    await db.commit()
    await db.refresh(machine)

    # 同步更新 Redis 缓存
    await EnvPoolManager.sync_machine_to_cache(machine)

    return EnvMachineResponse.model_validate(machine)


@router.delete("/{machine_id}", summary="删除执行机")
async def delete_env_machine(
    machine_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除执行机（软删除）"""
    machine = await EnvMachineService.get_by_id(db, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="执行机不存在")

    # 记录 namespace 用于缓存清理
    namespace = machine.namespace

    await EnvMachineService.delete(db, machine_id)
    await db.commit()

    # 从 Redis 缓存中移除
    await EnvPoolManager.remove_machine_from_cache(machine_id, namespace)

    return {"status": "success", "message": "删除成功"}


@router.get("/dashboard/stats", summary="获取设备监控看板统计")
async def get_dashboard_stats(
    namespace: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    获取设备监控看板统计数据

    Args:
        namespace: 可选，筛选指定 namespace，默认查询全部

    Returns:
        DashboardStatsResponse: 看板统计数据
    """
    from core.env_machine.log_service import EnvMachineLogService
    from core.env_machine.log_schema import DashboardStatsResponse

    # 获取各项统计数据
    device_stats = await EnvMachineLogService.get_device_stats(db, namespace)
    apply_24h = await EnvMachineLogService.get_apply_24h_stats(db, namespace)
    top10_tags = await EnvMachineLogService.get_top10_tags(db, namespace)
    top20_duration = await EnvMachineLogService.get_top20_duration(db, namespace)
    top10_insufficient = await EnvMachineLogService.get_top10_insufficient(db, namespace)
    offline_machines = await EnvMachineLogService.get_offline_machines(db, namespace)

    return DashboardStatsResponse(
        device_stats=device_stats,
        apply_24h=apply_24h,
        top10_tags=top10_tags,
        top20_duration=top20_duration,
        top10_insufficient=top10_insufficient,
        offline_machines=offline_machines
    )