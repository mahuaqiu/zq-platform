#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2026-04-15
@File: api.py
@Desc: ConfigTemplate API - 配置模板管理接口
"""
import asyncio
import hashlib
import logging
import time
from itertools import islice
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_schema import PaginatedResponse
from app.database import get_db
from utils.background_tasks import spawn_background_task
from core.config_template.schema import (
    ConfigTemplateCreate,
    ConfigTemplateUpdate,
    ConfigTemplateResponse,
    DeployRequest,
    DeployResponse,
    ConfigPreviewResponse,
    MachineSelectionTemplateCreate,
    MachineSelectionTemplateUpdate,
    MachineSelectionTemplateResponse,
    MachineSelectionTemplateDetailResponse,
    CommandTaskResponse,
    CommandTaskDetailResponse,
)
from core.config_template.service import ConfigTemplateService, SUPPORTED_CONFIG_DEVICE_TYPES
from core.config_template.model import ConfigTemplate
from core.config_template.machine_selection_template_service import MachineSelectionTemplateService
from core.config_template.command_task_service import CommandTaskService
from core.env_machine.model import EnvMachine

logger = logging.getLogger(__name__)

def _worker_http_error_message(response: httpx.Response, fallback: str) -> str:
    """提取 Worker HTTP 错误，兼容结构化 detail 和旧文本响应。"""
    try:
        payload = response.json()
    except ValueError:
        return fallback
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("code") or fallback)
    return str(detail or payload.get("message") or fallback) if isinstance(payload, dict) else fallback


router = APIRouter(prefix="/config-template", tags=["设备配置管理"])

# ==================== 静态路由（必须在动态路由之前）====================


@router.get("", response_model=PaginatedResponse[ConfigTemplateResponse], summary="获取模板列表")
async def list_config_templates(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    template_type: Optional[str] = Query(None, description="模板类型筛选: config/script/command"),
    keyword: Optional[str] = Query(None, max_length=100, description="名称、脚本名、命令或备注搜索"),
    db: AsyncSession = Depends(get_db)
) -> PaginatedResponse[ConfigTemplateResponse]:
    """获取配置模板列表（分页）"""
    filters = []
    if template_type:
        filters.append(ConfigTemplate.type == template_type)
    if keyword and keyword.strip():
        escaped = keyword.strip().replace("%", r"\%").replace("_", r"\_")
        pattern = f"%{escaped}%"
        filters.append(or_(
            ConfigTemplate.name.ilike(pattern),
            ConfigTemplate.script_name.ilike(pattern),
            ConfigTemplate.command.ilike(pattern),
            ConfigTemplate.note.ilike(pattern),
        ))

    templates, total = await ConfigTemplateService.get_list(
        db,
        page=page,
        page_size=page_size,
        filters=filters,
    )

    return PaginatedResponse(
        items=[ConfigTemplateResponse.model_validate(t) for t in templates],
        total=total,
    )


@router.get("/preview", response_model=ConfigPreviewResponse, summary="配置下发预览")
async def preview_config_deploy(
    template_id: str = Query(..., description="模板ID"),
    namespace: Optional[str] = Query(None, description="命名空间筛选"),
    device_type: Optional[str] = Query(None, description="设备类型筛选"),
    ip: Optional[str] = Query(None, description="IP地址筛选"),
    machine_ids: Optional[str] = Query(None, description="机器ID列表，逗号分隔"),
    db: AsyncSession = Depends(get_db)
) -> ConfigPreviewResponse:
    """配置下发预览"""
    # 解析 machine_ids
    parsed_machine_ids = None
    if machine_ids:
        parsed_machine_ids = [mid.strip() for mid in machine_ids.split(",") if mid.strip()]

    try:
        preview = await ConfigTemplateService.get_preview(
            db,
            template_id=template_id,
            namespace=namespace,
            device_type=device_type,
            machine_ids=parsed_machine_ids,
        )
        # 如果有 IP 筛选，进一步过滤
        if ip:
            preview.machines = [m for m in preview.machines if ip.lower() in m.ip.lower()]
            preview.deployable_count = sum(1 for m in preview.machines if m.config_status in ("synced", "pending"))
            preview.offline_count = sum(1 for m in preview.machines if m.config_status == "offline")
            preview.updating_count = sum(1 for m in preview.machines if m.config_status == "updating")
        return preview
    except ValueError as e:
        logger.warning(f"配置预览失败: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"配置预览异常: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@router.post("", response_model=ConfigTemplateResponse, summary="新建配置模板")
async def create_config_template(
    data: ConfigTemplateCreate,
    db: AsyncSession = Depends(get_db)
) -> ConfigTemplateResponse:
    """新建配置模板"""
    is_unique = await ConfigTemplateService.check_name_unique(db, data.name)
    if not is_unique:
        raise HTTPException(status_code=400, detail="模板名称已存在")

    try:
        template = await ConfigTemplateService.create_with_version(db, data)
        logger.info(f"创建配置模��成功: id={template.id}, name={template.name}, type={template.type}")
        return ConfigTemplateResponse.model_validate(template)
    except Exception as e:
        await db.rollback()
        logger.error(f"创建配置模板失败: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@router.post("/deploy", response_model=DeployResponse, summary="执行配置/脚本/命令下发")
async def deploy_config(
    data: DeployRequest,
    db: AsyncSession = Depends(get_db)
) -> DeployResponse:
    """执行配置下发"""
    try:
        # 获取模板
        template = await ConfigTemplateService.get_by_id(db, data.template_id)
        if not template:
            raise HTTPException(status_code=404, detail="模板不存在")

        # 如果是 command 类型，使用异步执行
        if template.type == "command":
            return await _execute_command_deploy(db, template, data.machine_ids, data.command)

        # config/script 类型使用原有逻��
        response = await ConfigTemplateService.deploy_config(
            db,
            template_id=data.template_id,
            machine_ids=data.machine_ids,
        )
        logger.info(
            f"��置下发完成: template_id={data.template_id}, "
            f"success={response.success_count}, failed={response.failed_count}"
        )
        return response
    except ValueError as e:
        logger.warning(f"配置下发失败: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"配置下发异常: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


async def _execute_command_deploy(
    db: AsyncSession,
    template,
    machine_ids: List[str],
    command_override: Optional[str] = None
) -> DeployResponse:
    """执行运行命令下发（异步方式）"""
    # 获取实际命令内容
    command = command_override or template.command
    if not command:
        raise HTTPException(status_code=400, detail="命令内容不能为空")

    # 查询机器
    # 命令执行独立于配置/脚本下发，不依赖版本状态；
    # 使用中（using）的机器 Worker 仍可达，允许下发；仅排除离线机器
    result = await db.execute(
        select(EnvMachine).where(
            and_(
                EnvMachine.id.in_(machine_ids),
                EnvMachine.is_deleted == False,
                EnvMachine.is_virtual == False,
                EnvMachine.status.in_(["online", "using"]),
            )
        )
    )
    machines = result.scalars().all()

    unsupported = [
        machine.device_type
        for machine in machines
        if machine.device_type not in SUPPORTED_CONFIG_DEVICE_TYPES
    ]
    if unsupported:
        raise HTTPException(status_code=400, detail="鸿蒙、Android、iOS 设备不支持宿主机命令下发")

    if not machines:
        raise HTTPException(status_code=400, detail="没有可执行的机器")

    # 创建任务记录
    task = await CommandTaskService.create_task(
        db,
        template_id=str(template.id),
        template_type="command",
        template_name=template.name,
        command=command,
        machine_count=len(machines),
    )

    # 拷贝机器快照（避免 session 关闭后对象变成 detached 状态）
    machine_snapshot = [
        {
            "id": str(m.id),
            "ip": m.ip,
            "port": m.port,
            "device_type": m.device_type,
            "device_sn": m.device_sn,
        }
        for m in machines
    ]
    task_id = str(task.id)

    # 异步执行命令（使用独立的 session，不依赖请求级 db）
    # 通过 spawn_background_task 持有强引用并记录异常，避免任务被 GC 中途取消
    spawn_background_task(
        _execute_commands_async(task_id, machine_snapshot, command),
        name=f"command-deploy-{task_id}",
    )

    return DeployResponse(
        task_id=task_id,
        success_count=0,
        failed_count=0,
        skipped_count=0,
        details=[],
    )


# 单批并发机器数上限：与前端列表分页对齐，避免一次性打爆 worker 网络层
COMMAND_BATCH_SIZE = 20


async def _execute_commands_async(task_id: str, machines: List[dict], command: str):
    """异步执行命令（后台任务，使用独立 session）。

    机器数超过 COMMAND_BATCH_SIZE 时分批并发：批内 asyncio.gather 并发执行，
    批与批之间串行。每台机器各自有独立的 worker task_id 与轮询，互不阻塞。
    """
    from app.database import AsyncSessionLocal

    results = []
    success_count = 0
    failed_count = 0

    it = iter(machines)
    while batch := list(islice(it, COMMAND_BATCH_SIZE)):
        batch_results = await asyncio.gather(
            *(_execute_single_command(m, command, task_id) for m in batch)
        )
        for result in batch_results:
            results.append(result)
            if result["success"]:
                success_count += 1
            else:
                failed_count += 1

    # 更新任务结果（使用独立 session）
    status = "success" if failed_count == 0 else ("partial" if success_count > 0 else "failed")
    async with AsyncSessionLocal() as db:
        await CommandTaskService.update_task_result(
            db,
            task_id,
            status=status,
            success_count=success_count,
            failed_count=failed_count,
            result_detail=results,
        )


async def _execute_single_command(machine: dict, command: str, parent_task_id: str) -> dict:
    """执行单台机器的命令（machine 为机器快照 dict: id/ip/port/device_type）"""
    start_time = time.time()
    machine_id = machine["id"]
    ip = machine["ip"]
    port = machine["port"]
    device_type = machine["device_type"]
    device_sn = machine.get("device_sn")

    # 调用 worker 异步接口
    worker_url = f"http://{ip}:{port}/task/execute_async"
    worker_request = {
        "platform": device_type,
        "device_id": device_sn or machine_id,
        "actions": [{"action_type": "cmd_exec", "value": command}],
    }
    idempotency_key = hashlib.sha256(
        f"{parent_task_id}:{machine_id}:{command}".encode("utf-8")
    ).hexdigest()

    try:
        async with httpx.AsyncClient(timeout=60.0, trust_env=False, verify=False) as client:
            resp = await client.post(
                worker_url,
                json=worker_request,
                headers={"Idempotency-Key": idempotency_key},
            )
            duration = time.time() - start_time

            if resp.status_code == 200:
                data = resp.json()
                task_id = data.get("task_id")

                # 等待任务完成（轮询）—— 用默认总超时，不能用 POST 阶段的 duration
                # （duration 只是发起请求的耗时，约 0.x 秒，当 timeout 会导致一次都不查就超时）
                result = await _wait_task_result(ip, port, task_id)
                return {
                    "machine_id": machine_id,
                    "ip": ip,
                    "device_type": device_type,
                    "success": result["success"],
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "duration_seconds": result.get("duration", duration),
                }
            else:
                return {
                    "machine_id": machine_id,
                    "ip": ip,
                    "device_type": device_type,
                    "success": False,
                    "stdout": "",
                    "stderr": _worker_http_error_message(resp, f"Worker 返回错误: {resp.status_code}"),
                    "duration_seconds": duration,
                }
    except httpx.TimeoutException:
        duration = time.time() - start_time
        return {
            "machine_id": machine_id,
            "ip": ip,
            "device_type": device_type,
            "success": False,
            "stdout": "",
            "stderr": "命令执行超时",
            "duration_seconds": duration,
        }
    except Exception as e:
        duration = time.time() - start_time
        return {
            "machine_id": machine_id,
            "ip": ip,
            "device_type": device_type,
            "success": False,
            "stdout": "",
            "stderr": f"执行异常: {str(e)}",
            "duration_seconds": duration,
        }


def _interpret_task_poll(
    status_code: int,
    payload: Optional[dict],
) -> tuple[str, Optional[dict]]:
    """解释一次任务结果查询响应（纯函数，便于回归测试）。

    Returns:
        tuple: (action, result)
        - ("running", None): 任务未结束，继续轮询
        - ("retry", None):   暂时性失败（5xx 等），可有限次重试
        - ("retry", None) 后由调用方计数，连续失败达到上限即终止
        - ("done", dict):    得到终态结果，结束轮询
        - ("gone", dict):    任务确定不存在（404），立即失败
    """
    if status_code == 200 and isinstance(payload, dict):
        status = payload.get("status")
        actions = payload.get("actions", []) or []
        action0 = actions[0] if actions else {}
        if status in ("accepted", "pending", "running", "cancelling"):
            return "running", None
        if status == "success":
            return "done", {
                "success": True,
                "stdout": action0.get("stdout", ""),
                "stderr": action0.get("stderr", ""),
            }
        if status in ("failed", "timeout", "cancelled", "interrupted"):
            stderr = action0.get("error") or action0.get("stderr") or f"执行失败: {status}"
            return "done", {
                "success": False,
                "stdout": action0.get("stdout", ""),
                "stderr": stderr,
            }
        # 200 但状态值不认识：按确定失败处理，避免空轮询到超时
        return "done", {
            "success": False,
            "stdout": "",
            "stderr": f"Worker 返回未知任务状态: {status}",
        }

    if status_code == 404:
        # 任务不存在：Worker 重启后任务丢失或从未创建，继续轮询只会白等 10 分钟
        return "gone", {
            "success": False,
            "stdout": "",
            "stderr": "任务不存在（Worker 可能已重启或任务已过期）",
        }

    # 其余 4xx/5xx 视为暂时性错误，由调用方做连续失败计数
    return "retry", None


async def _wait_task_result(ip: str, port: int, task_id: str) -> dict:
    """等待任务完成并返回结果。

    Worker 的 /task/{task_id} 是幂等查询接口，结果可重复读取。
    只有明确终态才结束轮询，cancelling 等中间状态继续等待。

    轮询策略（两段频率，总超时 10 分钟）：
    - 前 60 秒：每 3 秒查询一次（快速感知短任务结束）
    - 60 秒之后：每 20 秒查询一次（长任务降频，减少无效请求）
    - 网络异常 / 非 200（404 除外）连续失败达到上限时快速终止，
      避免 Worker 不可达时空轮询 600 秒、任务记录长期悬挂 running
    """
    worker_url = f"http://{ip}:{port}/task/{task_id}"
    start_time = time.time()

    # 总超时 10 分钟
    timeout = 600.0
    # 前 60 秒以 3 秒间隔轮询，之后以 20 秒间隔轮询的分界点
    fast_phase_deadline = 60.0
    fast_interval = 3.0
    slow_interval = 20.0
    # 连续查询失败上限（网络异常 / 5xx / 响应解析失败）
    MAX_CONSECUTIVE_FAILURES = 5

    def _next_interval() -> float:
        """根据已耗时返回下一次轮询的等待间隔"""
        elapsed = time.time() - start_time
        return fast_interval if elapsed < fast_phase_deadline else slow_interval

    # 首次查询前加短暂延迟，给 worker 把任务跑起来的时间，避免过早查到 running
    await asyncio.sleep(0.5)

    consecutive_failures = 0
    last_error = ""

    while time.time() - start_time < timeout:
        resp = None
        try:
            async with httpx.AsyncClient(timeout=30.0, trust_env=False, verify=False) as client:
                resp = await client.get(worker_url)
        except Exception as exc:
            last_error = f"查询任务结果失败: {exc}"

        if resp is not None:
            payload: Optional[dict] = None
            if resp.status_code == 200:
                try:
                    payload = resp.json()
                except ValueError:
                    payload = None
                    last_error = "Worker 任务结果响应不是有效 JSON"

            action, result = _interpret_task_poll(resp.status_code, payload)
            if action in ("done", "gone"):
                # Worker 上报的执行耗时（毫秒）优先，轮询总耗时兜底
                elapsed = max(time.time() - start_time, 0.0)
                duration = elapsed
                if payload:
                    try:
                        duration_ms = float(payload.get("duration_ms") or 0)
                        if duration_ms > 0:
                            duration = duration_ms / 1000
                    except (TypeError, ValueError):
                        pass
                result["duration"] = duration or elapsed
                return result
            if action == "running":
                consecutive_failures = 0
                await asyncio.sleep(_next_interval())
                continue

            # action == "retry"（5xx 等）
            consecutive_failures += 1
            last_error = last_error or f"Worker 查询接口返回错误: {resp.status_code}"
        else:
            consecutive_failures += 1

        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            return {
                "success": False,
                "stdout": "",
                "stderr": last_error or "查询任务结果连续失败",
                "duration": time.time() - start_time,
            }

        await asyncio.sleep(_next_interval())

    return {
        "success": False,
        "stdout": "",
        "stderr": last_error or "等待结果超时",
        "duration": timeout,
    }


# ==================== 动态路由 ====================


@router.get("/{template_id}", response_model=ConfigTemplateResponse, summary="获取模板详情")
async def get_config_template(
    template_id: str,
    db: AsyncSession = Depends(get_db)
) -> ConfigTemplateResponse:
    """获取模板详情"""
    template = await ConfigTemplateService.get_by_id(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    return ConfigTemplateResponse.model_validate(template)


@router.put("/{template_id}", response_model=ConfigTemplateResponse, summary="编辑配置模板")
async def update_config_template(
    template_id: str,
    data: ConfigTemplateUpdate,
    db: AsyncSession = Depends(get_db)
) -> ConfigTemplateResponse:
    """编辑配置模板"""
    template = await ConfigTemplateService.get_by_id(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    if data.name and data.name != template.name:
        is_unique = await ConfigTemplateService.check_name_unique(
            db, data.name, exclude_id=template_id
        )
        if not is_unique:
            raise HTTPException(status_code=400, detail="模板名称已存在")

    try:
        updated_template = await ConfigTemplateService.update_with_version(
            db, template_id, data
        )
        return ConfigTemplateResponse.model_validate(updated_template)
    except Exception as e:
        await db.rollback()
        logger.error(f"更新配置模板失败: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@router.delete("/{template_id}", summary="删除配置模板")
async def delete_config_template(
    template_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除配置模板（软删除）"""
    template = await ConfigTemplateService.get_by_id(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    try:
        await ConfigTemplateService.delete(db, template_id)
        return {"status": "success", "message": "删除成功"}
    except Exception as e:
        await db.rollback()
        logger.error(f"删除配置模板失败: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


# ==================== IP 模板 API ====================

IP_TEMPLATE_ROUTER = APIRouter(prefix="/machine-selection-template", tags=["IP模板管理"])


@IP_TEMPLATE_ROUTER.get("", response_model=PaginatedResponse[MachineSelectionTemplateResponse], summary="获取IP模板列表")
async def list_machine_selection_templates(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db)
) -> PaginatedResponse[MachineSelectionTemplateResponse]:
    """获取IP模板列表（每项含 resolved_stats 机器统计）"""
    templates, total = await MachineSelectionTemplateService.get_list(
        db, page=page, page_size=page_size
    )
    items: List[MachineSelectionTemplateResponse] = []
    for t in templates:
        resp = MachineSelectionTemplateResponse.model_validate(t)
        resp.resolved_stats = await MachineSelectionTemplateService.resolve_stats(db, t)
        items.append(resp)
    return PaginatedResponse(items=items, total=total)


@IP_TEMPLATE_ROUTER.post("", response_model=MachineSelectionTemplateResponse, summary="新建IP模板")
async def create_machine_selection_template(
    data: MachineSelectionTemplateCreate,
    db: AsyncSession = Depends(get_db)
) -> MachineSelectionTemplateResponse:
    """新建IP模板"""
    is_unique = await MachineSelectionTemplateService.check_name_unique(db, data.name)
    if not is_unique:
        raise HTTPException(status_code=400, detail="模板名称已存在")

    try:
        template = await MachineSelectionTemplateService.create_with_version(db, data)
        return MachineSelectionTemplateResponse.model_validate(template)
    except Exception as e:
        await db.rollback()
        logger.error(f"创建IP模板失败: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@IP_TEMPLATE_ROUTER.get(
    "/{template_id}/machines",
    response_model=MachineSelectionTemplateDetailResponse,
    summary="获取IP模板机器明细",
)
async def get_machine_selection_template_machines(
    template_id: str,
    db: AsyncSession = Depends(get_db)
) -> MachineSelectionTemplateDetailResponse:
    """获取某 IP 模板全部 machine_ids 的明细（含已删除标记，不含 config_status/config_version）"""
    detail = await MachineSelectionTemplateService.get_machines_detail(db, template_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="模板不存在")
    return detail


@IP_TEMPLATE_ROUTER.get("/{template_id}", response_model=MachineSelectionTemplateResponse, summary="获取IP模板详情")
async def get_machine_selection_template(
    template_id: str,
    db: AsyncSession = Depends(get_db)
) -> MachineSelectionTemplateResponse:
    """获取IP模板详情"""
    template = await MachineSelectionTemplateService.get_by_id(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return MachineSelectionTemplateResponse.model_validate(template)


@IP_TEMPLATE_ROUTER.put("/{template_id}", response_model=MachineSelectionTemplateResponse, summary="编辑IP模板")
async def update_machine_selection_template(
    template_id: str,
    data: MachineSelectionTemplateUpdate,
    db: AsyncSession = Depends(get_db)
) -> MachineSelectionTemplateResponse:
    """编辑IP模板"""
    template = await MachineSelectionTemplateService.get_by_id(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    if data.name and data.name != template.name:
        is_unique = await MachineSelectionTemplateService.check_name_unique(db, data.name, exclude_id=template_id)
        if not is_unique:
            raise HTTPException(status_code=400, detail="模板名称已存在")

    try:
        updated = await MachineSelectionTemplateService.update_with_version(db, template_id, data)
        return MachineSelectionTemplateResponse.model_validate(updated)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="内部服务器错误")


@IP_TEMPLATE_ROUTER.delete("/{template_id}", summary="删除IP模板")
async def delete_machine_selection_template(
    template_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除IP模板"""
    template = await MachineSelectionTemplateService.get_by_id(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    try:
        await MachineSelectionTemplateService.delete(db, template_id)
        return {"status": "success", "message": "删除成功"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="内部服务器错误")


# ==================== 命令任务历史 API ====================

TASK_ROUTER = APIRouter(prefix="/command-task", tags=["命令任务历史"])


@TASK_ROUTER.get("", response_model=PaginatedResponse[CommandTaskResponse], summary="获取任务历史列表")
async def list_command_tasks(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    template_type: Optional[str] = Query(None, description="模板类型筛选"),
    db: AsyncSession = Depends(get_db)
) -> PaginatedResponse[CommandTaskResponse]:
    """获取任务历史列表"""
    tasks, total = await CommandTaskService.get_task_list(
        db, page=page, page_size=page_size, template_type=template_type
    )
    return PaginatedResponse(
        items=[CommandTaskResponse.model_validate(t) for t in tasks],
        total=total,
    )


@TASK_ROUTER.get("/{task_id}", response_model=CommandTaskDetailResponse, summary="获取任务详情")
async def get_command_task(
    task_id: str,
    db: AsyncSession = Depends(get_db)
) -> CommandTaskDetailResponse:
    """获取任务详情"""
    task = await CommandTaskService.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 获取关联的机器信息
    machines = []
    if task.result_detail:
        for rd in task.result_detail:
            machines.append({
                "machine_id": rd.get("machine_id"),
                "ip": rd.get("ip"),
                "device_type": rd.get("device_type"),
                "success": rd.get("success"),
                "stdout": rd.get("stdout"),
                "stderr": rd.get("stderr"),
                "duration_seconds": rd.get("duration_seconds"),
            })

    response = CommandTaskDetailResponse.model_validate(task)
    response.machines = machines
    return response


@TASK_ROUTER.delete("/{task_id}", summary="删除任务记录")
async def delete_command_task(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除任务记录"""
    task = await CommandTaskService.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    try:
        await CommandTaskService.delete(db, task_id)
        return {"status": "success", "message": "删除成功"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="内部服务器错误")
