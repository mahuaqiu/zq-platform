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
from core.router import router as core_router
from core.websocket.router import router as websocket_router
from core.env_machine.api import router as env_machine_router
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
    from scheduler.service import scheduler_service
    await scheduler_service.init_scheduler()
    # ========== 调度器初始化结束 ==========

    # ========== 执行机管理模块启动初始化 ==========
    from core.env_machine.scheduler import reset_using_machines, setup_env_machine_scheduler
    from core.env_machine.pool_manager import EnvPoolManager
    from app.database import AsyncSessionLocal

    # 1. 重置 using 状态的机器为 online（服务重启后任务丢失）
    await reset_using_machines()

    # 2. 加载机器池到 Redis
    async with AsyncSessionLocal() as db:
        await EnvPoolManager.load_machine_pool(db)

    # 3. 启动离线检测任务
    setup_env_machine_scheduler()
    # ========== 执行机管理模块启动初始化结束 ==========

    # ========== 测试报告模块启动初始化 ==========
    from core.test_report.scheduler import setup_test_report_scheduler
    setup_test_report_scheduler()
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
