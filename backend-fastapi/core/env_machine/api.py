#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2025-03-25
@File: api.py
@Desc: 执行机管理 API - 注册、申请、保持使用、释放、CRUD 接口
"""
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_schema import PaginatedResponse
from app.config import get_settings
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
    EnvMachineBatchDeleteRequest,
    EnvMachineBatchImportResponse,
    EnvMachineBatchCommandRequest,
    CommandResultItem,
    EnvMachineBatchCommandResponse,
    BatchEnableRequest,
    BatchEnableResponse,
    BatchDisableRequest,
    BatchDisableResponse,
    SkippedItem,
    FailedItem,
)
from core.env_machine.service import (
    EnvMachineService,
    register_env_machine as register_env_machine_service,
)
from core.env_machine.pool_manager import EnvPoolManager
from core.env_machine.auth import verify_env_apply_auth
from core.env_machine.lock_manager import EnvLockManager
from core.env_machine.debug_service import DebugActionService
from core.env_machine.log_service import EnvMachineLogService
from core.env_machine.worker_client import execute_single_machine, fetch_worker_logs
from utils.client_info import get_client_ip
from utils.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/env", tags=["执行机管理"])

@router.post("/register", response_model=EnvSuccessResponse, summary="执行机注册")
async def register_env_machine(
    data: EnvRegisterRequest,
    db: AsyncSession = Depends(get_db)
) -> EnvSuccessResponse:
    """执行机注册（业务编排见 core.env_machine.service.register_env_machine）。"""
    return await register_env_machine_service(data, db)

@router.get("/namespaces", summary="获取所有机器分类")
async def get_namespaces(db: AsyncSession = Depends(get_db)) -> Dict[str, str]:
    """
    获取所有 namespace 配置（命名空间名称 -> 中文显示名称）

    用于前端筛选下拉框和表格显示的数据源。
    只返回配置中定义的命名空间，过滤掉未配置的（如 meeting_manual）。
    返回格式: {"meeting_gamma": "集成验证", "meeting_app": "APP", ...}
    """
    # 从配置获取命名空间映射（包含显示名称）
    settings = get_settings()
    return settings.namespace_map


@router.post(
    "/{namespace}/application",
    summary="申请执行机",
    dependencies=[Depends(verify_env_apply_auth)]  # 添加权限验证依赖
)
async def apply_env_machines(
    namespace: str,
    request: Request,
    data: Dict[str, str],
    db: AsyncSession = Depends(get_db),
    x_testcase_id: Optional[str] = Header(None, alias="X-Testcase-Id")
) -> Union[EnvSuccessResponse, EnvFailResponse]:
    """
    申请执行机接口

    Header:
        X-Testcase-Id: 用例编号（可选），用于合并连续失败记录
        X-Env-Auth: 申请权限key（必填），用于验证申请权限

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
    client_ip = get_client_ip(request)
    try:
        # 调用池管理器分配机器，传入 testcase_id
        success, result = await EnvPoolManager.allocate_machines(
            db, namespace, data, testcase_id=x_testcase_id
        )

        if success:
            logger.info(f"执行机申请成功 | namespace={namespace} | source_ip={client_ip} | allocations={list(result.keys())}")
            return EnvSuccessResponse(status="success", data=result)
        else:
            logger.warning(f"执行机申请失败 | namespace={namespace} | source_ip={client_ip} | reason={result}")
            return EnvFailResponse(status="fail", result=result)
    except Exception as e:
        await db.rollback()
        logger.error(f"执行机申请异常 | namespace={namespace} | source_ip={client_ip} | error={e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@router.post(
    "/keepusing",
    response_model=Union[EnvSuccessResponse, EnvFailResponse],
    summary="保持使用执行机",
)
async def keepusing_env_machines(
    request: Request,
    data: List[EnvMachineIdItem],
    db: AsyncSession = Depends(get_db)
) -> Union[EnvSuccessResponse, EnvFailResponse]:
    """
    保持使用执行机接口

    更新 last_keepusing_time，防止被周期任务超时释放。

    逻辑：
    1. 遍历请求中的机器 ID，忽略不存在或非 using 状态的机器
    2. 校验连续使用时长：从最近一次申请成功时间起算，超过
       ENV_MACHINE_KEEPUSING_MAX_HOURS（默认3小时）的机器拒绝保持，
       本次请求整体拒绝（不更新任何机器），需先释放设备后重新申请
    3. 更新通过校验机器的 last_keepusing_time
    """
    now = datetime.now()
    client_ip = get_client_ip(request)
    max_hours = get_settings().ENV_MACHINE_KEEPUSING_MAX_HOURS
    max_duration = timedelta(hours=max_hours)

    try:
        exceeded: List[str] = []
        machines_to_keep: List[EnvMachine] = []

        for item in data:
            machine = await EnvMachineService.get_by_id(db, item.id)

            if not machine:
                logger.debug(f"机器不存在，忽略: {item.id}")
                continue

            if machine.status != "using":
                logger.debug(f"机器状态非 using，忽略: {item.id}, status={machine.status}")
                continue

            # 连续使用时长从最近一次申请成功（未释放）的申请时间起算；
            # 找不到申请记录（如手工占用）时不在校验范围内
            apply_log = await EnvMachineLogService.get_latest_apply_log(db, item.id)
            if apply_log and apply_log.apply_time:
                held_duration = now - apply_log.apply_time
                if held_duration > max_duration:
                    exceeded.append(
                        f"{machine.ip or machine.device_sn or machine.id}"
                        f"(已使用{held_duration.total_seconds() / 3600:.1f}小时)"
                    )
                    continue

            machines_to_keep.append(machine)

        if exceeded:
            detail = ", ".join(exceeded)
            logger.warning(
                f"保持使用执行机被拒绝 | source_ip={client_ip} | "
                f"超过最长连续使用时长{max_hours}小时: {detail}"
            )
            await db.rollback()
            return EnvFailResponse(
                status="fail",
                result=(
                    f"设备已连续使用超过{max_hours}小时，拒绝保持使用，"
                    f"请先释放设备后重新申请: {detail}"
                ),
            )

        # 更新最后保持使用时间
        for machine in machines_to_keep:
            machine.last_keepusing_time = now

        # 提交数据库更改
        await db.commit()

        logger.info(f"保持使用执行机成功 | source_ip={client_ip} | count={len(data)}")

        return EnvSuccessResponse(status="success", data=None)
    except Exception as e:
        await db.rollback()
        logger.error(f"保持使用执行机失败 | source_ip={client_ip} | error={e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@router.post("/release", response_model=EnvSuccessResponse, summary="释放执行机")
async def release_env_machines(
    request: Request,
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
    client_ip = get_client_ip(request)
    try:
        for item in data:
            machine = await EnvMachineService.get_by_id(db, item.id)

            if not machine:
                logger.debug(f"机器不存在，忽略: {item.id}")
                continue

            # 调用 pool_manager.release_machine 释放机器（会更新日志的 duration_minutes）
            await EnvPoolManager.release_machine(db, item.id, machine.namespace)

        logger.info(f"释放执行机成功 | source_ip={client_ip} | count={len(data)}")

        return EnvSuccessResponse(status="success", data=None)
    except Exception as e:
        await db.rollback()
        logger.error(f"释放执行机失败 | source_ip={client_ip} | error={e}")
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

    # 标记宿主机（同 IP 的 windows/mac）升级中的设备：升级窗口内其执行通道
    # 经宿主 Worker 转发不可用，前端据此显示“宿主升级中”
    page_host_ips = {m.ip for m in machines if m.device_type in ("windows", "mac")}
    upgrading_host_ips: set[str] = set()
    if page_host_ips:
        result = await db.execute(
            select(EnvMachine).where(
                EnvMachine.ip.in_(page_host_ips),
                EnvMachine.device_type.in_(("windows", "mac")),
                EnvMachine.status == "upgrading",
                EnvMachine.is_deleted == False,  # noqa: E712
                EnvMachine.is_virtual == False,  # noqa: E712
            )
        )
        upgrading_host_ips = {m.ip for m in result.scalars().all()}

    items = []
    for machine in machines:
        item = EnvMachineResponse.model_validate(machine)
        if (
            machine.device_type not in ("windows", "mac")
            and machine.ip in upgrading_host_ips
        ):
            item.host_upgrading = True
        items.append(item)

    return PaginatedResponse(
        items=items,
        total=total,
    )


@router.post("", response_model=EnvMachineResponse, summary="新增执行机")
async def create_env_machine(
    data: EnvMachineCreateRequest,
    db: AsyncSession = Depends(get_db)
) -> EnvMachineResponse:
    """
    新增执行机（手工使用场景或虚拟设备）

    根据设备类型自动处理：
    - Windows/Mac：填写 IP
    - iOS/Android：填写 device_sn
    - 虚拟设备：is_virtual=True，无需真实 worker
    """
    # 构建端口默认值
    # 虚拟设备无端口，非虚拟设备默认8088
    if data.ip and ":" in data.ip:
        port = data.ip.split(":")[1]
        ip = data.ip.split(":")[0]
    else:
        ip = data.ip or ""
        port = None if data.is_virtual else "8088"

    # 虚拟设备默认 online（无需心跳），非虚拟设备默认 offline（等待心跳）
    machine = EnvMachine(
        namespace=data.namespace,
        device_type=data.device_type,
        asset_number=data.asset_number,
        ip=ip or "",
        port=port,
        device_sn=data.device_sn,
        note=data.note,
        status="online" if data.is_virtual else "offline",
        available=False,
        is_virtual=data.is_virtual,
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
    if "device_sn" in update_data and not update_data["device_sn"]:
        update_data["device_sn"] = None
    for key, value in update_data.items():
        setattr(machine, key, value)

    await db.commit()
    await db.refresh(machine)

    # 同步更新 Redis 缓存
    await EnvPoolManager.sync_machine_to_cache(machine)

    return EnvMachineResponse.model_validate(machine)


@router.get("/import-template", summary="下载虚拟设备导入模板")
async def download_import_template():
    """
    下载虚拟设备导入 Excel 模板

    模板包含表头和示例数据
    """
    buffer = await EnvMachineService.generate_virtual_import_template()

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=virtual_device_import_template.xlsx"
        }
    )


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
    """删除执行机（物理删除）"""
    machine = await EnvMachineService.get_by_id(db, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="执行机不存在")

    # 记录 namespace 用于缓存清理
    namespace = machine.namespace

    await EnvMachineService.delete(db, machine_id, hard=True)
    await db.commit()

    # 从 Redis 缓存中移除
    await EnvPoolManager.remove_machine_from_cache(machine_id, namespace)

    return {"status": "success", "message": "删除成功"}


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

    # Worker 通信收口在 worker_client（构建 URL、查询参数与错误映射）
    return await fetch_worker_logs(
        machine,
        lines=lines if has_lines else None,
        request_id=request_id if has_request_id else None,
        start_time=start_time if has_time_range else None,
        end_time=end_time if has_time_range else None,
    )


@router.post("/{machine_id}/debug-action", response_model=DebugActionResponse, summary="设备调试操作")
async def debug_device_action(
    machine_id: str,
    data: DebugActionRequest,
    db: AsyncSession = Depends(get_db)
) -> DebugActionResponse:
    """设备调试操作（编排见 core.env_machine.debug_service.DebugActionService）。"""
    return await DebugActionService.execute(db, machine_id, data)


@router.post("/batch-execute-command", response_model=EnvMachineBatchCommandResponse, summary="批量执行命令")
async def batch_execute_command(
    data: EnvMachineBatchCommandRequest,
    db: AsyncSession = Depends(get_db)
) -> EnvMachineBatchCommandResponse:
    """
    批量执行命令接口

    在多台设备上并行执行命令，支持 Windows（cmd）和 Mac（shell）设备。

    流程：
    1. 查询所有设备信息
    2. 过滤不支持命令执行的设备（iOS/Android、虚拟设备）
    3. 使用 asyncio.gather 并行执行
    4. 返回执行结果汇总

    Args:
        data: 批量执行命令请求
        db: 数据库会话

    Returns:
        EnvMachineBatchCommandResponse: 执行结果汇总
    """
    # 查询所有设备
    machines = []
    for machine_id in data.ids:
        machine = await EnvMachineService.get_by_id(db, machine_id)
        if machine:
            machines.append(machine)

    if not machines:
        return EnvMachineBatchCommandResponse(
            results=[],
            total=0,
            success_count=0,
            failed_count=0,
        )

    # 并行执行命令
    tasks = [execute_single_machine(machine, data.command) for machine in machines]
    results = await asyncio.gather(*tasks)

    # 统计结果
    success_count = sum(1 for r in results if r.success)
    failed_count = len(results) - success_count

    logger.info(
        f"批量执行命令完成: total={len(results)}, success={success_count}, failed={failed_count}"
    )

    return EnvMachineBatchCommandResponse(
        results=results,
        total=len(results),
        success_count=success_count,
        failed_count=failed_count,
    )


@router.post("/batch-delete", summary="批量删除设备")
async def batch_delete_env_machines(
    data: EnvMachineBatchDeleteRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    批量删除设备（支持虚拟和真实设备）

    - 物理删除：直接从数据库删除记录
    - 从 Redis 缓存中移除
    """
    success_count = 0
    failed_ids = []

    for machine_id in data.ids:
        machine = await EnvMachineService.get_by_id(db, machine_id)
        if not machine:
            failed_ids.append(machine_id)
            continue

        namespace = machine.namespace
        await EnvMachineService.delete(db, machine_id, hard=True)
        await EnvPoolManager.remove_machine_from_cache(machine_id, namespace)
        success_count += 1

    await db.commit()

    return {
        "success_count": success_count,
        "failed_ids": failed_ids
    }


@router.post("/batch-import-virtual", response_model=EnvMachineBatchImportResponse, summary="批量导入虚拟设备")
async def batch_import_virtual_devices(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
) -> EnvMachineBatchImportResponse:
    """
    批量导入虚拟设备

    - Excel 文件上传
    - 返回导入结果
    """
    # 验证文件类型
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="只支持 Excel 文件 (.xlsx, .xls)")

    content = await file.read()
    success_count, failed_items = await EnvMachineService.import_virtual_from_excel(db, content)

    return EnvMachineBatchImportResponse(
        success_count=success_count,
        failed_items=failed_items
    )


@router.post("/batch-enable", response_model=BatchEnableResponse, summary="批量启用设备")
async def batch_enable_env_machines(
    data: BatchEnableRequest,
    db: AsyncSession = Depends(get_db)
) -> BatchEnableResponse:
    """
    批量启用设备（带校验）

    校验规则：
    - 标签字段必须存在
    - 扩展信息字段必须存在且为有效 dict
    - 每个标签在扩展信息中必须有对应配置
    - Linux 设备不支持启用（自动跳过）

    不满足条件的设备会被跳过，返回跳过原因。
    """
    # 查询所有设备，过滤 Linux 设备
    machines = await EnvMachineService.get_by_ids(db, data.ids)

    # 过滤 Linux 设备
    linux_ids = [str(m.id) for m in machines if m.device_type == 'linux']
    other_ids = [str(m.id) for m in machines if m.device_type != 'linux']

    # Linux 设备跳过
    linux_skipped = [{"id": id, "ip": "", "reason": "Linux 设备不支持启用"} for id in linux_ids]

    # 其他设备执行启用校验
    success_count, skipped_items = await EnvMachineService.batch_enable_with_validation(
        db, other_ids
    )

    # 合并跳过列表
    all_skipped = linux_skipped + skipped_items

    # 同步 Redis 缓存（将启用的设备加入申请池）
    enabled_machines = await EnvMachineService.get_by_ids(db, other_ids)
    for machine in enabled_machines:
        if machine.available:
            await EnvPoolManager.sync_machine_to_cache(machine)

    return BatchEnableResponse(
        success_count=success_count,
        skipped_count=len(all_skipped),
        skipped_items=[SkippedItem(**item) for item in all_skipped]
    )


@router.post("/batch-disable", response_model=BatchDisableResponse, summary="批量停用设备")
async def batch_disable_env_machines(
    data: BatchDisableRequest,
    db: AsyncSession = Depends(get_db)
) -> BatchDisableResponse:
    """
    批量停用设备

    直接停用所有选中的设备，无需校验。
    """
    # 使用现有方法批量更新
    success_count, failed_ids = await EnvMachineService.batch_update_available(
        db, data.ids, available=False
    )

    # 同步 Redis 缓存
    machines = await EnvMachineService.get_by_ids(db, data.ids)
    for machine in machines:
        await EnvPoolManager.sync_machine_to_cache(machine)

    # 构建失败项详情
    failed_items = []
    if failed_ids:
        for fid in failed_ids:
            failed_items.append(FailedItem(id=fid, ip=""))

    return BatchDisableResponse(
        success_count=success_count,
        failed_count=len(failed_ids),
        failed_items=failed_items
    )
