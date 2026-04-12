#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Time: 2026-04-12
@File: nanoclaw_client.py
@Desc: NanoClaw API 客户端封装
"""
import logging
from typing import Optional, Dict, Any
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class NanoClawClient:
    """NanoClaw API 客户端"""

    def __init__(self):
        self.api_url = settings.NANOCLAW_API_URL
        self.token = settings.NANOCLAW_API_TOKEN
        self.headers = {
            "Content-Type": "application/json",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        url = f"{self.api_url}/api/health"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self.headers)
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException as e:
            logger.error(f"NanoClaw 健康检查超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"NanoClaw 健康检查请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"NanoClaw 健康检查异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def register_group(
        self,
        chat_id: str,
        name: str,
        folder: str,
        trigger: str,
        is_group: bool = True,
        requires_trigger: bool = True
    ) -> Dict[str, Any]:
        """注册群组到 NanoClaw"""
        url = f"{self.api_url}/api/register"
        data = {
            "chat_id": chat_id,
            "name": name,
            "folder": folder,
            "trigger": trigger,
            "is_group": is_group,
            "requires_trigger": requires_trigger
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=self.headers, json=data)
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException as e:
            logger.error(f"NanoClaw 注册群组超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"NanoClaw 注册群组请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"NanoClaw 注册群组异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def send_message(
        self,
        chat_id: str,
        sender: str,
        content: str,
        sender_name: Optional[str] = None,
        chat_name: Optional[str] = None,
        is_group: bool = True
    ) -> Dict[str, Any]:
        """发送消息到 NanoClaw"""
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

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, headers=self.headers, json=data)
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException as e:
            logger.error(f"NanoClaw 发送消息超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"NanoClaw 发送消息请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"NanoClaw 发送消息异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def clear_session(self, chat_id: str) -> Dict[str, Any]:
        """清除 NanoClaw 会话"""
        url = f"{self.api_url}/api/clear"
        data = {"chat_id": chat_id}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=self.headers, json=data)
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException as e:
            logger.error(f"NanoClaw 清除会话超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"NanoClaw 清除会话请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"NanoClaw 清除会话异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def get_session_info(self, chat_id: str) -> Dict[str, Any]:
        """查询 NanoClaw 会话状态"""
        url = f"{self.api_url}/api/session/{chat_id}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self.headers)
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException as e:
            logger.error(f"NanoClaw 查询会话超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"NanoClaw 查询会话请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"NanoClaw 查询会话异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}


# 全局客户端实例
nanoclaw_client = NanoClawClient()