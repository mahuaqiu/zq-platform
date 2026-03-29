# 日志系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用 loguru 为 zq-platform 后端实现持久化日志系统，记录请求参数、返回结果及核心业务操作。

**Architecture:** 使用 loguru 替换 Python 标准 logging，通过 RotatingFileHandler 实现日志旋转，通过中间件记录请求/响应日志，改造核心业务模块使用统一日志接口。

**Tech Stack:** FastAPI, loguru, Python

---

## 文件结构

| 操作 | 文件路径 | 说明 |
|------|----------|------|
| Create | `backend-fastapi/utils/logging_config.py` | loguru 配置模块 |
| Create | `backend-fastapi/utils/request_log_middleware.py` | 请求日志中间件 |
| Modify | `backend-fastapi/requirements.txt` | 添加 loguru 依赖 |
| Modify | `backend-fastapi/main.py` | 初始化日志，添加中间件 |
| Modify | `backend-fastapi/scheduler/service.py` | 改造日志调用 |
| Modify | `backend-fastapi/utils/auth_middleware.py` | 改造日志调用 |
| Modify | `backend-fastapi/core/auth/api.py` | 改造日志调用 |
| Modify | `backend-fastapi/core/user/service.py` | 改造日志调用 |
| Modify | `backend-fastapi/core/env_machine/pool_manager.py` | 改造日志调用 |
| Modify | `backend-fastapi/core/websocket/consumers/*.py` | 改造日志调用 |

---

### Task 1: 安装 loguru 依赖

**Files:**
- Modify: `backend-fastapi/requirements.txt`

- [ ] **Step 1: 添加 loguru 到 requirements.txt**

在 `requirements.txt` 末尾添加：
```
loguru>=0.7.0
```

- [ ] **Step 2: 安装依赖**

Run: `cd backend-fastapi && pip install loguru`
Expected: Successfully installed loguru

- [ ] **Step 3: 验证安装**

Run: `python -c "from loguru import logger; print('loguru ok')"`
Expected: 输出 "loguru ok"

- [ ] **Step 4: Commit**

```bash
git add backend-fastapi/requirements.txt
git commit -m "feat: 添加 loguru 日志依赖"
```

---

### Task 2: 创建日志配置模块

**Files:**
- Create: `backend-fastapi/utils/logging_config.py`

- [ ] **Step 1: 创建日志配置模块**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2026-03-29
@File: logging_config.py
@Desc: Loguru 日志配置模块
"""
import sys
import os
from loguru import logger

# 日志配置参数
LOG_DIR = "logs"
LOG_FILE = "app.log"
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
RETENTION_COUNT = 5  # 5 个文件，总计 100MB
LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"


def setup_logging():
    """
    初始化日志配置，应用启动时调用

    配置内容：
    - 文件日志：RotatingFileHandler，自动旋转
    - 控制台日志：stderr 输出（开发环境）
    """
    # 确保日志目录存在
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    # 移除默认 handler
    logger.remove()

    # 添加文件 handler（旋转）
    logger.add(
        os.path.join(LOG_DIR, LOG_FILE),
        format=LOG_FORMAT,
        rotation=MAX_FILE_SIZE,  # 文件大小达到阈值时旋转
        retention=RETENTION_COUNT,  # 保留文件数量
        compression="zip",  # 压缩旧日志文件
        level="DEBUG",
        encoding="utf-8",
        enqueue=True,  # 异步写入，避免阻塞
    )

    # 添加控制台 handler（开发环境）
    logger.add(
        sys.stderr,
        format=LOG_FORMAT,
        level="DEBUG",
        colorize=True,
    )

    logger.info("日志系统初始化完成")


def get_logger(name: str = None):
    """
    获取日志实例

    Args:
        name: 模块名称，用于标识日志来源

    Returns:
        logger 实例

    使用方式：
        from utils.logging_config import get_logger
        log = get_logger(__name__)
        log.info("操作成功")
    """
    if name:
        return logger.bind(name=name)
    return logger
```

- [ ] **Step 2: 验证模块导入**

Run: `cd backend-fastapi && python -c "from utils.logging_config import setup_logging, get_logger; setup_logging(); log = get_logger('test'); log.info('test'); print('ok')"`
Expected: 输出日志信息并创建 `logs/app.log` 文件

- [ ] **Step 3: Commit**

```bash
git add backend-fastapi/utils/logging_config.py
git commit -m "feat: 创建 loguru 日志配置模块"
```

---

### Task 3: 创建请求日志中间件

**Files:**
- Create: `backend-fastapi/utils/request_log_middleware.py`

- [ ] **Step 1: 创建请求日志中间件**

```python
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
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse, JSONResponse

from utils.logging_config import get_logger

logger = get_logger("request")

# 不记录日志的路径（静态资源、文档等）
SKIP_PATHS = [
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
    "/",
]

# 响应体截断阈值（10KB）
MAX_RESPONSE_BODY_SIZE = 10 * 1024


class RequestLogMiddleware(BaseHTTPMiddleware):
    """
    HTTP 请求日志中间件

    记录：
    - 请求信息：方法、路径、参数、客户端 IP
    - 响应信息：状态码、响应体、耗时
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 跳过静态资源和文档路径
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        # 跳过 WebSocket 请求
        if request.url.path.startswith("/ws"):
            return await call_next(request)

        # 记录请求开始时间
        start_time = time.time()

        # 获取客户端 IP
        client_ip = self._get_client_ip(request)

        # 获取请求参数
        request_params = await self._get_request_params(request)

        # 记录请求日志
        logger.info(
            f"请求开始 | {request.method} | {request.url.path} | "
            f"IP: {client_ip} | 参数: {request_params}"
        )

        # 调用下一个处理器
        try:
            response = await call_next(request)
        except Exception as e:
            # 记录异常
            elapsed_time = (time.time() - start_time) * 1000
            logger.error(
                f"请求异常 | {request.method} | {request.url.path} | "
                f"耗时: {elapsed_time:.2f}ms | 异常: {str(e)}"
            )
            raise

        # 记录请求结束时间
        elapsed_time = (time.time() - start_time) * 1000

        # 获取响应体
        response_body = await self._get_response_body(response)

        # 记录响应日志
        logger.info(
            f"请求结束 | {request.method} | {request.url.path} | "
            f"状态: {response.status_code} | 耗时: {elapsed_time:.2f}ms | "
            f"响应: {response_body}"
        )

        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端 IP"""
        # 优先从 X-Forwarded-For 获取（代理场景）
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # 从 X-Real-IP 获取
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # 直接连接
        if request.client:
            return request.client.host

        return "unknown"

    async def _get_request_params(self, request: Request) -> str:
        """获取请求参数（Query + Body）"""
        params = {}

        # Query 参数
        if request.query_params:
            params["query"] = dict(request.query_params)

        # Body 参数（仅对 POST/PUT/PATCH）
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                # 读取 body
                body = await request.body()
                if body:
                    try:
                        params["body"] = json.loads(body.decode("utf-8"))
                    except json.JSONDecodeError:
                        # 非 JSON 格式，直接记录原始内容
                        params["body"] = body.decode("utf-8", errors="ignore")[:500]

                # 重新设置 body（因为已被读取）
                async def receive():
                    return {"type": "http.request", "body": body}
                request._receive = receive
            except Exception:
                params["body"] = "读取失败"

        return json.dumps(params, ensure_ascii=False) if params else "无"

    async def _get_response_body(self, response: Response) -> str:
        """获取响应体"""
        try:
            # StreamingResponse 不适合读取完整内容
            if isinstance(response, StreamingResponse):
                return "{streaming response}"

            # 读取响应体
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            # 重新设置 body_iterator
            async def body_iterator():
                yield body
            response.body_iterator = body_iterator()

            # 截断大响应体
            if len(body) > MAX_RESPONSE_BODY_SIZE:
                size_kb = len(body) / 1024
                return f"{{truncated, size={size_kb:.1f}kb}}"

            # 尝试解析 JSON
            try:
                return json.dumps(json.loads(body.decode("utf-8")), ensure_ascii=False)
            except json.JSONDecodeError:
                return body.decode("utf-8", errors="ignore")[:500]

        except Exception as e:
            return f"读取失败: {str(e)}"
```

- [ ] **Step 2: 验证中间件导入**

Run: `cd backend-fastapi && python -c "from utils.request_log_middleware import RequestLogMiddleware; print('ok')"`
Expected: 输出 "ok"

- [ ] **Step 3: Commit**

```bash
git add backend-fastapi/utils/request_log_middleware.py
git commit -m "feat: 创建 HTTP 请求日志中间件"
```

---

### Task 4: 在 main.py 初始化日志配置并添加中间件

**Files:**
- Modify: `backend-fastapi/main.py`

- [ ] **Step 1: 在 main.py 添加日志初始化和中间件**

修改 `main.py`：

1. 在导入部分添加：
```python
from utils.logging_config import setup_logging
from utils.request_log_middleware import RequestLogMiddleware
```

2. 在 `lifespan` 函数开头添加：
```python
    # ========== 日志系统初始化 ==========
    setup_logging()
    # ========== 日志系统初始化结束 ==========
```

3. 在 `app.add_middleware(AuthMiddleware)` 之后添加：
```python
# 添加请求日志中间件
app.add_middleware(RequestLogMiddleware)
```

完整修改后的 `main.py` 开头部分：
```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2025-12-31
@File: main.py
@Desc: 应用生命周期管理 - # 启动时
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.security import OAuth2PasswordBearer

from app.config import settings
from utils.redis import RedisClient
from utils.logging_config import setup_logging
from utils.request_log_middleware import RequestLogMiddleware
from core.router import router as core_router
from core.websocket.router import router as websocket_router
from utils.auth_middleware import AuthMiddleware
```

`lifespan` 函数开头：
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    # ========== 日志系统初始化 ==========
    setup_logging()
    # ========== 日志系统初始化结束 ==========
    ...
```

中间件添加（在 `AuthMiddleware` 之后）：
```python
# 添加全局认证中间件（白名单内的路由无需认证）
app.add_middleware(AuthMiddleware)
# 添加请求日志中间件
app.add_middleware(RequestLogMiddleware)
```

- [ ] **Step 2: 启动应用验证**

Run: `cd backend-fastapi && python main.py`
Expected: 应用启动，控制台输出 "日志系统初始化完成"，`logs/app.log` 文件创建

- [ ] **Step 3: 测试请求日志**

Run: 使用 curl 或浏览器访问 `http://localhost:8000/`
Expected: 控制台和日志文件记录请求信息

- [ ] **Step 4: Commit**

```bash
git add backend-fastapi/main.py
git commit -m "feat: 在 main.py 初始化日志系统并添加请求日志中间件"
```

---

### Task 5: 改造 scheduler/service.py 的日志

**Files:**
- Modify: `backend-fastapi/scheduler/service.py`

- [ ] **Step 1: 替换 logging 为 loguru**

修改 `scheduler/service.py`：

1. 替换导入：
```python
# 移除
import logging
logger = logging.getLogger(__name__)

# 替换为
from utils.logging_config import get_logger
logger = get_logger("scheduler")
```

2. 日志调用保持不变（loguru API 兼容）

- [ ] **Step 2: 验证模块**

Run: `cd backend-fastapi && python -c "from scheduler.service import scheduler_service; print('ok')"`
Expected: 输出 "ok"

- [ ] **Step 3: Commit**

```bash
git add backend-fastapi/scheduler/service.py
git commit -m "feat: 改造 scheduler 日志为 loguru"
```

---

### Task 6: 改造 auth_middleware.py 的日志

**Files:**
- Modify: `backend-fastapi/utils/auth_middleware.py`

- [ ] **Step 1: 添加认证失败日志**

修改 `utils/auth_middleware.py`：

1. 在文件开头添加导入：
```python
from utils.logging_config import get_logger
logger = get_logger("auth")
```

2. 在 `AuthMiddleware.dispatch` 方法中，Token 验证失败处添加日志：

在 `if not token:` 之后添加：
```python
            logger.warning(f"认证失败 | 路径: {path} | 原因: 未提供认证凭据 | IP: {self._get_client_ip(request)}")
```

在 `if not payload:` 之后添加：
```python
            logger.warning(f"认证失败 | 路径: {path} | 原因: 无效或过期的Token | IP: {self._get_client_ip(request)}")
```

3. 添加 `_get_client_ip` 方法到 `AuthMiddleware` 类：
```python
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端 IP"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        if request.client:
            return request.client.host
        return "unknown"
```

- [ ] **Step 2: 验证模块**

Run: `cd backend-fastapi && python -c "from utils.auth_middleware import AuthMiddleware; print('ok')"`
Expected: 输出 "ok"

- [ ] **Step 3: Commit**

```bash
git add backend-fastapi/utils/auth_middleware.py
git commit -m "feat: 改造 auth_middleware 日志为 loguru"
```

---

### Task 7: 改造 core/auth/api.py 的日志

**Files:**
- Modify: `backend-fastapi/core/auth/api.py`

- [ ] **Step 1: 添加登录日志**

修改 `core/auth/api.py`：

1. 在文件开头添加导入：
```python
from utils.logging_config import get_logger
logger = get_logger("auth_api")
```

2. 在 `login` 函数登录成功后（`return TokenResponse` 之前）添加：
```python
    logger.info(f"登录成功 | 用户: {user.username} | IP: {client_info['login_ip']}")
```

3. 在 `logout` 函数中添加：
```python
    logger.info(f"用户登出 | 用户ID: {user_id}")
```

4. 在 `refresh_token` 函数成功后（`return TokenResponse` 之前）添加：
```python
    logger.info(f"Token刷新成功 | 用户: {user.username} | IP: {get_client_ip(request)}")
```

并添加获取 IP 的辅助函数：
```python
def get_client_ip(request: Request) -> str:
    """获取客户端 IP"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    if request.client:
        return request.client.host
    return "unknown"
```

- [ ] **Step 2: 验证模块**

Run: `cd backend-fastapi && python -c "from core.auth.api import router; print('ok')"`
Expected: 输出 "ok"

- [ ] **Step 3: Commit**

```bash
git add backend-fastapi/core/auth/api.py
git commit -m "feat: 改造 auth API 日志为 loguru"
```

---

### Task 8: 改造 core/user/service.py 的日志

**Files:**
- Modify: `backend-fastapi/core/user/service.py`

- [ ] **Step 1: 添加用户操作日志**

修改 `core/user/service.py`：

1. 在文件开头添加导入：
```python
from utils.logging_config import get_logger
logger = get_logger("user_service")
```

2. 在用户创建成功处添加：
```python
logger.info(f"用户创建 | 用户名: {user.username} | 创建者ID: {creator_id}")
```

3. 在用户更新成功处添加：
```python
logger.info(f"用户更新 | 用户ID: {user_id} | 更新者ID: {modifier_id}")
```

4. 在用户删除成功处添加：
```python
logger.info(f"用户删除 | 用户ID: {user_id} | 删除者ID: {operator_id}")
```

- [ ] **Step 2: 验证模块**

Run: `cd backend-fastapi && python -c "from core.user.service import UserService; print('ok')"`
Expected: 输出 "ok"

- [ ] **Step 3: Commit**

```bash
git add backend-fastapi/core/user/service.py
git commit -m "feat: 改造 user service 日志为 loguru"
```

---

### Task 9: 改造 core/env_machine/pool_manager.py 的日志

**Files:**
- Modify: `backend-fastapi/core/env_machine/pool_manager.py`

- [ ] **Step 1: 添加执行机池管理日志**

修改 `core/env_machine/pool_manager.py`：

1. 在文件开头添加导入：
```python
from utils.logging_config import get_logger
logger = get_logger("env_machine")
```

2. 在机器加载成功处添加：
```python
logger.info(f"执行机池加载完成 | 机器数: {len(machines)}")
```

3. 在机器状态变更处添加：
```python
logger.info(f"执行机状态变更 | 机器ID: {machine_id} | 状态: {old_status} -> {new_status}")
```

4. 在机器分配处添加：
```python
logger.info(f"执行机分配 | 机器ID: {machine_id} | 任务ID: {task_id}")
```

- [ ] **Step 2: 验证模块**

Run: `cd backend-fastapi && python -c "from core.env_machine.pool_manager import EnvPoolManager; print('ok')"`
Expected: 输出 "ok"

- [ ] **Step 3: Commit**

```bash
git add backend-fastapi/core/env_machine/pool_manager.py
git commit -m "feat: 改造 env_machine pool_manager 日志为 loguru"
```

---

### Task 10: 改造 WebSocket consumers 的日志

**Files:**
- Modify: `backend-fastapi/core/websocket/consumers/base.py`
- Modify: `backend-fastapi/core/websocket/consumers/database_monitor_consumer.py`
- Modify: `backend-fastapi/core/websocket/consumers/redis_monitor_consumer.py`
- Modify: `backend-fastapi/core/websocket/consumers/server_monitor_consumer.py`

- [ ] **Step 1: 改造 base.py 添加连接日志**

修改 `core/websocket/consumers/base.py`：

1. 在文件开头添加导入：
```python
from utils.logging_config import get_logger
logger = get_logger("websocket")
```

2. 在连接建立处添加：
```python
logger.info(f"WebSocket连接建立 | 路径: {path} | 用户ID: {user_id}")
```

3. 在连接断开处添加：
```python
logger.info(f"WebSocket连接断开 | 路径: {path} | 用户ID: {user_id}")
```

4. 在异常处理处添加：
```python
logger.error(f"WebSocket异常 | 路径: {path} | 异常: {str(e)}")
```

- [ ] **Step 2: 改造各 consumer 文件**

各 consumer 文件（database_monitor_consumer.py、redis_monitor_consumer.py、server_monitor_consumer.py）：

1. 添加导入：
```python
from utils.logging_config import get_logger
logger = get_logger("websocket.monitor")
```

2. 在关键操作处添加日志（如数据推送、监控开始/停止）

- [ ] **Step 3: 验证模块**

Run: `cd backend-fastapi && python -c "from core.websocket.consumers.base import BaseConsumer; print('ok')"`
Expected: 输出 "ok"

- [ ] **Step 4: Commit**

```bash
git add backend-fastapi/core/websocket/consumers/
git commit -m "feat: 改造 WebSocket consumers 日志为 loguru"
```

---

### Task 11: 综合验证

- [ ] **Step 1: 启动应用**

Run: `cd backend-fastapi && python main.py`
Expected: 应用正常启动，日志目录和文件创建

- [ ] **Step 2: 测试登录请求**

Run: 使用 POST 请求 `/api/core/login` 进行登录测试
Expected: 日志文件记录完整的请求参数和响应结果

- [ ] **Step 3: 测试认证失败**

Run: 不带 Token 访问需要认证的接口
Expected: 日志记录 "认证失败" 信息

- [ ] **Step 4: 验证日志文件**

Run: 查看 `logs/app.log` 内容
Expected: 包含启动日志、请求日志、业务操作日志

- [ ] **Step 5: Final Commit**

```bash
git add -A
git commit -m "feat: 日志系统实现完成"
```