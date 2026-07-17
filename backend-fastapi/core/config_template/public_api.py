#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""免鉴权脚本下发接口。"""
import asyncio
import time
from typing import List

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.database import AsyncSessionLocal, get_db
from core.config_template.command_task_service import CommandTaskService
from core.config_template.machine_selection_template_model import MachineSelectionTemplate
from core.config_template.model import ConfigTemplate
from core.config_template.service import (
    ConfigTemplateService,
    SUPPORTED_CONFIG_DEVICE_TYPES,
    WORKER_CONFIG_TIMEOUT,
)
from core.env_machine.model import EnvMachine


router = APIRouter(prefix="/api/core/config-template", tags=["外部脚本下发"])


class ScriptDeployRequest(BaseModel):
    """按脚本名称和机器模板名称触发脚本下发请求。"""

    script_name: str = Field(..., min_length=1, max_length=128, description="脚本名称")
    template_name: str = Field(..., min_length=1, max_length=64, description="机器模板名称")


class ScriptDeployResponse(BaseModel):
    """脚本异步下发响应。"""

    success: bool = Field(True, description="是否已受理")
    message: str = Field(..., description="受理结果说明")
    task_id: str = Field(..., description="任务历史记录ID")
    status: str = Field("running", description="任务状态")


@router.post("/deploy-script", response_model=ScriptDeployResponse, summary="按名称异步下发脚本")
async def deploy_script_by_name(
    data: ScriptDeployRequest,
    db: AsyncSession = Depends(get_db),
) -> ScriptDeployResponse:
    """按保存的脚本名称和机器模板名称触发下发，不等待 Worker 执行结果。"""
    script_result = await db.execute(
        select(ConfigTemplate)
        .where(
            and_(
                ConfigTemplate.type == "script",
                ConfigTemplate.is_deleted == False,  # noqa: E712
                or_(
                    ConfigTemplate.name == data.script_name,
                    ConfigTemplate.script_name == data.script_name,
                ),
            )
        )
        .order_by(ConfigTemplate.sys_update_datetime.desc())
    )
    script_template = script_result.scalars().first()
    if not script_template:
        raise HTTPException(status_code=404, detail="脚本不存在")

    machine_template_result = await db.execute(
        select(MachineSelectionTemplate).where(
            and_(
                MachineSelectionTemplate.name == data.template_name,
                MachineSelectionTemplate.is_deleted == False,  # noqa: E712
            )
        )
    )
    machine_template = machine_template_result.scalars().first()
    if not machine_template:
        raise HTTPException(status_code=404, detail="机器模板不存在")

    machine_conditions = [
        EnvMachine.is_deleted == False,  # noqa: E712
        EnvMachine.is_virtual == False,  # noqa: E712
    ]
    if machine_template.machine_ids:
        machine_conditions.append(EnvMachine.id.in_(machine_template.machine_ids))
    else:
        if machine_template.namespace:
            machine_conditions.append(EnvMachine.namespace == machine_template.namespace)
        if machine_template.device_type:
            machine_conditions.append(EnvMachine.device_type == machine_template.device_type)
        if machine_template.ip_pattern:
            machine_conditions.append(EnvMachine.ip.ilike(f"%{machine_template.ip_pattern}%"))

    machine_result = await db.execute(select(EnvMachine).where(and_(*machine_conditions)))
    machines = list(machine_result.scalars().all())
    if not machines:
        raise HTTPException(status_code=400, detail="机器模板没有匹配到执行机")

    task = await CommandTaskService.create_task(
        db,
        template_id=str(script_template.id),
        template_type="script",
        template_name=script_template.name,
        command=f"机器模板: {data.template_name}",
        machine_count=len(machines),
    )

    script_snapshot = {
        "name": script_template.script_name,
        "content": script_template.config_content,
        "version": script_template.version,
    }
    machine_snapshot = [
        {
            "id": str(machine.id),
            "ip": machine.ip,
            "port": machine.port,
            "device_type": machine.device_type,
            "status": machine.status,
        }
        for machine in machines
    ]
    task_id = str(task.id)
    asyncio.create_task(_execute_script_deploy_async(task_id, script_snapshot, machine_snapshot))

    return ScriptDeployResponse(
        success=True,
        message="脚本下发任务已受理",
        task_id=task_id,
        status="running",
    )


async def _execute_script_deploy_async(task_id: str, script: dict, machines: List[dict]) -> None:
    """后台执行脚本下发，并把结果写入任务历史。"""
    try:
        gathered = await asyncio.gather(
            *(_execute_single_script(machine, script) for machine in machines),
            return_exceptions=True,
        )
        results = []
        for machine, result in zip(machines, gathered):
            if isinstance(result, Exception):
                results.append({
                    "machine_id": machine["id"],
                    "ip": machine.get("ip") or "",
                    "device_type": machine.get("device_type") or "",
                    "success": False,
                    "stdout": "",
                    "stderr": f"执行异常: {result}",
                    "duration_seconds": 0,
                })
            else:
                results.append(result)

        success_count = sum(1 for result in results if result["success"])
        failed_count = len(results) - success_count
        status = "success" if failed_count == 0 else ("partial" if success_count else "failed")

        async with AsyncSessionLocal() as result_db:
            success_ids = [result["machine_id"] for result in results if result["success"]]
            if success_ids:
                machine_result = await result_db.execute(
                    select(EnvMachine).where(EnvMachine.id.in_(success_ids))
                )
                for machine in machine_result.scalars().all():
                    scripts = dict(machine.scripts or {})
                    scripts[script["name"]] = script["version"]
                    machine.scripts = scripts
                    flag_modified(machine, "scripts")

            await CommandTaskService.update_task_result(
                result_db,
                task_id,
                status=status,
                success_count=success_count,
                failed_count=failed_count,
                result_detail=results,
            )
    except Exception:
        import logging
        logging.getLogger(__name__).exception("后台脚本下发失败: task_id=%s", task_id)
        async with AsyncSessionLocal() as result_db:
            await CommandTaskService.update_task_result(
                result_db,
                task_id,
                status="failed",
                success_count=0,
                failed_count=len(machines),
                result_detail=[{
                    "success": False,
                    "stdout": "",
                    "stderr": "后台脚本下发异常",
                    "duration_seconds": 0,
                }],
            )


async def _execute_single_script(machine: dict, script: dict) -> dict:
    """执行单台机器的脚本下发并返回任务历史明细。"""
    start_time = time.time()
    machine_id = machine["id"]
    ip = machine.get("ip") or ""
    device_type = machine.get("device_type") or ""
    result = {
        "machine_id": machine_id,
        "ip": ip,
        "device_type": device_type,
        "success": False,
        "stdout": "",
        "stderr": "",
        "duration_seconds": 0,
    }

    target_os = ConfigTemplateService._get_target_os_from_extension(script["name"])
    if device_type not in SUPPORTED_CONFIG_DEVICE_TYPES:
        result["stderr"] = "该设备类型暂不支持脚本下发"
        return result
    if target_os and device_type != target_os:
        result["stderr"] = f"脚本仅支持 {target_os} 设备"
        return result
    if machine.get("status") != "online":
        result["stderr"] = f"机器状态为 {machine.get('status')}"
        return result
    if not ip or not machine.get("port"):
        result["stderr"] = "机器未配置 IP 或端口"
        return result

    try:
        async with httpx.AsyncClient(
            timeout=WORKER_CONFIG_TIMEOUT,
            trust_env=False,
            verify=False,
        ) as client:
            response = await client.post(
                f"http://{ip}:{machine['port']}/worker/scripts",
                json={
                    "name": script["name"],
                    "content": script["content"],
                    "version": script["version"],
                    "overwrite": True,
                },
            )
        if response.status_code == 200:
            payload = response.json()
            if payload.get("status") == "success":
                result["success"] = True
            else:
                result["stderr"] = f"Worker 返回异常状态: {payload.get('status')}"
        elif response.status_code == 409:
            result["stderr"] = "脚本更新进行中或已存在"
        elif response.status_code == 503:
            result["stderr"] = "Worker 未初始化"
        else:
            result["stderr"] = f"Worker 返回错误状态码: {response.status_code}"
    except httpx.TimeoutException:
        result["stderr"] = "Worker 响应超时"
    except httpx.ConnectError:
        result["stderr"] = "无法连接到 Worker"
    except Exception as exc:
        result["stderr"] = f"网络错误: {exc}"
    finally:
        result["duration_seconds"] = round(time.time() - start_time, 2)
    return result