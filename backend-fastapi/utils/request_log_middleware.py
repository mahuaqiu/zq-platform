#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2026-03-29
@File: request_log_middleware.py
@Desc: HTTP 请求日志中间件
"""
import time
import json
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message, Receive, Send
from starlette.responses import StreamingResponse

from utils.logging_config import get_logger

logger = get_logger("request")

# 最大响应体记录大小（10KB）
MAX_RESPONSE_BODY_SIZE = 10 * 1024

# 不记录日志的路径（静态资源、文档等）
SKIP_PATHS = [
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
    "/",
]


class RequestLogMiddleware(BaseHTTPMiddleware):
    """
    HTTP 请求日志中间件

    功能：
    1. 记录请求信息：方法、路径、查询参数、请求体、客户端IP
    2. 记录响应信息：状态码、响应体、耗时
    3. 跳过静态路径和 WebSocket 请求的日志记录
    4. 大响应体截断处理（>10KB）
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并记录日志"""

        # 获取请求路径
        path = request.url.path

        # 跳过静态路径
        if path in SKIP_PATHS:
            return await call_next(request)

        # 跳过 WebSocket 请求
        if path.startswith("/ws"):
            return await call_next(request)

        # 记录开始时间
        start_time = time.perf_counter()

        # 获取客户端 IP
        client_ip = self._get_client_ip(request)

        # 获取查询参数
        query_params = dict(request.query_params) if request.query_params else None

        # 获取请求体
        request_body = await self._get_request_body(request)

        # 记录请求日志
        log_data = {
            "type": "request",
            "method": request.method,
            "path": path,
            "client_ip": client_ip,
        }
        if query_params:
            log_data["query_params"] = query_params
        if request_body:
            log_data["body"] = request_body

        logger.info(f"HTTP Request: {json.dumps(log_data, ensure_ascii=False)}")

        # 调用下一个中间件/路由处理器
        response = await call_next(request)

        # 计算耗时
        elapsed_time = time.perf_counter() - start_time

        # 获取响应体
        response_body = await self._get_response_body(response)

        # 记录响应日志
        response_log = {
            "type": "response",
            "method": request.method,
            "path": path,
            "status_code": response.status_code,
            "elapsed_ms": round(elapsed_time * 1000, 2),
        }
        if response_body:
            response_log["body"] = response_body

        # 根据状态码选择日志级别
        if response.status_code >= 500:
            logger.error(f"HTTP Response: {json.dumps(response_log, ensure_ascii=False)}")
        elif response.status_code >= 400:
            logger.warning(f"HTTP Response: {json.dumps(response_log, ensure_ascii=False)}")
        else:
            logger.info(f"HTTP Response: {json.dumps(response_log, ensure_ascii=False)}")

        return response

    def _get_client_ip(self, request: Request) -> str:
        """
        获取客户端真实 IP

        优先从代理头获取，否则使用直接连接 IP
        """
        # 尝试从代理头获取
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For 可能包含多个 IP，取第一个
            return forwarded_for.split(",")[0].strip()

        # 尝试从 X-Real-IP 获取
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # 使用直接连接的客户端 IP
        if request.client:
            return request.client.host

        return "unknown"

    async def _get_request_body(self, request: Request) -> Optional[str]:
        """
        获取请求体内容

        Returns:
            请求体字符串，如果为空或无法读取则返回 None
        """
        try:
            # 读取请求体
            body = await request.body()

            if not body:
                return None

            # 重置请求体以便后续处理器可以使用
            async def receive() -> Message:
                return {"type": "http.request", "body": body}

            request._receive = receive

            # 尝试解析为 JSON
            try:
                body_str = body.decode("utf-8")
                # 尝试解析并重新序列化，确保格式正确
                parsed = json.loads(body_str)
                return json.dumps(parsed, ensure_ascii=False)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # 非 JSON 或二进制数据，返回摘要
                return f"<binary data: {len(body)} bytes>"

        except Exception as e:
            logger.debug(f"Failed to read request body: {e}")
            return None

    async def _get_response_body(self, response: Response) -> Optional[str]:
        """
        获取响应体内容

        处理 StreamingResponse 和大响应体截断

        Returns:
            响应体字符串，如果为空或无法读取则返回 None
        """
        # StreamingResponse 不读取响应体
        if isinstance(response, StreamingResponse):
            return "<streaming response>"

        try:
            # 读取响应体
            body_chunks = []
            async for chunk in response.body_iterator:
                body_chunks.append(chunk)

            # 合并响应体
            body = b"".join(body_chunks)

            # 重置 body_iterator 以便后续使用
            response.body_iterator = self._body_iterator_from_bytes(body)

            if not body:
                return None

            # 检查响应体大小
            if len(body) > MAX_RESPONSE_BODY_SIZE:
                size_kb = len(body) // 1024
                return f"{{{{truncated, size={size_kb}kb}}}}"

            # 尝试解析为 JSON
            try:
                body_str = body.decode("utf-8")
                parsed = json.loads(body_str)
                return json.dumps(parsed, ensure_ascii=False)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # 非 JSON 或二进制数据，返回摘要
                return f"<binary data: {len(body)} bytes>"

        except Exception as e:
            logger.debug(f"Failed to read response body: {e}")
            return None

    async def _body_iterator_from_bytes(self, body: bytes):
        """从字节数据创建 body_iterator"""
        yield body