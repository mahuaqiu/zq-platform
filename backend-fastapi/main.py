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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles

from app.config import settings
from utils.redis import RedisClient
from core.router import router as core_router
from core.websocket.router import router as websocket_router
from core.env_machine.api import router as env_machine_router
from core.config_template.public_api import router as public_config_template_router
from utils.auth_middleware import AuthPermissionMiddleware
from utils.logging_config import setup_logging
from utils.request_log_middleware import RequestLogMiddleware

# 全局OAuth2方案，用于Swagger显示小锁图标
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/core/auth/login/oauth2", auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 判断是否为主 worker（只有主 worker 启动调度器）
    # gunicorn 多 worker 模式下，通过环境变量判断
    # - 单进程模式 (uvicorn/python main.py)：无 GUNICORN_WORKER_ID，启动调度器
    # - gunicorn 多 worker 模式：只有 worker_id=0 启动调度器
    import os
    worker_id = os.environ.get("GUNICORN_WORKER_ID", None)
    is_main_worker = worker_id is None or worker_id == "0"

    # 启动时
    # ========== 日志系统初始化 ==========
    setup_logging()
    # ========== 日志系统初始化结束 ==========

    # ========== 调度器初始化（仅主 worker） ==========
    if is_main_worker:
        from core.scheduler.service import scheduler_service
        await scheduler_service.init_scheduler()
    # ========== 调度器初始化结束 ==========

    # ========== 执行机管理模块启动初始化 ==========
    from core.env_machine.pool_manager import EnvPoolManager
    from app.database import AsyncSessionLocal

    # 1. 加载机器池到 Redis（所有 worker 执行，保证 Redis 缓存初始化）
    async with AsyncSessionLocal() as db:
        await EnvPoolManager.load_machine_pool(db)

    # 2. 启动后台任务：延迟10秒后主动访问设备验证状态（仅主 worker 执行）
    if is_main_worker:
        from core.env_machine.scheduler import reload_machine_status_after_restart
        asyncio.create_task(reload_machine_status_after_restart())
    # ========== 执行机管理模块启动初始化结束 ==========

    # ========== 测试报告模块启动初始化 ==========
    # 创建 HTML 存储目录（如果不存在）
    html_path = Path(settings.TEST_REPORT_HTML_PATH)
    html_path.mkdir(parents=True, exist_ok=True)
    # ========== 测试报告模块启动初始化结束 ==========

    # ========== 导出任务模块启动初始化（仅主 worker） ==========
    if is_main_worker:
        from utils.excel import TEMP_EXPORTS_DIR
        from core.performance_monitor.service import ExportTaskService

        # 1. 创建导出临时目录
        TEMP_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

        # 2. 注册定时清理任务（每小时执行）
        async def cleanup_export_loop():
            while True:
                await asyncio.sleep(3600)  # 每小时
                try:
                    await ExportTaskService.cleanup_export_files()
                except Exception as e:
                    import logging
                    logging.error(f"清理导出文件失败: {e}")

        asyncio.create_task(cleanup_export_loop())
    # ========== 导出任务模块启动初始化结束 ==========

    yield

    # 关闭时（仅主 worker 关闭调度器）
    if is_main_worker:
        from core.scheduler.service import scheduler_service
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

# CORS 跨域配置
cors_origins = settings.CORS_ORIGINS
if cors_origins == "*":
    allow_origins = ["*"]
else:
    allow_origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加全局认证+鉴权中间件（白名单内的路由无需认证，权限检查基于Permission表）
app.add_middleware(AuthPermissionMiddleware)

# 添加请求日志中间件
app.add_middleware(RequestLogMiddleware)

# 注册路由（带全局OAuth2依赖，用于Swagger显示小锁图标）
app.include_router(core_router, prefix="/api/core", dependencies=[Depends(oauth2_scheme)])
# WebSocket路由（不需要OAuth2依赖，WebSocket自己处理认证）
app.include_router(websocket_router)
# 执行机管理路由（公开接口，供外部 worker 调用，无需认证）
app.include_router(env_machine_router)
# 外部脚本下发接口不挂载全局 OAuth2 依赖
app.include_router(public_config_template_router)

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
