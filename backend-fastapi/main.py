#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2025-12-31
@File: main.py
@Desc: 应用生命周期管理 - # 启动时
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles

from app.config import settings
from utils.redis import RedisClient
from core.router import router as core_router
from core.websocket.router import router as websocket_router
from core.env_machine.api import router as env_machine_router
from core.ai_assistant.public_api import router as ai_public_router
from utils.auth_middleware import AuthMiddleware
from utils.logging_config import setup_logging
from utils.request_log_middleware import RequestLogMiddleware

# 全局OAuth2方案，用于Swagger显示小锁图标
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/core/auth/login/oauth2", auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    # ========== 日志系统初始化 ==========
    setup_logging()
    # ========== 日志系统初始化结束 ==========

    # ========== 调度器初始化 ==========
    from core.scheduler.service import scheduler_service
    await scheduler_service.init_scheduler()
    # ========== 调度器初始化结束 ==========

    # ========== 执行机管理模块启动初始化 ==========
    from core.env_machine.scheduler import reset_using_machines, reload_machine_status_after_restart
    from core.env_machine.pool_manager import EnvPoolManager
    from app.database import AsyncSessionLocal

    # 1. 重置 using 状态的机器为 online（服务重启后任务丢失）
    await reset_using_machines()

    # 2. 加载机器池到 Redis（初始加载，状态会在后续重载中更新）
    async with AsyncSessionLocal() as db:
        await EnvPoolManager.load_machine_pool(db)

    # 3. 启动后台任务：延迟10秒后主动访问设备验证状态
    asyncio.create_task(reload_machine_status_after_restart())
    # ========== 执行机管理模块启动初始化结束 ==========

    # ========== 测试报告模块启动初始化 ==========
    # 创建 HTML 存储目录（如果不存在）
    html_path = Path(settings.TEST_REPORT_HTML_PATH)
    html_path.mkdir(parents=True, exist_ok=True)
    # ========== 测试报告模块启动初始化结束 ==========

    yield

    # 关闭时
    await scheduler_service.shutdown()
    await RedisClient.close()

app = FastAPI(
    title=settings.APP_NAME,
    description="企业级后台管理系统 API",
    version="1.0.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": True,
    },
)

# 添加全局认证中间件（白名单内的路由无需认证）
app.add_middleware(AuthMiddleware)

# 添加请求日志中间件
app.add_middleware(RequestLogMiddleware)

# 注册路由（带全局OAuth2依赖，用于Swagger显示小锁图标）
app.include_router(core_router, prefix="/api/core", dependencies=[Depends(oauth2_scheme)])
# WebSocket路由（不需要OAuth2依赖，WebSocket自己处理认证）
app.include_router(websocket_router)
# 执行机管理路由（公开接口，供外部 worker 调用，无需认证）
app.include_router(env_machine_router)
# AI助手公开接口（供外部系统发送消息和接收回调，无需认证）
app.include_router(ai_public_router, prefix="/api")

# 测试报告 HTML 静态文件（公开访问，无需认证）
html_path = Path(settings.TEST_REPORT_HTML_PATH)
if html_path.exists():
    app.mount("/test-reports-html", StaticFiles(directory=str(html_path)), name="test-reports")


@app.get("/", tags=["根路径"])
async def root():
    """API根路径"""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "env": settings.ENV,
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG
    )
