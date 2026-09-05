#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""性能监控模块对 Worker 的 HTTP 通信出口。

Worker 通知（采集开始/停止）与进程列表代理收口在本模块，
路由层不得直接使用 httpx。函数体自 api.py 原样迁移，行为不变。
"""
from datetime import datetime
from typing import Optional

import httpx

from fastapi import HTTPException

from app.database import AsyncSessionLocal
from core.performance_monitor.model import PerformanceCollect


async def get_worker_processes(
    *,
    device_id: str,
    device,
    search: Optional[str],
    device_type: str,
    device_sn: Optional[str],
) -> dict:
    """代理 Worker 进程列表查询。device 为 EnvMachine ORM 对象。"""
    # Worker 性能路径需要有有效端口；Mac 等不支持类型已在调用方拒绝。
    if not device.port:
        raise HTTPException(status_code=400, detail="设备缺少端口信息，无法连接 worker")

    # 构建 worker URL
    worker_url = f"http://{device.ip}:{device.port}/api/worker/{device_id}/processes"

    # 调用 worker API
    try:
        async with httpx.AsyncClient(timeout=10.0, trust_env=False, verify=False) as client:
            params = {}
            if search:
                params["search"] = search
            params["device_type"] = device_type
            if device_sn:
                params["device_sn"] = device_sn
            resp = await client.get(worker_url, params=params)
            if resp.status_code == 200:
                return resp.json()
            else:
                raise HTTPException(status_code=resp.status_code, detail=f"Worker 返回错误: {resp.text}")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail=f"无法连接到 Worker: {device.ip}:{device.port}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Worker 响应超时")


async def notify_worker_start(
    *,
    device_id: str,
    collect_id: str,
    interval: int,
    timeout: int,
    target_processes: list | None,
    device_ip: str,
    device_port: str | int,
    device_type: str,
    device_sn: str | None,
) -> None:
    """后台通知 Worker 开始采集；失败时把平台记录标为 failed。"""
    worker_url = f"http://{device_ip}:{device_port}/api/worker/{device_id}/collect/start"
    worker_request = {
        "collect_id": collect_id,
        "interval": interval,
        "timeout": timeout,
        "target_processes": target_processes or [],
        "device_type": device_type,
    }
    if device_sn:
        worker_request["device_sn"] = device_sn
    try:
        async with httpx.AsyncClient(timeout=10.0, trust_env=False, verify=False) as client:
            resp = await client.post(worker_url, json=worker_request)
            if resp.status_code in (200, 201):
                return
            failure_message = resp.text[:500]
            status_code = resp.status_code
    except httpx.ConnectError:
        failure_message = f"无法连接到 Worker: {device_ip}:{device_port}"
        status_code = 503
    except httpx.TimeoutException:
        failure_message = "Worker 响应超时"
        status_code = 504
    except Exception as e:
        failure_message = f"通知 Worker 异常: {e}"
        status_code = 500

    async with AsyncSessionLocal() as db:
        collect = await db.get(PerformanceCollect, collect_id)
        if collect and collect.status in ("pending", "starting", "running"):
            collect.status = "failed"
            collect.failure_code = "WORKER_START_FAILED"
            collect.failure_message = failure_message
            collect.end_time = datetime.utcnow()
            collect.end_reason = "failed"
            await db.commit()
    # 仅写库，不抛给前端（前端已拿到 starting）
    return


async def notify_worker_stop(
    *,
    device_id: str,
    collect_id: str | None,
    device_ip: str,
    device_port: str | int,
    device_type: str,
    device_sn: str | None,
) -> None:
    """后台通知 Worker 停止采集。"""
    worker_url = f"http://{device_ip}:{device_port}/api/worker/{device_id}/collect/stop"
    worker_request = {"collect_id": collect_id} if collect_id else {}
    worker_request["device_type"] = device_type
    if device_sn:
        worker_request["device_sn"] = device_sn
    try:
        async with httpx.AsyncClient(timeout=10.0, trust_env=False, verify=False) as client:
            await client.post(worker_url, json=worker_request)
    except Exception:
        # 停止失败由对账逻辑兜底，不阻塞前端
        return
