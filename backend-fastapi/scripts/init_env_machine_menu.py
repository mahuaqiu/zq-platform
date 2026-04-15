#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
初始化执行机管理菜单
执行方式: cd backend-fastapi && python scripts/init_env_machine_menu.py

注意：超级管理员（is_superuser=True）自动拥有所有菜单权限，无需额外分配
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
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
    # 二级菜单：设备列表（合并）
    {
        "id": "env-machine-list",
        "name": "EnvMachineList",
        "title": "设备列表",
        "path": "/env-machine/list",
        "type": "menu",
        "component": "/views/env-machine/list",
        "parent_id": "env-machine-root",
        "order": 1,
    },
    # 二级菜单：手工使用
    {
        "id": "env-machine-manual",
        "name": "EnvMachineManual",
        "title": "手工使用",
        "path": "/env-machine/manual",
        "type": "menu",
        "component": "/views/env-machine/index",
        "parent_id": "env-machine-root",
        "order": 2,
    },
]


async def init_menus():
    """初始化菜单"""
    async with AsyncSessionLocal() as session:
        # 创建菜单
        for menu_data in MENUS:
            result = await session.execute(
                select(Menu).where(Menu.id == menu_data["id"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"菜单已存在，跳过: {menu_data['title']}")
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
            print(f"创建菜单: {menu_data['title']}")

        await session.commit()
        print("\n菜单初始化完成！超级管理员用户请刷新前端页面查看。")


if __name__ == "__main__":
    asyncio.run(init_menus())