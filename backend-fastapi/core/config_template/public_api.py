#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""免鉴权脚本下发接口。"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from utils.background_tasks import spawn_background_task
from core.config_template.command_task_service import CommandTaskService
from core.config_template.deploy_service import ScriptDeployService
from core.config_template.machine_selection_template_model import MachineSelectionTemplate
from core.config_template.machine_selection_template_service import MachineSelectionTemplateService
from core.config_template.model import ConfigTemplate
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


class ScriptDeployStatusResponse(BaseModel):
    """脚本异步下发任务进度查询响应。"""

    task_id: str = Field(..., description="任务历史记录ID")
    status: str = Field(..., description="任务状态: running/success/failed/partial")
    template_name: str = Field(..., description="脚本模板名称")
    machine_count: int = Field(..., description="目标机器数量")
    success_count: int = Field(..., description="成功数量")
    failed_count: int = Field(..., description="失败数量")
    result_detail: Optional[List[dict]] = Field(None, description="每台机器执行结果详情")
    sys_create_datetime: Optional[datetime] = Field(None, description="任务创建时间")
    finished_datetime: Optional[datetime] = Field(None, description="任务结束时间")


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

    if machine_template.machine_targets or machine_template.machine_ids:
        resolved = await MachineSelectionTemplateService.resolve_machines(
            db, machine_template
        )
        machines = [machine for _, machine in resolved if machine is not None]
    else:
        machine_conditions = [
            EnvMachine.is_deleted == False,  # noqa: E712
            EnvMachine.is_virtual == False,  # noqa: E712
        ]
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
    spawn_background_task(
        ScriptDeployService.execute_script_deploy(task_id, script_snapshot, machine_snapshot),
        name=f"script-deploy-{task_id}",
    )

    return ScriptDeployResponse(
        success=True,
        message="脚本下发任务已受理",
        task_id=task_id,
        status="running",
    )


@router.get(
    "/deploy-script/{task_id}",
    response_model=ScriptDeployStatusResponse,
    summary="查询脚本异步下发任务进度",
)
async def get_script_deploy_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> ScriptDeployStatusResponse:
    """按任务 ID 查询脚本异步下发进度与结果。"""
    task = await CommandTaskService.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return ScriptDeployStatusResponse(
        task_id=str(task.id),
        status=task.status,
        template_name=task.template_name,
        machine_count=task.machine_count,
        success_count=task.success_count,
        failed_count=task.failed_count,
        result_detail=task.result_detail,
        sys_create_datetime=task.sys_create_datetime,
        finished_datetime=task.finished_datetime,
    )
