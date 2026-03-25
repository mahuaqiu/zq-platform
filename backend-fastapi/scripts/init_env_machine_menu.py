#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
初始化执行机管理菜单并分配给管理员角色
执行方式: cd backend-fastapi && python scripts/init_env_machine_menu.py
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select, text
from app.database import AsyncSessionLocal
from core.menu.model import Menu


# 菜单配置数据
MENUS = [
    # 一级菜单
    {
        "id": "env-machine-root",
        "name": "EnvMachine",
        "title": "设备管理",
        "path": "/env-machine",
        "type": "catalog",
        "icon": "ep:monitor",
        "order": 100,
        "parent_id": None,
    },
    # 二级菜单
    {
        "id": "env-machine-gamma",
        "name": "EnvMachineGamma",
        "title": "集成验证",
        "path": "/env-machine/gamma",
        "type": "menu",
        "component": "/views/env-machine/index",
        "parent_id": "env-machine-root",
        "order": 1,
    },
    {
        "id": "env-machine-app",
        "name": "EnvMachineApp",
        "title": "APP",
        "path": "/env-machine/app",
        "type": "menu",
        "component": "/views/env-machine/index",
        "parent_id": "env-machine-root",
        "order": 2,
    },
    {
        "id": "env-machine-av",
        "name": "EnvMachineAv",
        "title": "音视频",
        "path": "/env-machine/av",
        "type": "menu",
        "component": "/views/env-machine/index",
        "parent_id": "env-machine-root",
        "order": 3,
    },
    {
        "id": "env-machine-public",
        "name": "EnvMachinePublic",
        "title": "公共设备",
        "path": "/env-machine/public",
        "type": "menu",
        "component": "/views/env-machine/index",
        "parent_id": "env-machine-root",
        "order": 4,
    },
    {
        "id": "env-machine-manual",
        "name": "EnvMachineManual",
        "title": "手工使用",
        "path": "/env-machine/manual",
        "type": "menu",
        "component": "/views/env-machine/index",
        "parent_id": "env-machine-root",
        "order": 5,
    },
]


async def init_menus():
    """初始化菜单并分配给管理员角色"""
    async with AsyncSessionLocal() as session:
        menu_ids = []

        # 1. 创建菜单
        for menu_data in MENUS:
            result = await session.execute(
                select(Menu).where(Menu.id == menu_data["id"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"菜单已存在，跳过: {menu_data['title']}")
                menu_ids.append(menu_data["id"])
                continue

            menu = Menu(
                id=menu_data["id"],
                name=menu_data["name"],
                title=menu_data["title"],
                path=menu_data["path"],
                type=menu_data["type"],
                icon=menu_data.get("icon"),
                component=menu_data.get("component"),
                parent_id=menu_data.get("parent_id"),
                order=menu_data.get("order", 0),
                sort=menu_data.get("order", 0),
            )
            session.add(menu)
            menu_ids.append(menu_data["id"])
            print(f"创建菜单: {menu_data['title']}")

        await session.commit()

        # 2. 查找管理员角色（使用原生 SQL 避免关系加载问题）
        result = await session.execute(
            text("SELECT id, name, code FROM core_role WHERE code = 'admin' OR code = 'super_admin' OR role_type = 0 LIMIT 1")
        )
        admin_row = result.fetchone()

        if not admin_row:
            print("\n警告: 未找到管理员角色，请手动在角色管理中分配菜单权限")
            print("菜单初始化完成！")
            return

        admin_id = admin_row[0]
        admin_name = admin_row[1]
        admin_code = admin_row[2]

        print(f"\n找到角色: {admin_name} ({admin_code})")

        # 3. 为管理员角色分配菜单权限
        for menu_id in menu_ids:
            # 检查是否已分配
            result = await session.execute(
                text("SELECT 1 FROM core_role_menu WHERE role_id = :role_id AND menu_id = :menu_id"),
                {"role_id": admin_id, "menu_id": menu_id}
            )
            if result.scalar():
                print(f"  菜单权限已存在: {menu_id}")
                continue

            # 插入关联
            await session.execute(
                text("INSERT INTO core_role_menu (role_id, menu_id) VALUES (:role_id, :menu_id)"),
                {"role_id": admin_id, "menu_id": menu_id}
            )
            print(f"  分配菜单权限: {menu_id}")

        await session.commit()
        print("\n菜单初始化并分配权限完成！请刷新前端页面查看。")


if __name__ == "__main__":
    asyncio.run(init_menus())