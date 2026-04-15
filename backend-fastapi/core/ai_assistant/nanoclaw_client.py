#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Time: 2026-04-12
@File: nanoclaw_client.py
@Desc: NanoClaw API 客户端封装（支持回调模式和轮询保底）
"""
import asyncio
import json
from typing import Optional, Dict, Any
import httpx
from app.config import settings
from utils.logging_config import get_logger

logger = get_logger("nanoclaw")


class NanoClawClient:
    """NanoClaw API 客户端"""

    def __init__(self):
        self.api_url = settings.NANOCLAW_API_URL
        self.token = settings.NANOCLAW_API_TOKEN
        # 回调 URL（本服务的回调接口地址）
        self.callback_url = getattr(settings, 'NANOCLAW_CALLBACK_URL', None)
        self.headers = {
            "Content-Type": "application/json",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        url = f"{self.api_url}/api/health"
        logger.info(f"[NanoClaw] 健康检查请求: GET {url}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 健康检查响应: {json.dumps(result, ensure_ascii=False)}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 健康检查超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 健康检查请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 健康检查异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def register_group(
        self,
        chat_id: str,
        folder: str,
        profiles: Optional[list] = None,
        name: Optional[str] = None,
        trigger: Optional[str] = None,
        default_profile: Optional[str] = None,
        is_group: bool = True,
        requires_trigger: bool = True,
        is_main: bool = False
    ) -> Dict[str, Any]:
        """
        注册群组到 NanoClaw（支持新旧两种格式）

        新格式（推荐）：使用 profiles 数组，支持多角色
        旧格式：使用 name + trigger，单一角色

        Args:
            chat_id: 聊天唯一标识
            folder: 群组文件夹名称
            profiles: 角色数组（新格式），每个元素包含 id, name, trigger, description, system_prompt 等
            name: 群组名称（旧格式）
            trigger: 触发词（旧格式）
            default_profile: 默认角色 ID（新格式）
            is_group: 是否群聊
            requires_trigger: 是否需要触发词
            is_main: 是否主群组
        """
        url = f"{self.api_url}/api/register"
        data = {
            "chat_id": chat_id,
            "folder": folder,
            "is_group": is_group,
            "requires_trigger": requires_trigger,
            "is_main": is_main
        }

        # 新格式：profiles 数组
        if profiles:
            data["profiles"] = profiles
            if default_profile:
                data["default_profile"] = default_profile
        # 旧格式：name + trigger
        elif name and trigger:
            data["name"] = name
            data["trigger"] = trigger
        else:
            logger.error(f"[NanoClaw] 注册群组参数无效: 必须提供 profiles 或 name+trigger")
            return {"error": "invalid_params", "message": "Must provide either profiles or name+trigger"}

        logger.info(f"[NanoClaw] 注册群组请求: POST {url}")
        logger.info(f"[NanoClaw] 注册群组请求体: {json.dumps(data, ensure_ascii=False)}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=self.headers, json=data)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 注册群组响应: {json.dumps(result, ensure_ascii=False)}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 注册群组超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 注册群组请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 注册群组异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def update_group(
        self,
        chat_id: str,
        profiles: Optional[list] = None,
        default_profile: Optional[str] = None,
        requires_trigger: Optional[bool] = None,
        name: Optional[str] = None,
        trigger: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        更新 NanoClaw 群组配置（支持多角色）

        Args:
            chat_id: 聊天 ID
            profiles: 角色数组（传入后会完全替换现有角色）
            default_profile: 默认角色 ID
            requires_trigger: 是否需要触发词
            name: 群组名称（旧格式）
            trigger: 触发词（旧格式）
        """
        # jid 格式为 http:{chat_id}
        jid = f"http:{chat_id}"
        url = f"{self.api_url}/api/groups/{jid}"
        data = {}

        if profiles:
            data["profiles"] = profiles
        if default_profile:
            data["default_profile"] = default_profile
        if requires_trigger is not None:
            data["requires_trigger"] = requires_trigger
        if name:
            data["name"] = name
        if trigger:
            data["trigger"] = trigger

        logger.info(f"[NanoClaw] 更新群组请求: PUT {url}")
        logger.info(f"[NanoClaw] 更新群组请求体: {json.dumps(data, ensure_ascii=False)}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.put(url, headers=self.headers, json=data)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 更新群组响应: {json.dumps(result, ensure_ascii=False)}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 更新群组超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 更新群组请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 更新群组异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def get_group_detail(self, chat_id: str) -> Dict[str, Any]:
        """
        查询 NanoClaw 群组详情（包括所有角色配置）

        Args:
            chat_id: 聊天 ID
        """
        # jid 格式为 http:{chat_id}
        jid = f"http:{chat_id}"
        url = f"{self.api_url}/api/groups/{jid}"
        logger.info(f"[NanoClaw] 查询群组详情请求: GET {url}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 查询群组详情响应: {json.dumps(result, ensure_ascii=False)}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 查询群组详情超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 查询群组详情请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 查询群组详情异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def get_groups(self) -> Dict[str, Any]:
        """
        查询 NanoClaw 已注册群组列表
        """
        url = f"{self.api_url}/api/groups"
        logger.info(f"[NanoClaw] 查询群组列表请求: GET {url}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 查询群组列表响应: {json.dumps(result, ensure_ascii=False)}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 查询群组列表超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 查询群组列表请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 查询群组列表异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def delete_group(self, chat_id: str) -> Dict[str, Any]:
        """
        删除 NanoClaw 群组（同时删除所有角色配置）

        Args:
            chat_id: 聊天 ID

        注意：
            - 删除群组时会同时删除所有角色配置
            - 删除群组时会清除该群组的会话记录
            - 主群组（is_main=true）不能删除，需要先取消主群组状态
        """
        # jid 格式为 http:{chat_id}
        jid = f"http:{chat_id}"
        url = f"{self.api_url}/api/groups/{jid}"
        logger.info(f"[NanoClaw] 删除群组请求: DELETE {url}")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.delete(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 删除群组响应: {json.dumps(result, ensure_ascii=False)}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 删除群组超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 删除群组请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 删除群组异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def send_message(
        self,
        chat_id: str,
        sender: str,
        content: str,
        sender_name: Optional[str] = None,
        chat_name: Optional[str] = None,
        is_group: bool = True,
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """发送消息到 NanoClaw（支持回调模式）"""
        url = f"{self.api_url}/api/message"
        data = {
            "chat_id": chat_id,
            "sender": sender,
            "content": content,
            "is_group": is_group
        }
        if sender_name:
            data["sender_name"] = sender_name
        if chat_name:
            data["chat_name"] = chat_name
        # 添加回调 URL
        if callback_url:
            data["callback_url"] = callback_url

        logger.info(f"[NanoClaw] 发送消息请求: POST {url}")
        logger.info(f"[NanoClaw] 发送消息请求体: {json.dumps(data, ensure_ascii=False)}")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, headers=self.headers, json=data)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 发送消息响应: {json.dumps(result, ensure_ascii=False)}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 发送消息超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 发送消息请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 发送消息异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def get_outbox(self, chat_id: str) -> Dict[str, Any]:
        """轮询获取 AI 回复（保底机制）"""
        # jid 格式为 http:{chat_id}
        jid = f"http:{chat_id}"
        url = f"{self.api_url}/api/outbox/{jid}"
        logger.info(f"[NanoClaw] 获取回复请求: GET {url}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 获取回复响应: {json.dumps(result, ensure_ascii=False)}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 获取回复超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 获取回复请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 获取回复异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def poll_for_reply(
        self,
        chat_id: str,
        session_id: str,
        max_attempts: int = 5,
        interval_seconds: int = 60
    ) -> Optional[str]:
        """
        保底轮询获取回复

        Args:
            chat_id: NanoClaw chat_id
            session_id: 本系统会话 ID（用于存储消息）
            max_attempts: 最大轮询次数
            interval_seconds: 轮询间隔（秒）

        Returns:
            AI 回复内容（如果有）
        """
        logger.info(f"[NanoClaw] 开始保底轮询: chat_id={chat_id}, session_id={session_id}, attempts={max_attempts}")

        for attempt in range(1, max_attempts + 1):
            await asyncio.sleep(interval_seconds)

            try:
                result = await self.get_outbox(chat_id)

                if "error" in result:
                    logger.warning(f"[NanoClaw] 轮询第 {attempt} 次失败: {result.get('error')}")
                    continue

                # 检查是否有消息
                messages = result.get("messages", [])
                count = result.get("count", 0)

                if count > 0 and messages:
                    reply_content = messages[0]
                    logger.info(f"[NanoClaw] 轮询第 {attempt} 次成功获取回复: chat_id={chat_id}, content={reply_content[:200]}...")
                    return reply_content

            except Exception as e:
                logger.error(f"[NanoClaw] 轮询第 {attempt} 次异常: {str(e)}")

        logger.warning(f"[NanoClaw] 保底轮询结束，未获取到回复: chat_id={chat_id}")
        return None

    async def clear_session(self, chat_id: str) -> Dict[str, Any]:
        """清除 NanoClaw 会话"""
        url = f"{self.api_url}/api/clear"
        data = {"chat_id": chat_id}
        logger.info(f"[NanoClaw] 清除会话请求: POST {url}")
        logger.info(f"[NanoClaw] 清除会话请求体: {json.dumps(data, ensure_ascii=False)}")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=self.headers, json=data)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 清除会话响应: {json.dumps(result, ensure_ascii=False)}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 清除会话超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 清除会话请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 清除会话异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def get_session_info(self, chat_id: str) -> Dict[str, Any]:
        """查询 NanoClaw 会话状态"""
        url = f"{self.api_url}/api/session/{chat_id}"
        logger.info(f"[NanoClaw] 查询会话状态请求: GET {url}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 查询会话状态响应: {json.dumps(result, ensure_ascii=False)}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 查询会话超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 查询会话请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 查询会话异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def get_skills(self) -> Dict[str, Any]:
        """
        查询 NanoClaw 所有全局 Skill

        Returns:
            {"skills": [...], "count": N}
        """
        url = f"{self.api_url}/api/skills"
        logger.info(f"[NanoClaw] 查询 Skill 列表请求: GET {url}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 查询 Skill 列表响应: count={result.get('count', 0)}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 查询 Skill 列表超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 查询 Skill 列表请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 查询 Skill 列表异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def get_skill_detail(self, skill_id: str) -> Dict[str, Any]:
        """
        查询 NanoClaw Skill 详情

        Args:
            skill_id: Skill ID

        Returns:
            {"id": "...", "name": "...", "description": "...", "content": "..."}
        """
        url = f"{self.api_url}/api/skills/{skill_id}"
        logger.info(f"[NanoClaw] 查询 Skill 详情请求: GET {url}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 查询 Skill 详情响应: id={skill_id}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 查询 Skill 详情超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 查询 Skill 详情请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 查询 Skill 详情异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def create_skill(self, skill_id: str, content: str) -> Dict[str, Any]:
        """
        创建 NanoClaw Skill

        Args:
            skill_id: Skill ID
            content: SKILL.md 完整内容（含 frontmatter）

        Returns:
            {"status": "ok", "id": "..."} 或 {"error": "..."}
        """
        url = f"{self.api_url}/api/skills/{skill_id}"
        data = {"content": content}
        logger.info(f"[NanoClaw] 创建 Skill 请求: POST {url}")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=self.headers, json=data)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 创建 Skill 响应: id={skill_id}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 创建 Skill 超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 创建 Skill 请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 创建 Skill 异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def update_skill(self, skill_id: str, content: str) -> Dict[str, Any]:
        """
        更新 NanoClaw Skill

        Args:
            skill_id: Skill ID
            content: SKILL.md 完整内容（含 frontmatter）

        Returns:
            {"status": "ok", "id": "..."} 或 {"error": "..."}
        """
        url = f"{self.api_url}/api/skills/{skill_id}"
        data = {"content": content}
        logger.info(f"[NanoClaw] 更新 Skill 请求: PUT {url}")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.put(url, headers=self.headers, json=data)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 更新 Skill 响应: id={skill_id}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 更新 Skill 超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 更新 Skill 请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 更新 Skill 异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def delete_skill(self, skill_id: str) -> Dict[str, Any]:
        """
        删除 NanoClaw Skill

        Args:
            skill_id: Skill ID

        Returns:
            {"status": "ok", "id": "..."} 或 {"error": "..."}
        """
        url = f"{self.api_url}/api/skills/{skill_id}"
        logger.info(f"[NanoClaw] 删除 Skill 请求: DELETE {url}")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.delete(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 删除 Skill 响应: id={skill_id}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 删除 Skill 超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 删除 Skill 请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 删除 Skill 异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def assign_skill_to_profile(
        self, jid: str, profile_id: str, skill_id: str
    ) -> Dict[str, Any]:
        """
        分配 Skill 到群组角色

        Args:
            jid: 群组标识，格式 http:{chat_id}
            profile_id: 角色 ID
            skill_id: Skill ID

        Returns:
            {"status": "ok", ...} 或 {"error": "..."}
        """
        url = f"{self.api_url}/api/profiles/{jid}/{profile_id}/skills/{skill_id}"
        logger.info(f"[NanoClaw] 分配 Skill 请求: POST {url}")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 分配 Skill 响应: skill={skill_id} -> profile={profile_id}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 分配 Skill 超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 分配 Skill 请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 分配 Skill 异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def remove_skill_from_profile(
        self, jid: str, profile_id: str, skill_id: str
    ) -> Dict[str, Any]:
        """
        移除群组角色的 Skill

        Args:
            jid: 群组标识，格式 http:{chat_id}
            profile_id: 角色 ID
            skill_id: Skill ID

        Returns:
            {"status": "ok", ...} 或 {"error": "..."}
        """
        url = f"{self.api_url}/api/profiles/{jid}/{profile_id}/skills/{skill_id}"
        logger.info(f"[NanoClaw] 移除 Skill 请求: DELETE {url}")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.delete(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 移除 Skill 响应: skill={skill_id} from profile={profile_id}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 移除 Skill 超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 移除 Skill 请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 移除 Skill 异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def get_profile_skills(self, jid: str, profile_id: str) -> Dict[str, Any]:
        """
        查询群组角色的 Skill 列表

        Args:
            jid: 群组标识，格式 http:{chat_id}
            profile_id: 角色 ID

        Returns:
            {"skills": [...], "count": N} 或 {"error": "..."}
        """
        url = f"{self.api_url}/api/profiles/{jid}/{profile_id}/skills"
        logger.info(f"[NanoClaw] 查询角色 Skill 列表请求: GET {url}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 查询角色 Skill 列表响应: count={result.get('count', 0)}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 查询角色 Skill 列表超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 查询角色 Skill 列表请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 查询角色 Skill 列表异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    # ==================== 角色管理 API ====================

    async def get_profiles(self, jid: str) -> Dict[str, Any]:
        """
        获取群组角色列表

        Args:
            jid: 群组标识，格式 http:{chat_id}

        Returns:
            {
                "jid": "http:chat-123",
                "profiles": [
                    {
                        "id": "xiaoma",
                        "name": "小马",
                        "trigger": "@XiaoMa",
                        "description": "...",
                        "system_prompt": "# 小马\n\n你是一个...",
                        "is_active": true,
                        "added_at": "2026-04-15T..."
                    }
                ],
                "count": 1
            }
        """
        url = f"{self.api_url}/api/profiles/{jid}"
        logger.info(f"[NanoClaw] 获取角色列表请求: GET {url}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 获取角色列表响应: jid={jid}, count={result.get('count', 0)}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 获取角色列表超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 获取角色列表请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 获取角色列表异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def get_profile(self, jid: str, profile_id: str) -> Dict[str, Any]:
        """
        获取单个角色详情

        Args:
            jid: 群组标识，格式 http:{chat_id}
            profile_id: 角色 ID

        Returns:
            {
                "jid": "http:chat-123",
                "profile": {
                    "id": "xiaoma",
                    "name": "小马",
                    "trigger": "@XiaoMa",
                    "description": "...",
                    "system_prompt": "# 小马\n\n你是一个...",
                    "is_active": true,
                    "added_at": "..."
                }
            }
        """
        url = f"{self.api_url}/api/profiles/{jid}/{profile_id}"
        logger.info(f"[NanoClaw] 获取角色详情请求: GET {url}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 获取角色详情响应: jid={jid}, profile_id={profile_id}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 获取角色详情超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 获取角色详情请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 获取角色详情异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def create_profile(
        self,
        jid: str,
        name: str,
        trigger: str,
        system_prompt: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建角色

        Args:
            jid: 群组标识，格式 http:{chat_id}
            name: 角色名称
            trigger: 触发词（如 @XiaoMa）
            system_prompt: 系统提示词（可选，不传则自动生成）
            description: 角色描述（可选）

        Returns:
            {
                "status": "ok",
                "jid": "http:chat-123",
                "profile": {
                    "id": "profile-xxx",
                    "name": "小马",
                    "trigger": "@XiaoMa",
                    "system_prompt": "# 小马\n\n...",
                    "is_active": true,
                    "added_at": "..."
                }
            }
        """
        url = f"{self.api_url}/api/profiles/{jid}"
        data = {
            "name": name,
            "trigger": trigger,
        }
        if system_prompt:
            data["system_prompt"] = system_prompt
        if description:
            data["description"] = description

        logger.info(f"[NanoClaw] 创建角色请求: POST {url}")
        logger.info(f"[NanoClaw] 创建角色请求体: {json.dumps(data, ensure_ascii=False)}")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=self.headers, json=data)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 创建角色响应: jid={jid}, name={name}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 创建角色超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 创建角色请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 创建角色异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def update_profile(
        self,
        jid: str,
        profile_id: str,
        system_prompt: Optional[str] = None,
        name: Optional[str] = None,
        trigger: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        更新角色

        Args:
            jid: 群组标识，格式 http:{chat_id}
            profile_id: 角色 ID
            system_prompt: 系统提示词（可选）
            name: 角色名称（可选）
            trigger: 触发词（可选）
            description: 角色描述（可选）
            is_active: 是否启用（可选）

        Returns:
            {
                "status": "ok",
                "jid": "http:chat-123",
                "profileId": "xiaoma",
                "updates": { ... }
            }
        """
        url = f"{self.api_url}/api/profiles/{jid}/{profile_id}"
        data = {}
        if system_prompt is not None:
            data["system_prompt"] = system_prompt
        if name is not None:
            data["name"] = name
        if trigger is not None:
            data["trigger"] = trigger
        if description is not None:
            data["description"] = description
        if is_active is not None:
            data["is_active"] = is_active

        logger.info(f"[NanoClaw] 更新角色请求: PUT {url}")
        logger.info(f"[NanoClaw] 更新角色请求体: {json.dumps(data, ensure_ascii=False)}")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.put(url, headers=self.headers, json=data)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 更新角色响应: jid={jid}, profile_id={profile_id}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 更新角色超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 更新角色请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 更新角色异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def delete_profile(self, jid: str, profile_id: str) -> Dict[str, Any]:
        """
        删除角色

        Args:
            jid: 群组标识，格式 http:{chat_id}
            profile_id: 角色 ID

        Returns:
            {"status": "ok", ...} 或 {"error": "..."}
        """
        url = f"{self.api_url}/api/profiles/{jid}/{profile_id}"
        logger.info(f"[NanoClaw] 删除角色请求: DELETE {url}")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.delete(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 删除角色响应: jid={jid}, profile_id={profile_id}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 删除角色超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 删除角色请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 删除角色异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}


# 全局客户端实例
nanoclaw_client = NanoClawClient()