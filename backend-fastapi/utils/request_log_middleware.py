#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
HTTP 请求日志中间件
"""
import time
import json
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message
from starlette.responses import StreamingResponse

from utils.logging_config import get_logger

logger = get_logger("http")

# 不记录日志的路径
SKIP_PATHS = [
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
    "/",
]


class RequestLogMiddleware(BaseHTTPMiddleware):
    """HTTP 请求日志中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # 跳过静态路径和 WebSocket
        if path in SKIP_PATHS or path.startswith("/ws") or path.startswith("/test-reports-html"):
            return await call_next(request)

        start_time = time.perf_counter()

        # 获取请求体
        request_body = await self._get_request_body(request)

        try:
            response = await call_next(request)
        except Exception as e:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(f"{request.method} {path} | {elapsed_ms}ms | ERROR: {e}")
            raise

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # 获取响应体
        response_body = await self._get_response_body(response)

        # 构建日志消息
        log_msg = f"{request.method} {path} | {response.status_code} | {elapsed_ms}ms"

        # 添加请求体（如果有）
        if request_body:
            log_msg += f" | req: {request_body}"

        # 添加响应体（如果有）
        if response_body:
            log_msg += f" | res: {response_body}"

        # 根据状态码选择日志级别
        if response.status_code >= 500:
            logger.error(log_msg)
        elif response.status_code >= 400:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        return response

    async def _get_request_body(self, request: Request) -> Optional[str]:
        """获取请求体内容"""
        try:
            body = await request.body()
            if not body:
                return None

            # 重置请求体
            async def receive() -> Message:
                return {"type": "http.request", "body": body}
            request._receive = receive

            # 尝试解析 JSON
            try:
                body_str = body.decode("utf-8")
                parsed = json.loads(body_str)
                # 如果内容太长，截断显示
                result = json.dumps(parsed, ensure_ascii=False)
                if len(result) > 500:
                    return f"{result[:500]}..."
                return result
            except (json.JSONDecodeError, UnicodeDecodeError):
                return f"<binary:{len(body)}B>"

        except Exception:
            return None

    async def _get_response_body(self, response: Response) -> Optional[str]:
        """获取响应体内容"""
        if isinstance(response, StreamingResponse):
            return "<stream>"

        try:
            body_chunks = []
            async for chunk in response.body_iterator:
                body_chunks.append(chunk)

            body = b"".join(body_chunks)
            response.body_iterator = self._body_iterator_from_bytes(body)

            if not body:
                return None

            # 如果响应体太大，截断
            if len(body) > 1000:
                return f"<{len(body)}B>"

            try:
                body_str = body.decode("utf-8")
                parsed = json.loads(body_str)
                result = json.dumps(parsed, ensure_ascii=False)
                if len(result) > 500:
                    return f"{result[:500]}..."
                return result
            except (json.JSONDecodeError, UnicodeDecodeError):
                return f"<binary:{len(body)}B>"

        except Exception:
            return None

    async def _body_iterator_from_bytes(self, body: bytes):
        """从字节数据创建 body_iterator"""
        yield body