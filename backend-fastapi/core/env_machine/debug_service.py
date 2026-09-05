#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""设备调试操作编排（自 api.py 的 debug-action 路由原样迁移，行为不变）。"""
import asyncio
import logging

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.env_machine.schema import DebugActionRequest, DebugActionResponse
from core.env_machine.service import EnvMachineService
from core.env_machine.worker_client import worker_error_message

logger = logging.getLogger(__name__)


class DebugActionService:
    """设备调试操作：代理转发到 Worker /remote/execute。"""

    # 鸿蒙会话停止需等待 WS 租约释放（Worker 端最长等 2s），留出余量。
    RELEASE_SESSION_TIMEOUT = 10.0

    @classmethod
    async def _release_session(cls, machine, machine_id: str) -> DebugActionResponse:
        """转发到 Worker /remote/release，立即停止设备常驻官方会话。

        平台调试页"断开"语义是完全断开：画面清空、操作禁用、设备侧投屏
        终止。其他平台（Windows 等）的推流资源随最后一个 WebSocket 关闭
        自动回收，无需显式释放，直接返回成功。
        """
        if machine.device_type not in ("harmony_mobile", "harmony_pc"):
            return DebugActionResponse(
                success=True,
                result={"stopped": False, "reason": "平台无常驻会话，无需释放"},
            )

        worker_url = f"http://{machine.ip}:{machine.port}/remote/release"
        worker_request = {
            "platform": machine.device_type,
            "device_id": machine.device_sn or machine_id,
        }
        try:
            async with httpx.AsyncClient(
                timeout=cls.RELEASE_SESSION_TIMEOUT, trust_env=False, verify=False
            ) as client:
                resp = await client.post(worker_url, json=worker_request)
            if resp.status_code == 200:
                return DebugActionResponse(success=True, result=resp.json())
            return DebugActionResponse(
                success=False,
                result={"error": f"停止会话失败: Worker 返回 {resp.status_code}"},
            )
        except httpx.TimeoutException:
            return DebugActionResponse(success=False, result={"error": "停止会话请求超时"})
        except httpx.ConnectError:
            return DebugActionResponse(success=False, result={"error": "无法连接到 Worker"})
        except Exception as e:
            logger.error(f"停止设备会话失败: {e}")
            return DebugActionResponse(success=False, result={"error": str(e)})

    @classmethod
    async def execute(
        cls,
        db: AsyncSession,
        machine_id: str,
        data: DebugActionRequest,
    ) -> DebugActionResponse:
        """
        设备调试操作接口

        代理转发调试操作到 Worker，支持以下操作：
        - screenshot: 获取截图
        - click: 点击坐标
        - double_click: 双击坐标
        - swipe: 滑动操作
        - input: 文本输入
        - press: 按键操作

        流程：
        1. 根据 machine_id 查询设备信息
        2. 校验设备类型
        3. 校验设备状态（online/using 均可远程操作）
        4. 构造 Worker API 请求体
        5. POST http://{ip}:{port}/remote/execute
        6. 返回结果
        """
        # 查询设备信息
        machine = await EnvMachineService.get_by_id(db, machine_id)
        if not machine:
            raise HTTPException(status_code=404, detail="设备不存在")

        # 校验设备类型（支持所有设备类型）
        if machine.device_type not in (
            "ios", "android", "windows", "mac", "harmony_mobile", "harmony_pc"
        ):
            raise HTTPException(status_code=400, detail="不支持该设备类型调试")

        # 调试页"断开连接"：让 Worker 立即停止设备常驻会话（鸿蒙官方投屏）。
        # 停止会话本身无害，设备状态非在线也允许执行，不走下方状态拦截。
        if data.action_type == "release_session":
            return await cls._release_session(machine, machine_id)

        # 远程操作和普通用例使用不同的 Worker 资源域，因此允许设备处于
        # using 状态；只有离线、升级等不可连接状态才拒绝请求。
        if machine.status not in ("online", "using"):
            raise HTTPException(status_code=400, detail=f"设备状态为 {machine.status}，无法调试")

        # 构造 Worker API 请求体
        action_type = data.action_type
        params = data.params

        # 构建 actions 列表
        actions = []

        # 获取 monitor 参数（桌面端设备多屏幕支持）
        monitor = params.get("monitor")

        if action_type == "screenshot":
            action = {"action_type": "screenshot", "value": "debug"}
            if monitor:
                action["monitor"] = monitor
            actions.append(action)
        elif action_type == "click":
            action = {"action_type": "click", "x": params.get("x"), "y": params.get("y")}
            if monitor:
                action["monitor"] = monitor
            actions.append(action)
        elif action_type == "double_click":
            action = {"action_type": "double_click", "x": params.get("x"), "y": params.get("y")}
            if monitor:
                action["monitor"] = monitor
            actions.append(action)
        elif action_type == "right_click":
            action = {"action_type": "right_click", "x": params.get("x"), "y": params.get("y")}
            if monitor:
                action["monitor"] = monitor
            actions.append(action)
        elif action_type == "swipe":
            action = {
                "action_type": "swipe",
                "from": {"x": params.get("from_x"), "y": params.get("from_y")},
                "to": {"x": params.get("to_x"), "y": params.get("to_y")},
                "duration": params.get("duration", 500)
            }
            if monitor:
                action["monitor"] = monitor
            actions.append(action)
        elif action_type == "input":
            action = {
                "action_type": "input",
                "x": params.get("x"),
                "y": params.get("y"),
                "text": params.get("text")
            }
            if monitor:
                action["monitor"] = monitor
            actions.append(action)
        elif action_type == "press":
            actions.append({"action_type": "press", "key": params.get("key")})
        elif action_type == "unlock_screen":
            actions.append({"action_type": "unlock_screen", "value": params.get("value")})
        else:
            raise HTTPException(status_code=400, detail=f"不支持的操作类型: {action_type}")

        # 发送请求到 Worker
        worker_url = f"http://{machine.ip}:{machine.port}/remote/execute"
        worker_request = {
            "platform": machine.device_type,
            "device_id": machine.device_sn or machine_id,
            "actions": actions
        }

        # 根据操作类型设置超时时间（解锁操作需要更长时间）
        request_timeout = 35.0 if action_type == "unlock_screen" else 20.0

        try:
            async with httpx.AsyncClient(timeout=request_timeout, trust_env=False, verify=False) as client:
                resp = None
                for attempt in range(3):
                    resp = await client.post(worker_url, json=worker_request)
                    if resp.status_code != 503 or attempt == 2:
                        break
                    logger.warning(
                        "Worker 返回 503，准备重试调试操作: machine_id=%s attempt=%s",
                        machine_id,
                        attempt + 1,
                    )
                    await asyncio.sleep(0.4 * (attempt + 1))

                assert resp is not None
                if resp.status_code == 200:
                    worker_result = resp.json()

                    # 首先检查 worker 顶层状态（如设备未找到等情况）
                    worker_status = worker_result.get("status", "")
                    worker_error = worker_error_message(worker_result, "设备操作失败")
                    if worker_status == "failed":
                        return DebugActionResponse(
                            success=False,
                            result={"error": worker_error or "设备操作失败"}
                        )

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
                    try:
                        payload = resp.json()
                    except ValueError:
                        payload = {}
                    return DebugActionResponse(
                        success=False,
                        result={"error": worker_error_message(payload, f"设备返回异常: {resp.status_code}")},
                    )
        except httpx.TimeoutException:
            return DebugActionResponse(success=False, result={"error": "操作超时"})
        except httpx.ConnectError:
            return DebugActionResponse(success=False, result={"error": "无法连接到设备"})
        except Exception as e:
            logger.error(f"调试操作失败: {e}")
            return DebugActionResponse(success=False, result={"error": str(e)})
