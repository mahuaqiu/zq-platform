#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控菜单初始化脚本
执行方式: cd backend-fastapi && python scripts/init_performance_monitor_menus.py

功能：初始化性能监控模块的菜单（不清空其他菜单）

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


# 性能监控菜单配置数据
PERFORMANCE_MONITOR_MENUS = [
    # ==================== 性能监控（一级菜单）====================
    {
        "id": "performance-monitor-root",
        "name": "PerformanceMonitor",
        "title": "性能监控",
        "path": "/performance-monitor",
        "type": "catalog",
        "icon": "ep:data-line",
        "order": 5,
        "parent_id": None,
    },
    # 性能监控子菜单
    {
        "id": "performance-monitor-main",
        "name": "PerformanceMonitorMain",
        "title": "性能监控",
        "path": "/performance-monitor",
        "type": "menu",
        "component": "/views/performance-monitor/index",
        "parent_id": "performance-monitor-root",
        "order": 1,
    },
    {
        "id": "performance-monitor-compare",
        "name": "PerformanceMonitorCompare",
        "title": "版本对比",
        "path": "/performance-monitor/compare",
        "type": "menu",
        "component": "/views/performance-monitor/compare",
        "parent_id": "performance-monitor-root",
        "order": 2,
    },
]


async def init_performance_monitor_menus():
    """初始化性能监控菜单（仅删除并重建性能监控相关菜单）"""
    async with AsyncSessionLocal() as session:
        print("=" * 50)
        print("开始初始化性能监控菜单...")
        print("=" * 50)

        # 1. 删除性能监控相关的角色-菜单关联
        for menu_data in PERFORMANCE_MONITOR_MENUS:
            await session.execute(
                text("DELETE FROM core_role_menu WHERE menu_id = :menu_id"),
                {"menu_id": menu_data["id"]}
            )
        print("[1] 已删除性能监控菜单的角色关联")

        # 2. 删除性能监控相关的菜单
        for menu_data in PERFORMANCE_MONITOR_MENUS:
            await session.execute(
                text("DELETE FROM core_menu WHERE id = :id"),
                {"id": menu_data["id"]}
            )
        print("[2] 已删除性能监控菜单")

        # 3. 创建性能监控菜单
        print("\n[3] 开始创建菜单...")
        for menu_data in PERFORMANCE_MONITOR_MENUS:
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

            for menu_data in PERFORMANCE_MONITOR_MENUS:
                await session.execute(
                    text("INSERT INTO core_role_menu (role_id, menu_id) VALUES (:role_id, :menu_id)"),
                    {"role_id": admin_id, "menu_id": menu_data["id"]}
                )
                print(f"    分配: {menu_data['title']}")

            await session.commit()
        else:
            print("    [警告] 未找到管理员角色，请手动在角色管理中分配菜单权限")

        print("\n" + "=" * 50)
        print("性能监控菜单初始化完成！")
        print("菜单结构：")
        print("  性能监控 (order=5)")
        print("    - 性能监控")
        print("    - 版本对比")
        print("请刷新前端页面查看。")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(init_performance_monitor_menus())