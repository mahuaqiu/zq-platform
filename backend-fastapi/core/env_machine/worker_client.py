#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""执行机模块对 Worker 的 HTTP 通信出口。

批量命令执行的 Worker 调用与错误消息映射收口在本模块，
路由层不得直接使用 httpx。函数体自 api.py 原样迁移，行为不变。
"""
import logging
import time
from typing import Optional

import httpx
from fastapi import HTTPException

from core.env_machine.model import EnvMachine
from core.env_machine.schema import CommandResultItem

logger = logging.getLogger(__name__)


def worker_error_message(payload: dict, fallback: str) -> str:
    """提取 Worker 结构化错误，同时兼容旧字符串错误。"""
    error = payload.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("code") or fallback)
    if error:
        return str(error)
    detail = payload.get("detail")
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("code") or fallback)
    return str(detail or fallback)


async def execute_single_machine(machine: EnvMachine, command: str) -> CommandResultItem:
    """
    执行单台设备命令的辅助函数

    Args:
        machine: 设备对象
        command: 要执行的命令

    Returns:
        CommandResultItem: 执行结果
    """
    start_time = time.time()
    device_name = machine.asset_number or machine.ip

    # 初始化结果对象
    result = CommandResultItem(
        id=str(machine.id),
        ip=machine.ip or "",
        device_type=machine.device_type,
        device_name=device_name,
        success=False,
        stdout="",
        stderr="",
        duration_seconds=0.0,
    )

    # 过滤不支持批量命令执行的设备类型
    if machine.device_type in ("ios", "android", "harmony_mobile", "harmony_pc"):
        result.stderr = "移动设备和鸿蒙设备不支持批量命令执行"
        return result

    # 过滤虚拟设备
    if machine.is_virtual:
        result.stderr = "虚拟设备不支持批量命令执行"
        return result

    # 校验设备状态
    if machine.status != "online":
        result.stderr = f"设备状态为 {machine.status}，无法执行命令"
        return result

    # 校验 IP 和端口
    if not machine.ip or not machine.port:
        result.stderr = "设备未配置 IP 或端口"
        return result

    # 构造 Worker API 请求
    # 鸿蒙设备通过 HDC 控制，不执行 Worker 宿主机命令。
    action_type = "cmd_exec"

    worker_url = f"http://{machine.ip}:{machine.port}/task/execute"
    worker_request = {
        "platform": machine.device_type,
        "device_id": machine.device_sn or str(machine.id),
        "actions": [
            {
                "action_type": action_type,
                "value": command,
            }
        ],
    }

    # 执行请求（超时 60 秒）
    try:
        async with httpx.AsyncClient(timeout=60.0, trust_env=False, verify=False) as client:
            resp = await client.post(worker_url, json=worker_request)
            duration = time.time() - start_time
            result.duration_seconds = round(duration, 2)

            if resp.status_code == 200:
                worker_result = resp.json()

                # 检查 Worker 顶层状态
                worker_status = worker_result.get("status", "")
                if worker_status == "failed":
                    result.stderr = worker_error_message(worker_result, "命令执行失败")
                    return result

                # 检查 action 执行状态
                actions_result = worker_result.get("actions", [])
                if actions_result:
                    first_action = actions_result[0]
                    action_status = first_action.get("status", "")

                    if action_status == "failed":
                        result.stderr = first_action.get("error", "命令执行失败")
                        return result

                    # 提取输出（Worker API 返回 stdout/stderr/exit_code）
                    result.stdout = first_action.get("stdout", "")
                    result.stderr = first_action.get("stderr", "")

                    # exit_code 为 0 表示成功
                    exit_code = first_action.get("exit_code", -1)
                    if exit_code == 0:
                        result.success = True
                    else:
                        result.success = False
                        if not result.stderr and exit_code != -1:
                            result.stderr = f"命令执行失败，退出码: {exit_code}"
                else:
                    result.stderr = "Worker 未返回执行结果"
            elif resp.status_code == 502:
                result.stderr = "无法连接到设备"
            elif resp.status_code == 503:
                result.stderr = "Worker 未初始化"
            else:
                result.stderr = f"设备返回异常: {resp.status_code}"

    except httpx.TimeoutException:
        duration = time.time() - start_time
        result.duration_seconds = round(duration, 2)
        result.stderr = "命令执行超时（60秒）"
    except httpx.ConnectError:
        duration = time.time() - start_time
        result.duration_seconds = round(duration, 2)
        result.stderr = "无法连接到设备"
    except Exception as e:
        duration = time.time() - start_time
        result.duration_seconds = round(duration, 2)
        result.stderr = f"执行异常: {str(e)}"
        logger.error(f"批量命令执行失败: machine_id={machine.id}, error={e}")

    return result


async def fetch_worker_logs(
    machine: EnvMachine,
    *,
    lines: Optional[int] = None,
    request_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> dict:
    """代理 Worker 日志查询（自 api.py 的 /machine/{id}/logs 路由原样迁移）。

    调用方需已完成参数互斥校验与设备存在性/端口校验。
    """
    url = f"http://{machine.ip}:{machine.port}/worker/logs"

    # 构建查询参数
    params = {}
    if lines is not None:
        params["lines"] = lines
    elif request_id:
        params["request_id"] = request_id
    elif start_time and end_time:
        params["start_time"] = start_time
        params["end_time"] = end_time

    try:
        async with httpx.AsyncClient(timeout=30.0, trust_env=False, verify=False) as client:
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
