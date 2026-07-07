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
import logging
import time
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_schema import PaginatedResponse
from app.database import get_db
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
    CommandTaskResponse,
    CommandTaskDetailResponse,
)
from core.config_template.service import ConfigTemplateService
from core.config_template.machine_selection_template_service import MachineSelectionTemplateService
from core.config_template.command_task_service import CommandTaskService
from core.env_machine.model import EnvMachine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config-template", tags=["设备配置管理"])

# ==================== 静态路由（必须在动态路由之前）====================


@router.get("", response_model=PaginatedResponse[ConfigTemplateResponse], summary="获取模板列表")
async def list_config_templates(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    template_type: Optional[str] = Query(None, description="模板类型筛选: config/script/command"),
    db: AsyncSession = Depends(get_db)
) -> PaginatedResponse[ConfigTemplateResponse]:
    """获取配置模板列表（分页）"""
    templates, total = await ConfigTemplateService.get_list(
        db,
        page=page,
        page_size=page_size,
    )

    # 如果有类型筛选
    if template_type:
        templates = [t for t in templates if t.type == template_type]
        total = len(templates)

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
    result = await db.execute(
        select(EnvMachine).where(
            and_(
                EnvMachine.id.in_(machine_ids),
                EnvMachine.is_deleted == False,
                EnvMachine.is_virtual == False,
                EnvMachine.status == "online",
            )
        )
    )
    machines = result.scalars().all()

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
        {"id": str(m.id), "ip": m.ip, "port": m.port, "device_type": m.device_type}
        for m in machines
    ]
    task_id = str(task.id)

    # 异步执行命令（使用独立的 session，不依赖请求级 db）
    asyncio.create_task(_execute_commands_async(task_id, machine_snapshot, command))

    return DeployResponse(
        task_id=task_id,
        success_count=0,
        failed_count=0,
        skipped_count=0,
        details=[],
    )


async def _execute_commands_async(task_id: str, machines: List[dict], command: str):
    """异步执行命令（后台任务，使用独立 session）"""
    from app.database import AsyncSessionLocal

    results = []
    success_count = 0
    failed_count = 0

    for machine in machines:
        result = await _execute_single_command(machine, command)
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


async def _execute_single_command(machine: dict, command: str) -> dict:
    """执行单台机器的命令（machine 为机器快照 dict: id/ip/port/device_type）"""
    start_time = time.time()
    machine_id = machine["id"]
    ip = machine["ip"]
    port = machine["port"]
    device_type = machine["device_type"]

    # 调用 worker 异步接口
    worker_url = f"http://{ip}:{port}/task/execute_async"
    worker_request = {
        "platform": device_type,
        "device_id": machine_id,
        "actions": [{"action_type": "cmd_exec", "value": command}],
    }

    try:
        async with httpx.AsyncClient(timeout=60.0, trust_env=False, verify=False) as client:
            resp = await client.post(worker_url, json=worker_request)
            duration = time.time() - start_time

            if resp.status_code == 200:
                data = resp.json()
                task_id = data.get("task_id")

                # 等待任务完成（轮询）
                result = await _wait_task_result(ip, port, task_id, duration)
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
                    "stderr": f"Worker 返回错误: {resp.status_code}",
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


async def _wait_task_result(ip: str, port: int, task_id: str, timeout: float = 300) -> dict:
    """等待任务完成并返回结果"""
    worker_url = f"http://{ip}:{port}/task/{task_id}"
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            async with httpx.AsyncClient(timeout=30.0, trust_env=False, verify=False) as client:
                resp = await client.get(worker_url)
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status")
                    if status == "running":
                        await asyncio.sleep(2)
                        continue
                    elif status in ("success", "completed"):
                        # 获取 action 结果
                        actions = data.get("actions", [])
                        stdout = ""
                        stderr = ""
                        if actions:
                            stdout = actions[0].get("stdout", "")
                            stderr = actions[0].get("stderr", "")
                        duration = data.get("duration_ms", 0) / 1000
                        return {"success": True, "stdout": stdout, "stderr": stderr, "duration": duration}
                    else:
                        # failed
                        actions = data.get("actions", [])
                        stderr = actions[0].get("error", "执行失败") if actions else "执行失败"
                        return {"success": False, "stdout": "", "stderr": stderr, "duration": time.time() - start_time}
                elif resp.status_code == 404:
                    # 任务不存在，可能已完成并被清理
                    return {"success": False, "stdout": "", "stderr": "任务未找到", "duration": time.time() - start_time}
        except Exception:
            pass

        await asyncio.sleep(2)

    return {"success": False, "stdout": "", "stderr": "等待结果超时", "duration": timeout}


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
    """获取IP模板列表"""
    templates, total = await MachineSelectionTemplateService.get_list(
        db, page=page, page_size=page_size
    )
    return PaginatedResponse(
        items=[MachineSelectionTemplateResponse.model_validate(t) for t in templates],
        total=total,
    )


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
