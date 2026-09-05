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
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles

from app.config import settings
from utils.redis import RedisClient
from utils.background_tasks import spawn_background_task
from core.router import router as core_router
from core.websocket.router import router as websocket_router
from core.env_machine.api import router as env_machine_router
from core.env_machine.lock_manager import LockAcquireError
from core.config_template.public_api import router as public_config_template_router
from utils.auth_middleware import AuthPermissionMiddleware
from utils.logging_config import setup_logging
from utils.request_log_middleware import RequestLogMiddleware

# 全局OAuth2方案，用于Swagger显示小锁图标
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/core/auth/login/oauth2", auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 调度器领导权由 Redis 租约决定（core/scheduler/service.py LEASE_KEY）：
    # - 单实例：必然抢到租约，行为与原"单进程启动调度器"一致
    # - 多 worker / 多副本：只有持锁实例启动定时任务，其余实例为纯 API 服务
    from core.scheduler.service import scheduler_service
    is_leader = await scheduler_service.init_scheduler()

    # 启动时
    # ========== 日志系统初始化 ==========
    setup_logging()
    # ========== 日志系统初始化结束 ==========

    # ========== 执行机管理模块启动初始化 ==========
    from core.env_machine.pool_manager import EnvPoolManager
    from app.database import AsyncSessionLocal

    # 1. 加载机器池到 Redis（所有 worker 执行，保证 Redis 缓存初始化）
    async with AsyncSessionLocal() as db:
        await EnvPoolManager.load_machine_pool(db)

    # 2. 启动后台任务：延迟10秒后主动访问设备验证状态（仅领导权实例执行）
    if is_leader:
        from core.env_machine.scheduler import reload_machine_status_after_restart
        spawn_background_task(reload_machine_status_after_restart(), name="reload-machine-status")
    # ========== 执行机管理模块启动初始化结束 ==========

    # ========== 权限缓存失效监听（所有 worker，保证多进程权限一致） ==========
    from utils.permission import start_permission_cache_listener, stop_permission_cache_listener
    start_permission_cache_listener()
    # ========== 权限缓存失效监听结束 ==========

    # ========== 命令任务对账（所有实例） ==========
    # 后台命令/脚本任务随进程重启静默丢失，超过 1 天仍 running 的记录必然已死，
    # 启动时统一标记为 failed，避免任务记录永久 running。
    # UPDATE 带状态条件，幂等，多实例重复执行无副作用。
    from sqlalchemy import update as sa_update
    from core.config_template.command_task_model import CommandTask

    async with AsyncSessionLocal() as db:
        cutoff = datetime.now() - timedelta(days=1)
        result = await db.execute(
            sa_update(CommandTask)
            .where(
                CommandTask.status == "running",
                CommandTask.sys_create_datetime < cutoff,
            )
            .values(status="failed", finished_datetime=datetime.now())
        )
        await db.commit()
        if result.rowcount:
            logging.getLogger(__name__).warning(
                f"启动对账：{result.rowcount} 条超过 1 天仍 running 的命令任务已标记为 failed"
            )
    # ========== 命令任务对账结束 ==========

    # ========== 测试报告模块启动初始化 ==========
    # 创建 HTML 存储目录（如果不存在）
    html_path = Path(settings.TEST_REPORT_HTML_PATH)
    html_path.mkdir(parents=True, exist_ok=True)
    # ========== 测试报告模块启动初始化结束 ==========

    # ========== 导出任务模块启动初始化（所有实例） ==========
    # 导出临时目录所有实例都可能写入（export/create 在任意 worker 均可服务）；
    # 周期清理已迁移为调度器内置 job（export_files_cleanup，仅领导权实例执行）
    from utils.excel import TEMP_EXPORTS_DIR
    TEMP_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    # ========== 导出任务模块启动初始化结束 ==========

    yield

    # 关闭时停止调度器（未持租约的实例为空操作）
    await scheduler_service.shutdown()
    await stop_permission_cache_listener()
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


# 机器池锁竞争（LockAcquireError）是瞬时过载而非服务器错误，返回 503 让调用方稍后重试
@app.exception_handler(LockAcquireError)
async def lock_acquire_error_handler(request, exc: LockAcquireError):
    return JSONResponse(status_code=503, content={"detail": exc.message})

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
