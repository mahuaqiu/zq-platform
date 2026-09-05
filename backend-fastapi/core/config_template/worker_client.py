#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""平台侧对 Worker 的全部 HTTP 通信唯一出口。

命令下发、任务结果轮询、脚本下发、错误消息映射都收口在本模块；
其他模块（路由/service）不得直接使用 httpx 调用 Worker。
函数体自 api.py / public_api.py 原样迁移，行为不变。
"""
import asyncio
import hashlib
import time
from typing import Optional

import httpx

from fastapi import HTTPException

from core.config_template.service import (
    SUPPORTED_CONFIG_DEVICE_TYPES,
    WORKER_CONFIG_TIMEOUT,
    ConfigTemplateService,
)


def worker_http_error_message(response: httpx.Response, fallback: str) -> str:
    """提取 Worker HTTP 错误，兼容结构化 detail 和旧文本响应。"""
    try:
        payload = response.json()
    except ValueError:
        return fallback
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("code") or fallback)
    return str(detail or payload.get("message") or fallback) if isinstance(payload, dict) else fallback


async def execute_single_command(machine: dict, command: str, parent_task_id: str) -> dict:
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
                result = await wait_task_result(ip, port, task_id)
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
                    "stderr": worker_http_error_message(resp, f"Worker 返回错误: {resp.status_code}"),
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


def interpret_task_poll(
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


async def wait_task_result(ip: str, port: int, task_id: str) -> dict:
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

            action, result = interpret_task_poll(resp.status_code, payload)
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


async def deploy_single_script(machine: dict, script: dict) -> dict:
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
