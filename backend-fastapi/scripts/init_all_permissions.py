#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
权限初始化脚本
执行方式: cd backend-fastapi && python scripts/init_all_permissions.py

功能：初始化所有菜单的API权限（仅API权限，不包含按钮权限）

注意：超级管理员（is_superuser=True）自动拥有所有权限，无需额外分配
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select, delete, text
from app.database import AsyncSessionLocal
from core.permission.model import Permission
from core.menu.model import Menu

# HTTP方法映射
HTTP_METHOD_GET = 0
HTTP_METHOD_POST = 1
HTTP_METHOD_PUT = 2
HTTP_METHOD_DELETE = 3
HTTP_METHOD_PATCH = 4
HTTP_METHOD_ALL = 5

# 权限类型映射（仅API权限）
PERMISSION_TYPE_API = 1     # API权限


# ==================== 权限配置数据 ====================
# 格式：menu_id -> 权限列表（仅API权限）
ALL_PERMISSIONS = {
    # ==================== 设备管理 ====================
    # 设备列表
    "env-machine-list": [
        {"name": "查询设备列表", "code": "api:core:env:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/env", "http_method": HTTP_METHOD_GET, "description": "查询设备列表"},
        {"name": "新增设备", "code": "api:core:env:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/env", "http_method": HTTP_METHOD_POST, "description": "新增设备"},
        {"name": "更新设备", "code": "api:core:env:put", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/env/{machine_id}", "http_method": HTTP_METHOD_PUT, "description": "更新设备信息"},
        {"name": "删除设备", "code": "api:core:env:delete", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/env/{machine_id}", "http_method": HTTP_METHOD_DELETE, "description": "删除设备"},
        {"name": "批量删除设备", "code": "api:core:env:batch-delete:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/env/batch-delete", "http_method": HTTP_METHOD_POST, "description": "批量删除设备"},
        {"name": "批量导入虚拟设备", "code": "api:core:env:batch-import:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/env/batch-import-virtual", "http_method": HTTP_METHOD_POST, "description": "批量导入虚拟设备"},
        {"name": "批量执行命令", "code": "api:core:env:batch-command:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/env/batch-execute-command", "http_method": HTTP_METHOD_POST, "description": "批量执行命令"},
        {"name": "获取设备日志", "code": "api:core:env:logs:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/env/machine/{machine_id}/logs", "http_method": HTTP_METHOD_GET, "description": "获取设备日志"},
        {"name": "设备调试操作", "code": "api:core:env:debug:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/env/{machine_id}/debug-action", "http_method": HTTP_METHOD_POST, "description": "设备调试操作"},
        {"name": "下载导入模板", "code": "api:core:env:template:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/env/import-template", "http_method": HTTP_METHOD_GET, "description": "下载虚拟设备导入模板"},
    ],

    # 升级管理
    "env-machine-upgrade": [
        {"name": "获取升级配置", "code": "api:core:upgrade:config:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/env/upgrade/config", "http_method": HTTP_METHOD_GET, "description": "获取升级配置列表"},
        {"name": "更新升级配置", "code": "api:core:upgrade:config:put", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/env/upgrade/config/{config_id}", "http_method": HTTP_METHOD_PUT, "description": "更新升级配置"},
        {"name": "批量升级", "code": "api:core:upgrade:batch:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/env/upgrade/batch", "http_method": HTTP_METHOD_POST, "description": "批量升级设备"},
        {"name": "升级预览", "code": "api:core:upgrade:preview:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/env/upgrade/preview", "http_method": HTTP_METHOD_GET, "description": "获取升级预览"},
        {"name": "查询升级队列", "code": "api:core:upgrade:queue:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/env/upgrade/queue", "http_method": HTTP_METHOD_GET, "description": "查询升级队列"},
        {"name": "移除升级队列", "code": "api:core:upgrade:queue:delete", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/env/upgrade/queue/{queue_id}", "http_method": HTTP_METHOD_DELETE, "description": "移除升级队列项"},
    ],

    # 设备配置
    "env-machine-config": [
        {"name": "获取模板列表", "code": "api:core:config-template:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/config-template", "http_method": HTTP_METHOD_GET, "description": "获取配置模板列表"},
        {"name": "新建配置模板", "code": "api:core:config-template:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/config-template", "http_method": HTTP_METHOD_POST, "description": "新建配置模板"},
        {"name": "获取模板详情", "code": "api:core:config-template:detail:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/config-template/{template_id}", "http_method": HTTP_METHOD_GET, "description": "获取模板详情"},
        {"name": "编辑配置模板", "code": "api:core:config-template:put", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/config-template/{template_id}", "http_method": HTTP_METHOD_PUT, "description": "编辑配置模板"},
        {"name": "删除配置模板", "code": "api:core:config-template:delete", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/config-template/{template_id}", "http_method": HTTP_METHOD_DELETE, "description": "删除配置模板"},
        {"name": "配置下发", "code": "api:core:config-template:deploy:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/config-template/deploy", "http_method": HTTP_METHOD_POST, "description": "执行配置下发"},
        {"name": "配置预览", "code": "api:core:config-template:preview:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/config-template/preview", "http_method": HTTP_METHOD_GET, "description": "配置下发预览"},
    ],

    # 设备监控（worker调用的接口不加权限控制）
    "env-machine-monitor": [
        {"name": "获取看板统计", "code": "api:core:env:dashboard:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/env/dashboard/stats", "http_method": HTTP_METHOD_GET, "description": "获取设备监控看板统计"},
        {"name": "获取命名空间", "code": "api:core:env:namespaces:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/env/namespaces", "http_method": HTTP_METHOD_GET, "description": "获取所有机器分类"},
        # 申请设备、释放设备、保持使用 是worker调用的接口，不需要权限控制
    ],

    # ==================== 性能监控 ====================
    # 性能监控
    "performance-monitor-main": [
        {"name": "开始采集", "code": "api:performance:collect:start:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/collect/start", "http_method": HTTP_METHOD_POST, "description": "开始采集"},
        {"name": "停止采集", "code": "api:performance:collect:stop:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/collect/stop", "http_method": HTTP_METHOD_POST, "description": "停止采集"},
        {"name": "删除采集", "code": "api:performance:collect:delete", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/collect/{collect_id}", "http_method": HTTP_METHOD_DELETE, "description": "删除采集记录"},
        {"name": "采集状态", "code": "api:performance:collect:status:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/collect/status", "http_method": HTTP_METHOD_GET, "description": "获取采集状态"},
        {"name": "采集列表", "code": "api:performance:collect:list:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/collect/list", "http_method": HTTP_METHOD_GET, "description": "获取采集列表"},
        {"name": "创建版本", "code": "api:performance:version:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/version/create", "http_method": HTTP_METHOD_POST, "description": "创建版本"},
        {"name": "版本列表", "code": "api:performance:version:list:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/version/list", "http_method": HTTP_METHOD_GET, "description": "获取版本列表"},
        {"name": "创建标签", "code": "api:performance:tag:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/tag/create", "http_method": HTTP_METHOD_POST, "description": "创建标签"},
        {"name": "更新标签", "code": "api:performance:tag:put", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/tag/update", "http_method": HTTP_METHOD_PUT, "description": "更新标签"},
        {"name": "删除标签", "code": "api:performance:tag:delete", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/tag/delete", "http_method": HTTP_METHOD_DELETE, "description": "删除标签"},
        {"name": "创建标记", "code": "api:performance:marker:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/marker", "http_method": HTTP_METHOD_POST, "description": "创建标记"},
        {"name": "更新标记", "code": "api:performance:marker:put", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/marker/{marker_id}", "http_method": HTTP_METHOD_PUT, "description": "更新标记"},
        {"name": "删除标记", "code": "api:performance:marker:delete", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/marker/{marker_id}", "http_method": HTTP_METHOD_DELETE, "description": "删除标记"},
        {"name": "设置保护", "code": "api:performance:collect:protected:put", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/collect/{collect_id}/protected", "http_method": HTTP_METHOD_PUT, "description": "设置采集保护状态"},
        {"name": "获取进程列表", "code": "api:performance:processes:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/processes", "http_method": HTTP_METHOD_GET, "description": "获取设备进程列表"},
        {"name": "获取指标列表", "code": "api:performance:metrics:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/metrics/list", "http_method": HTTP_METHOD_GET, "description": "获取可用指标列表"},
    ],

    # 版本对比
    "performance-monitor-compare": [
        {"name": "版本对比", "code": "api:performance:compare:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/version/compare", "http_method": HTTP_METHOD_GET, "description": "获取版本对比数据"},
        {"name": "创建对比标签", "code": "api:performance:compare:tag:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/compare/tag", "http_method": HTTP_METHOD_POST, "description": "创建对比标签"},
        {"name": "获取对比标签", "code": "api:performance:compare:tags:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/compare/tags", "http_method": HTTP_METHOD_GET, "description": "获取对比标签列表"},
        {"name": "更新对比标签", "code": "api:performance:compare:tag:put", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/compare/tag/{tag_id}", "http_method": HTTP_METHOD_PUT, "description": "更新对比标签"},
        {"name": "删除对比标签", "code": "api:performance:compare:tag:delete", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/compare/tag/{tag_id}", "http_method": HTTP_METHOD_DELETE, "description": "删除对比标签"},
        {"name": "创建导出任务", "code": "api:performance:export:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/version/export/create", "http_method": HTTP_METHOD_POST, "description": "创建导出任务"},
        {"name": "导出任务状态", "code": "api:performance:export:status:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/version/export/status/{task_id}", "http_method": HTTP_METHOD_GET, "description": "查询导出任务状态"},
        {"name": "下载导出文件", "code": "api:performance:export:download:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/performance-monitor/version/export/download/{task_id}", "http_method": HTTP_METHOD_GET, "description": "下载导出文件"},
    ],

    # ==================== 系统管理 ====================
    # 用户管理
    "system-user": [
        {"name": "查询用户列表", "code": "api:core:user:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/user", "http_method": HTTP_METHOD_GET, "description": "查询用户列表"},
        {"name": "创建用户", "code": "api:core:user:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/user", "http_method": HTTP_METHOD_POST, "description": "创建用户"},
        {"name": "获取用户详情", "code": "api:core:user:detail:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/user/{user_id}", "http_method": HTTP_METHOD_GET, "description": "获取用户详情"},
        {"name": "更新用户", "code": "api:core:user:put", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/user/{user_id}", "http_method": HTTP_METHOD_PUT, "description": "更新用户"},
        {"name": "删除用户", "code": "api:core:user:delete", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/user/{user_id}", "http_method": HTTP_METHOD_DELETE, "description": "删除用户"},
        {"name": "批量删除用户", "code": "api:core:user:batch-delete:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/user/batch_delete", "http_method": HTTP_METHOD_POST, "description": "批量删除用户"},
        {"name": "批量更新状态", "code": "api:core:user:batch-status:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/user/batch/status", "http_method": HTTP_METHOD_POST, "description": "批量更新用户状态"},
        {"name": "重置密码", "code": "api:core:user:reset-password:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/user/{user_id}/reset-password", "http_method": HTTP_METHOD_POST, "description": "重置用户密码"},
        {"name": "导出用户Excel", "code": "api:core:user:export:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/user/export/excel", "http_method": HTTP_METHOD_GET, "description": "导出用户Excel"},
        {"name": "导入用户Excel", "code": "api:core:user:import:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/user/import/excel", "http_method": HTTP_METHOD_POST, "description": "导入用户Excel"},
    ],

    # 角色管理
    "system-role": [
        {"name": "查询角色列表", "code": "api:core:role:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/role", "http_method": HTTP_METHOD_GET, "description": "查询角色列表"},
        {"name": "创建角色", "code": "api:core:role:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/role", "http_method": HTTP_METHOD_POST, "description": "创建角色"},
        {"name": "获取角色详情", "code": "api:core:role:detail:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/role/{role_id}", "http_method": HTTP_METHOD_GET, "description": "获取角色详情"},
        {"name": "更新角色", "code": "api:core:role:put", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/role/{role_id}", "http_method": HTTP_METHOD_PUT, "description": "更新角色"},
        {"name": "删除角色", "code": "api:core:role:delete", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/role/{role_id}", "http_method": HTTP_METHOD_DELETE, "description": "删除角色"},
        {"name": "批量删除角色", "code": "api:core:role:batch-delete:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/role/batch/delete", "http_method": HTTP_METHOD_POST, "description": "批量删除角色"},
        {"name": "批量更新状态", "code": "api:core:role:batch-status:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/role/batch/status", "http_method": HTTP_METHOD_POST, "description": "批量更新角色状态"},
        {"name": "更新菜单权限", "code": "api:core:role:menus-permissions:put", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/role/{role_id}/menus-permissions", "http_method": HTTP_METHOD_PUT, "description": "更新角色菜单和权限"},
        {"name": "复制角色", "code": "api:core:role:copy:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/role/copy/{role_id}", "http_method": HTTP_METHOD_POST, "description": "复制角色"},
    ],

    # 菜单管理
    "system-menu": [
        {"name": "查询菜单列表", "code": "api:core:menu:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/menu/list", "http_method": HTTP_METHOD_GET, "description": "查询菜单列表"},
        {"name": "创建菜单", "code": "api:core:menu:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/menu", "http_method": HTTP_METHOD_POST, "description": "创建菜单"},
        {"name": "获取菜单详情", "code": "api:core:menu:detail:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/menu/{menu_id}", "http_method": HTTP_METHOD_GET, "description": "获取菜单详情"},
        {"name": "更新菜单", "code": "api:core:menu:put", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/menu/{menu_id}", "http_method": HTTP_METHOD_PUT, "description": "更新菜单"},
        {"name": "删除菜单", "code": "api:core:menu:delete", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/menu/{menu_id}", "http_method": HTTP_METHOD_DELETE, "description": "删除菜单"},
        {"name": "批量删除菜单", "code": "api:core:menu:batch-delete:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/menu/batch/delete", "http_method": HTTP_METHOD_POST, "description": "批量删除菜单"},
        {"name": "移动菜单", "code": "api:core:menu:move:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/menu/move", "http_method": HTTP_METHOD_POST, "description": "移动菜单"},
        {"name": "获取菜单树", "code": "api:core:menu:tree:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/menu/get/tree", "http_method": HTTP_METHOD_GET, "description": "获取菜单树"},
    ],

    # 部门管理
    "system-dept": [
        {"name": "查询部门列表", "code": "api:core:dept:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/dept", "http_method": HTTP_METHOD_GET, "description": "查询部门列表"},
        {"name": "创建部门", "code": "api:core:dept:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/dept", "http_method": HTTP_METHOD_POST, "description": "创建部门"},
        {"name": "获取部门详情", "code": "api:core:dept:detail:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/dept/{dept_id}", "http_method": HTTP_METHOD_GET, "description": "获取部门详情"},
        {"name": "更新部门", "code": "api:core:dept:put", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/dept/{dept_id}", "http_method": HTTP_METHOD_PUT, "description": "更新部门"},
        {"name": "删除部门", "code": "api:core:dept:delete", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/dept/{dept_id}", "http_method": HTTP_METHOD_DELETE, "description": "删除部门"},
        {"name": "批量删除部门", "code": "api:core:dept:batch-delete:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/dept/batch/delete", "http_method": HTTP_METHOD_POST, "description": "批量删除部门"},
    ],

    # 登录日志
    "system-login-log": [
        {"name": "查询登录日志", "code": "api:core:login-log:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/login-log", "http_method": HTTP_METHOD_GET, "description": "查询登录日志列表"},
        {"name": "删除登录日志", "code": "api:core:login-log:delete", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/login-log/{log_id}", "http_method": HTTP_METHOD_DELETE, "description": "删除登录日志"},
        {"name": "批量删除登录日志", "code": "api:core:login-log:batch-delete:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/login-log/batch/delete", "http_method": HTTP_METHOD_POST, "description": "批量删除登录日志"},
        {"name": "导出登录日志", "code": "api:core:login-log:export:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/login-log/export/excel", "http_method": HTTP_METHOD_GET, "description": "导出登录日志Excel"},
    ],

    # 权限管理
    "system-permission": [
        {"name": "查询权限列表", "code": "api:core:permission:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/permission", "http_method": HTTP_METHOD_GET, "description": "查询权限列表"},
        {"name": "创建权限", "code": "api:core:permission:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/permission", "http_method": HTTP_METHOD_POST, "description": "创建权限"},
        {"name": "获取权限详情", "code": "api:core:permission:detail:get", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/permission/{permission_id}", "http_method": HTTP_METHOD_GET, "description": "获取权限详情"},
        {"name": "更新权限", "code": "api:core:permission:put", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/permission/{permission_id}", "http_method": HTTP_METHOD_PUT, "description": "更新权限"},
        {"name": "删除权限", "code": "api:core:permission:delete", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/permission/{permission_id}", "http_method": HTTP_METHOD_DELETE, "description": "删除权限"},
        {"name": "批量删除权限", "code": "api:core:permission:batch-delete:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/permission/batch/delete", "http_method": HTTP_METHOD_POST, "description": "批量删除权限"},
        {"name": "批量更新状态", "code": "api:core:permission:batch-status:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/permission/batch/status", "http_method": HTTP_METHOD_POST, "description": "批量更新权限状态"},
        {"name": "自动扫描生成", "code": "api:core:permission:auto-scan:post", "permission_type": PERMISSION_TYPE_API, "api_path": "/api/core/permission/auto/scan", "http_method": HTTP_METHOD_POST, "description": "自动扫描生成权限"},
    ],

    # ==================== 测试报告 ====================
    "test-report-list": [
        # API权限（具体API根据实际模块定义）
    ],

    # ==================== 定时任务 ====================
    "scheduler-task": [
        # API权限（具体API根据实际模块定义）
    ],

    "scheduler-log": [
        # API权限（具体API根据实际模块定义）
    ],
}


async def clear_and_init_permissions():
    """清空权限表并重新初始化所有权限"""
    async with AsyncSessionLocal() as session:
        print("=" * 50)
        print("开始清空并重新初始化权限...")
        print("=" * 50)

        # 1. 清空角色-权限关联表
        await session.execute(text("DELETE FROM core_role_permission"))
        print("[1] 已清空角色-权限关联表 (core_role_permission)")

        # 2. 清空权限表
        await session.execute(delete(Permission))
        print("[2] 已清空权限表 (core_permission)")

        # 3. 获取所有菜单ID
        result = await session.execute(select(Menu.id, Menu.title))
        menus = result.fetchall()
        menu_map = {m[0]: m[1] for m in menus}
        print(f"[3] 找到 {len(menus)} 个菜单")

        # 4. 创建权限
        print("\n[4] 开始创建权限...")
        total_created = 0
        total_skipped = 0

        for menu_id, permissions in ALL_PERMISSIONS.items():
            menu_title = menu_map.get(menu_id, menu_id)
            print(f"\n  菜单: {menu_title} ({menu_id})")

            for perm_data in permissions:
                permission = Permission(
                    menu_id=menu_id,
                    name=perm_data["name"],
                    code=perm_data["code"],
                    permission_type=perm_data["permission_type"],
                    api_path=perm_data.get("api_path"),
                    http_method=perm_data.get("http_method", HTTP_METHOD_GET),
                    description=perm_data.get("description", ""),
                    is_active=True,
                )
                session.add(permission)
                total_created += 1

                perm_type = "API"
                print(f"    创建: [{perm_type}] {perm_data['name']} ({perm_data['code']})")

        await session.commit()

        # 5. 为管理员角色分配所有权限
        print("\n[5] 分配权限给管理员角色...")
        result = await session.execute(
            text("SELECT id, name, code FROM core_role WHERE code = 'admin' OR code = 'super_admin' LIMIT 1")
        )
        admin_row = result.fetchone()

        if admin_row:
            admin_id = admin_row[0]
            admin_name = admin_row[1]
            admin_code = admin_row[2]
            print(f"    找到角色: {admin_name} ({admin_code})")

            # 获取所有权限ID
            result = await session.execute(select(Permission.id))
            perm_ids = [row[0] for row in result.fetchall()]

            # 批量插入角色-权限关联
            for perm_id in perm_ids:
                await session.execute(
                    text("INSERT INTO core_role_permission (role_id, permission_id) VALUES (:role_id, :perm_id)"),
                    {"role_id": admin_id, "perm_id": perm_id}
                )

            await session.commit()
            print(f"    分配了 {len(perm_ids)} 个权限")

        else:
            print("    [警告] 未找到管理员角色，请手动在角色管理中分配权限")

        print("\n" + "=" * 50)
        print("权限初始化完成！")
        print(f"创建权限数: {total_created}")
        print("权限分布（仅API权限）:")
        print("  设备管理:")
        print("    - 设备列表: 10 API")
        print("    - 升级管理: 6 API")
        print("    - 设备配置: 7 API")
        print("    - 设备监控: 2 API (申请/释放/保持使用接口不加权限控制)")
        print("  性能监控:")
        print("    - 性能监控: 14 API")
        print("    - 版本对比: 8 API")
        print("  系统管理:")
        print("    - 用户管理: 10 API")
        print("    - 角色管理: 9 API")
        print("    - 菜单管理: 8 API")
        print("    - 部门管理: 6 API")
        print("    - 登录日志: 4 API")
        print("    - 权限管理: 8 API")
        print("请刷新前端页面查看权限管理。")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(clear_and_init_permissions())