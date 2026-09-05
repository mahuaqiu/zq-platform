#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""配置/命令/脚本下发编排（自 api.py、public_api.py 原样迁移，行为不变）。"""
import asyncio
import logging
from itertools import islice
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.database import AsyncSessionLocal
from utils.background_tasks import spawn_background_task
from core.config_template.command_task_service import CommandTaskService
from core.config_template.worker_client import deploy_single_script, execute_single_command
from core.config_template.service import SUPPORTED_CONFIG_DEVICE_TYPES
from core.env_machine.model import EnvMachine

logger = logging.getLogger(__name__)

# 单批并发机器数上限：与前端列表分页对齐，避免一次性打爆 worker 网络层
COMMAND_BATCH_SIZE = 20
# 单批并发机器数上限：与配置/命令下发的批量上限对齐，避免一次性打爆 worker 网络层
SCRIPT_DEPLOY_BATCH_SIZE = 20


class CommandDeployService:
    """运行命令下发编排。"""

    @classmethod
    async def execute_command_deploy(
        cls,
        db: AsyncSession,
        template,
        machine_ids: List[str],
        command_override: Optional[str] = None
    ) -> "DeployResponse":
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
                    EnvMachine.is_deleted == False,  # noqa: E712
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
            cls.run_command_batch(task_id, machine_snapshot, command),
            name=f"command-deploy-{task_id}",
        )

        # 延迟导入避免循环依赖（schema 依赖 model，model 被 api 层广泛引用）
        from core.config_template.schema import DeployResponse

        return DeployResponse(
            task_id=task_id,
            success_count=0,
            failed_count=0,
            skipped_count=0,
            details=[],
        )

    @classmethod
    async def run_command_batch(cls, task_id: str, machines: List[dict], command: str) -> None:
        """异步执行命令（后台任务，使用独立 session）。

        机器数超过 COMMAND_BATCH_SIZE 时分批并发：批内 asyncio.gather 并发执行，
        批与批之间串行。每台机器各自有独立的 worker task_id 与轮询，互不阻塞。
        """
        results = []
        success_count = 0
        failed_count = 0

        it = iter(machines)
        while batch := list(islice(it, COMMAND_BATCH_SIZE)):
            batch_results = await asyncio.gather(
                *(execute_single_command(m, command, task_id) for m in batch)
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


class ScriptDeployService:
    """脚本下发编排。"""

    @classmethod
    async def execute_script_deploy(cls, task_id: str, script: dict, machines: List[dict]) -> None:
        """后台执行脚本下发，并把结果写入任务历史。"""
        try:
            # 分批并发下发：批内 gather 并发，批间串行，避免机器数过多时无上限并发
            gathered = []
            for i in range(0, len(machines), SCRIPT_DEPLOY_BATCH_SIZE):
                batch = machines[i:i + SCRIPT_DEPLOY_BATCH_SIZE]
                gathered.extend(await asyncio.gather(
                    *(deploy_single_script(machine, script) for machine in batch),
                    return_exceptions=True,
                ))
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
            logger.exception("后台脚本下发失败: task_id=%s", task_id)
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
