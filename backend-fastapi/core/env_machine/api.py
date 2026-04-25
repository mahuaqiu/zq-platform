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

import httpx
from fastapi import APIRouter, Depends, HTTPException, Header, Query
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
    DebugActionRequest,
    DebugActionResponse,
)
from core.env_machine.service import EnvMachineService
from core.env_machine.pool_manager import EnvPoolManager
from core.env_machine.scheduler import modify_release_job, remove_release_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/env", tags=["执行机管理"])


@router.get("/namespaces", summary="获取所有机器分类")
async def get_namespaces(db: AsyncSession = Depends(get_db)) -> List[str]:
    """
    获取所有 namespace 列表（去重、已排序）

    用于前端筛选下拉框的数据源。
    """
    return await EnvMachineService.get_namespaces(db)


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
    7. 如果从 upgrading 状态变为 online，触发队列中的升级任务
    """
    now = datetime.now()
    has_upgrading_machine = False  # 标记是否有从 upgrading 变为 online 的机器

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
                    # 存在则更新 sync_time
                    old_status = existing_machine.status
                    existing_machine.sync_time = now
                    existing_machine.port = data.port
                    if data.version:
                        existing_machine.version = data.version
                    if data.config_version:
                        existing_machine.config_version = data.config_version

                    # 状态更新规则：
                    # - using: 保持不变，只更新心跳时间（机器正在被使用）
                    # - upgrading: 变为 online（升级完成）
                    # - offline/online: 变为 online（正常心跳）
                    if existing_machine.status != "using":
                        existing_machine.status = "online"
                        # 标记是否有从 upgrading 变为 online 的机器
                        if old_status == "upgrading":
                            has_upgrading_machine = True
                    else:
                        # using 状态保持不变，记录日志
                        logger.info(f"机器正在使用中，保持状态: id={existing_machine.id}, ip={data.ip}, device_type={device_type}")
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
                        config_version=data.config_version,
                    )
                    db.add(new_machine)

            elif device_type in ("android", "ios"):
                # Android/iOS：根据 device_sn 列表，每个 sn 插入一条记录
                # 支持两种格式：字符串列表 ["udid1"] 或对象列表 [{"udid": "udid1"}]
                for device_item in device_sns:
                    if not device_item:
                        continue

                    # 提取 device_sn
                    if isinstance(device_item, dict):
                        device_sn = device_item.get("udid")
                    elif isinstance(device_item, str):
                        device_sn = device_item
                    else:
                        continue

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
                        # 存在则更新 sync_time
                        old_status = existing_machine.status
                        existing_machine.sync_time = now
                        existing_machine.port = data.port
                        if data.version:
                            existing_machine.version = data.version
                        if data.config_version:
                            existing_machine.config_version = data.config_version

                        # 状态更新规则：
                        # - using: 保持不变，只更新心跳时间（机器正在被使用）
                        # - upgrading: 变为 online（升级完成）
                        # - offline/online: 变为 online（正常心跳）
                        if existing_machine.status != "using":
                            existing_machine.status = "online"
                            # 标记是否有从 upgrading 变为 online 的机器
                            if old_status == "upgrading":
                                has_upgrading_machine = True
                        else:
                            # using 状态保持不变，记录日志
                            logger.info(f"机器正在使用中，保持状态: id={existing_machine.id}, ip={data.ip}, device_type={device_type}, device_sn={device_sn}")
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
                            config_version=data.config_version,
                        )
                        db.add(new_machine)

        # 提交数据库更改
        await db.commit()

        # 如果有从 upgrading 变为 online 的机器，触发队列处理
        if has_upgrading_machine:
            from core.env_machine.upgrade_service import UpgradeConcurrencyService
            processed_count = await UpgradeConcurrencyService.process_queue_batch(db)
            if processed_count > 0:
                logger.info(f"注册后触发队列升级: count={processed_count}")

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
    db: AsyncSession = Depends(get_db),
    x_testcase_id: Optional[str] = Header(None, alias="X-Testcase-Id")
) -> Union[EnvSuccessResponse, EnvFailResponse]:
    """
    申请执行机接口

    Header:
        X-Testcase-Id: 用例编号（可选），用于合并连续失败记录

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
        # 调用池管理器分配机器，传入 testcase_id
        success, result = await EnvPoolManager.allocate_machines(
            db, namespace, data, testcase_id=x_testcase_id
        )

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
    2. 对于每台机器：调用 pool_manager.release_machine 更新状态和日志
    3. 忽略不存在的机器
    """
    try:
        for item in data:
            machine = await EnvMachineService.get_by_id(db, item.id)

            if not machine:
                logger.debug(f"机器不存在，忽略: {item.id}")
                continue

            # 调用 pool_manager.release_machine 释放机器（会更新日志的 duration_minutes）
            await EnvPoolManager.release_machine(db, item.id, machine.namespace)

        logger.info(f"释放执行机成功: count={len(data)}")

        return EnvSuccessResponse(status="success", data=None)
    except Exception as e:
        await db.rollback()
        logger.error(f"释放执行机失败: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@router.get("", response_model=PaginatedResponse[EnvMachineResponse], summary="查询执行机列表")
async def list_env_machines(
    namespace: Optional[str] = None,  # 改为 Optional
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

    支持 namespace 可选筛选，其他条件可选。
    - namespace 为 None 时查询所有4个分类设备
    - namespace 有值时按指定分类筛选
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


@router.get("/{machine_id}", response_model=EnvMachineResponse, summary="获取单个设备详情")
async def get_env_machine_detail(
    machine_id: str,
    db: AsyncSession = Depends(get_db)
) -> EnvMachineResponse:
    """获取单个设备详情"""
    machine = await EnvMachineService.get_by_id(db, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="执行机不存在")
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
        namespace: 可选，筛选指定 namespace。
                   支持单个 namespace 或逗号分隔的多个 namespace。
                   例如: "meeting_gamma" 或 "meeting_gamma,meeting_app"
                   如果为空字符串，返回空数据。

    Returns:
        DashboardStatsResponse: 看板统计数据
    """
    from core.env_machine.log_service import EnvMachineLogService
    from core.env_machine.log_schema import DashboardStatsResponse, DeviceStats, Apply24hStats

    # 解析 namespace 参数：支持逗号分隔的多个值
    namespaces = None
    if namespace:
        namespaces = [ns.strip() for ns in namespace.split(',') if ns.strip()]

    # 如果 namespace 参数存在但解析后为空列表，返回空数据
    if namespace and not namespaces:
        return DashboardStatsResponse(
            device_stats=DeviceStats(total=0, online=0, offline=0, by_type=[]),
            apply_24h=Apply24hStats(total=0, success=0, failed=0),
            top10_tags=[],
            top20_duration=[],
            top10_insufficient=[],
            offline_machines=[]
        )

    # 获取各项统计数据
    device_stats = await EnvMachineLogService.get_device_stats(db, namespaces)
    apply_24h = await EnvMachineLogService.get_apply_24h_stats(db, namespaces)
    top10_tags = await EnvMachineLogService.get_top10_tags(db, namespaces)
    top20_duration = await EnvMachineLogService.get_top20_duration(db, namespaces)
    top10_insufficient = await EnvMachineLogService.get_top10_insufficient(db, namespaces)
    offline_machines = await EnvMachineLogService.get_offline_machines(db, namespaces)

    return DashboardStatsResponse(
        device_stats=device_stats,
        apply_24h=apply_24h,
        top10_tags=top10_tags,
        top20_duration=top20_duration,
        top10_insufficient=top10_insufficient,
        offline_machines=offline_machines
    )


# 注册升级管理路由
from core.env_machine.upgrade_api import router as upgrade_router
router.include_router(upgrade_router)


@router.get("/machine/{machine_id}/logs", summary="获取设备日志")
async def get_machine_logs(
    machine_id: str,
    lines: Optional[int] = Query(default=None, ge=1, le=2000),
    request_id: Optional[str] = Query(default=None),
    start_time: Optional[str] = Query(default=None),
    end_time: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db)
):
    """
    从指定 Worker 设备拉取日志

    支持三种查询模式（互斥）：
    - lines 模式: 返回最后 N 行（默认 400，范围 1-2000）
    - request_id 模式: grep 搜索指定 request_id 的日志
    - time_range 模式: 按时间区间过滤（需同时提供 start_time 和 end_time，最多 5 分钟）

    流程：
    1. 根据 machine_id 查询数据库获取 IP 和端口
    2. HTTP GET http://{ip}:{port}/worker/logs?参数
    3. 返回 Worker 的日志文本
    """
    # 参数验证：三选一，互斥
    has_lines = lines is not None
    has_request_id = request_id is not None
    has_time_range = start_time is not None or end_time is not None

    # 计算模式数量
    mode_count = sum([has_lines, has_request_id, has_time_range])

    # 默认使用 lines=400
    if mode_count == 0:
        lines = 400
        has_lines = True
        mode_count = 1

    # 验证互斥
    if mode_count > 1:
        raise HTTPException(
            status_code=400,
            detail="参数冲突：lines/request_id/start_time+end_time 三选一"
        )

    # 验证 time_range 模式参数完整性
    if has_time_range:
        if not start_time or not end_time:
            raise HTTPException(
                status_code=400,
                detail="时间区间模式需同时提供 start_time 和 end_time"
            )
        # 验证时间格式和区间
        try:
            from datetime import datetime
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            diff_minutes = (end_dt - start_dt).total_seconds() / 60
            if diff_minutes > 5:
                raise HTTPException(
                    status_code=400,
                    detail="时间区间不能超过 5 分钟"
                )
            if diff_minutes <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="end_time 必须大于 start_time"
                )
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"时间格式无效：{str(e)}"
            )

    machine = await EnvMachineService.get_by_id(db, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="设备不存在")

    if not machine.ip or not machine.port:
        raise HTTPException(status_code=400, detail="设备未配置 IP 或端口")

    url = f"http://{machine.ip}:{machine.port}/worker/logs"

    # 构建查询参数
    params = {}
    if has_lines:
        params["lines"] = lines
    elif has_request_id:
        params["request_id"] = request_id
    elif has_time_range:
        params["start_time"] = start_time
        params["end_time"] = end_time

    try:
        async with httpx.AsyncClient(timeout=30.0, trust_env=True, verify=False) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                # 从响应头获取统计信息
                log_count = int(resp.headers.get("X-Log-Count", 0))
                files_scanned = int(resp.headers.get("X-Files-Scanned", 1))

                return {
                    "content": resp.text,
                    "log_count": log_count,
                    "files_scanned": files_scanned,
                }
            elif resp.status_code == 400:
                raise HTTPException(status_code=400, detail=resp.text)
            elif resp.status_code == 404:
                raise HTTPException(status_code=404, detail="日志文件不存在")
            elif resp.status_code == 503:
                raise HTTPException(status_code=503, detail="Worker 未初始化")
            elif resp.status_code == 502:
                raise HTTPException(status_code=502, detail="无法连接到设备")
            else:
                raise HTTPException(status_code=502, detail=f"设备返回异常: {resp.status_code}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="获取日志超时")
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="无法连接到设备")


@router.post("/{machine_id}/debug-action", response_model=DebugActionResponse, summary="设备调试操作")
async def debug_device_action(
    machine_id: str,
    data: DebugActionRequest,
    db: AsyncSession = Depends(get_db)
) -> DebugActionResponse:
    """
    设备调试操作接口

    代理转发调试操作到 Worker，支持以下操作：
    - screenshot: 获取截图
    - click: 点击坐标
    - swipe: 滑动操作
    - input: 文本输入
    - press: 按键操作

    流程：
    1. 根据 machine_id 查询设备信息
    2. 校验设备类型（必须是 ios/android）
    3. 校验设备状态（必须是 online）
    4. 构造 Worker API 请求体
    5. POST http://{ip}:{port}/task/execute
    6. 返回结果
    """
    # 查询设备信息
    machine = await EnvMachineService.get_by_id(db, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="设备不存在")

    # 校验设备类型（支持所有设备类型）
    if machine.device_type not in ("ios", "android", "windows", "mac"):
        raise HTTPException(status_code=400, detail="仅支持 iOS/Android/Windows/Mac 设备调试")

    # 校验设备状态
    if machine.status != "online":
        raise HTTPException(status_code=400, detail=f"设备状态为 {machine.status}，无法调试")

    # 构造 Worker API 请求体
    action_type = data.action_type
    params = data.params

    # 构建 actions 列表
    actions = []

    if action_type == "screenshot":
        actions.append({"action_type": "screenshot", "value": "debug"})
    elif action_type == "click":
        actions.append({"action_type": "click", "x": params.get("x"), "y": params.get("y")})
    elif action_type == "swipe":
        actions.append({
            "action_type": "swipe",
            "from": {"x": params.get("from_x"), "y": params.get("from_y")},
            "to": {"x": params.get("to_x"), "y": params.get("to_y")},
            "duration": params.get("duration", 500)
        })
    elif action_type == "input":
        actions.append({
            "action_type": "input",
            "x": params.get("x"),
            "y": params.get("y"),
            "text": params.get("text")
        })
    elif action_type == "press":
        actions.append({"action_type": "press", "key": params.get("key")})
    elif action_type == "unlock_screen":
        actions.append({"action_type": "unlock_screen", "value": params.get("value")})
    else:
        raise HTTPException(status_code=400, detail=f"不支持的操作类型: {action_type}")

    # 发送请求到 Worker
    worker_url = f"http://{machine.ip}:{machine.port}/task/execute"
    worker_request = {
        "platform": machine.device_type,
        "device_id": machine.device_sn or machine_id,
        "actions": actions
    }

    # 根据操作类型设置超时时间（解锁操作需要更长时间）
    request_timeout = 35.0 if action_type == "unlock_screen" else 20.0

    try:
        async with httpx.AsyncClient(timeout=request_timeout, trust_env=True, verify=False) as client:
            resp = await client.post(worker_url, json=worker_request)
            if resp.status_code == 200:
                worker_result = resp.json()

                # 检查 action 执行状态
                actions_result = worker_result.get("actions", [])
                if actions_result:
                    first_action = actions_result[0]
                    action_status = first_action.get("status", "")
                    action_error = first_action.get("error", "")

                    # action 执行失败
                    if action_status == "failed":
                        return DebugActionResponse(
                            success=False,
                            result={"error": action_error or "操作执行失败"}
                        )

                # 提取截图结果
                result = {}
                if action_type == "screenshot":
                    for action in actions_result:
                        if action.get("action_type") == "screenshot" and action.get("screenshot"):
                            result["screenshot_base64"] = action["screenshot"]
                            break

                return DebugActionResponse(success=True, result=result)
            elif resp.status_code == 502:
                return DebugActionResponse(success=False, result={"error": "无法连接到设备"})
            else:
                return DebugActionResponse(success=False, result={"error": f"设备返回异常: {resp.status_code}"})
    except httpx.TimeoutException:
        return DebugActionResponse(success=False, result={"error": "操作超时"})
    except httpx.ConnectError:
        return DebugActionResponse(success=False, result={"error": "无法连接到设备"})
    except Exception as e:
        logger.error(f"调试操作失败: {e}")
        return DebugActionResponse(success=False, result={"error": str(e)})