#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统一菜单初始化脚本
执行方式: cd backend-fastapi && python scripts/init_all_menus.py

功能：清空菜单表，重新初始化所有菜单

注意：超级管理员（is_superuser=True）自动拥有所有菜单权限，无需额外分配
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select, delete, text
from app.database import AsyncSessionLocal
from core.menu.model import Menu


# 所有菜单配置数据（按层级顺序排列）
ALL_MENUS = [
    # ==================== 设备管理（一级菜单）====================
    {
        "id": "env-machine-root",
        "name": "EnvMachine",
        "title": "设备管理",
        "path": "/env-machine",
        "type": "catalog",
        "icon": "ep:monitor",
        "order": 1,
        "parent_id": None,
    },
    # 设备管理子菜单
    {
        "id": "env-machine-monitor",
        "name": "EnvMachineMonitor",
        "title": "设备监控",
        "path": "/env-machine/monitor",
        "type": "menu",
        "component": "/views/device-monitor/index",
        "parent_id": "env-machine-root",
        "order": 1,
    },
    {
        "id": "env-machine-list",
        "name": "EnvMachineList",
        "title": "设备列表",
        "path": "/env-machine/list",
        "type": "menu",
        "component": "/views/env-machine/list",
        "parent_id": "env-machine-root",
        "order": 2,
    },
    {
        "id": "env-machine-upgrade",
        "name": "EnvMachineUpgrade",
        "title": "升级管理",
        "path": "/env-machine/upgrade",
        "type": "menu",
        "component": "/views/env-machine/upgrade",
        "parent_id": "env-machine-root",
        "order": 3,
    },
    {
        "id": "env-machine-config",
        "name": "EnvMachineConfig",
        "title": "设备配置",
        "path": "/env-machine/config",
        "type": "menu",
        "component": "/views/env-machine/config",
        "parent_id": "env-machine-root",
        "order": 4,
    },

    # ==================== 测试报告（一级菜单）====================
    {
        "id": "test-report-root",
        "name": "TestReport",
        "title": "测试报告",
        "path": "/test-report",
        "type": "catalog",
        "icon": "ep:document",
        "order": 2,
        "parent_id": None,
    },
    # 测试报告子菜单
    {
        "id": "test-report-list",
        "name": "TestReportList",
        "title": "报告列表",
        "path": "/test-report/list",
        "type": "menu",
        "component": "/views/test-report/list/index",
        "parent_id": "test-report-root",
        "order": 1,
    },

    # ==================== AI助手（一级菜单）====================
    {
        "id": "ai-assistant-root",
        "name": "AIAssistant",
        "title": "AI助手",
        "path": "/ai-assistant",
        "type": "catalog",
        "icon": "ep:chat-dot-round",
        "order": 3,
        "parent_id": None,
    },
    # AI助手子菜单
    {
        "id": "ai-assistant-role",
        "name": "AIAssistantRole",
        "title": "角色管理",
        "path": "/ai-assistant/role",
        "type": "menu",
        "component": "/views/ai-assistant/role/index",
        "parent_id": "ai-assistant-root",
        "order": 0,
    },
    {
        "id": "ai-assistant-session",
        "name": "AIAssistantSession",
        "title": "会话管理",
        "path": "/ai-assistant/session",
        "type": "menu",
        "component": "/views/ai-assistant/session/index",
        "parent_id": "ai-assistant-root",
        "order": 1,
    },
    {
        "id": "ai-assistant-group",
        "name": "AIAssistantGroup",
        "title": "群组管理",
        "path": "/ai-assistant/group",
        "type": "menu",
        "component": "/views/ai-assistant/group/index",
        "parent_id": "ai-assistant-root",
        "order": 2,
    },
    {
        "id": "ai-assistant-skill",
        "name": "AIAssistantSkill",
        "title": "Skill管理",
        "path": "/ai-assistant/skill",
        "type": "menu",
        "component": "/views/ai-assistant/skill/index",
        "parent_id": "ai-assistant-root",
        "order": 3,
    },

    # ==================== 定时任务（一级菜单）====================
    {
        "id": "scheduler-root",
        "name": "Scheduler",
        "title": "定时任务",
        "path": "/scheduler",
        "type": "catalog",
        "icon": "mdi:clock-outline",
        "order": 4,
        "parent_id": None,
    },
    # 定时任务子菜单
    {
        "id": "scheduler-task",
        "name": "SchedulerTask",
        "title": "任务列表",
        "path": "/scheduler",
        "type": "menu",
        "component": "/views/scheduler/index",
        "parent_id": "scheduler-root",
        "order": 1,
    },
    {
        "id": "scheduler-log",
        "name": "SchedulerLog",
        "title": "执行日志",
        "path": "/scheduler/log",
        "type": "menu",
        "component": "/views/scheduler/log",
        "parent_id": "scheduler-root",
        "order": 2,
    },
]


async def clear_and_init_menus():
    """清空菜单表并重新初始化所有菜单"""
    async with AsyncSessionLocal() as session:
        print("=" * 50)
        print("开始清空并重新初始化菜单...")
        print("=" * 50)

        # 1. 清空角色-菜单关联表
        await session.execute(text("DELETE FROM core_role_menu"))
        print("[1] 已清空角色-菜单关联表 (core_role_menu)")

        # 2. 清空菜单表
        await session.execute(delete(Menu))
        print("[2] 已清空菜单表 (core_menu)")

        # 3. 按顺序创建所有菜单
        print("\n[3] 开始创建菜单...")
        for menu_data in ALL_MENUS:
            menu = Menu(
                id=menu_data["id"],
                name=menu_data["name"],
                title=menu_data["title"],
                path=menu_data["path"],
                type=menu_data["type"],
                icon=menu_data.get("icon", ""),
                component=menu_data.get("component"),
                parent_id=menu_data.get("parent_id"),
                order=menu_data.get("order", 0),
                sort=menu_data.get("order", 0),
            )
            session.add(menu)
            print(f"    创建: {menu_data['title']} ({menu_data['id']})")

        await session.commit()

        # 4. 为管理员角色分配菜单权限
        print("\n[4] 分配菜单权限给管理员角色...")
        result = await session.execute(
            text("SELECT id, name, code FROM core_role WHERE code = 'admin' OR code = 'super_admin' OR role_type = 0 LIMIT 1")
        )
        admin_row = result.fetchone()

        if admin_row:
            admin_id = admin_row[0]
            admin_name = admin_row[1]
            admin_code = admin_row[2]
            print(f"    找到角色: {admin_name} ({admin_code})")

            for menu_data in ALL_MENUS:
                await session.execute(
                    text("INSERT INTO core_role_menu (role_id, menu_id) VALUES (:role_id, :menu_id)"),
                    {"role_id": admin_id, "menu_id": menu_data["id"]}
                )
                print(f"    分配: {menu_data['title']}")

            await session.commit()
        else:
            print("    [警告] 未找到管理员角色，请手动在角色管理中分配菜单权限")

        print("\n" + "=" * 50)
        print("菜单初始化完成！")
        print("菜单结构：")
        print("  设备管理 (order=1)")
        print("    - 设备监控")
        print("    - 设备列表")
        print("    - 升级管理")
        print("    - 设备配置")
        print("  测试报告 (order=2)")
        print("    - 报告列表")
        print("  AI助手 (order=3)")
        print("    - 角色管理")
        print("    - 会话管理")
        print("    - 群组管理")
        print("    - Skill管理")
        print("  定时任务 (order=4)")
        print("    - 任务列表")
        print("    - 执行日志")
        print("请刷新前端页面查看。")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(clear_and_init_menus())