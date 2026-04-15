#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新执行机管理菜单（合并4个子菜单为设备列表）
执行方式: cd backend-fastapi && python scripts/update_env_machine_menu.py
"""
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select, delete
from app.database import AsyncSessionLocal
from core.menu.model import Menu

# 要删除的旧菜单ID
OLD_MENU_IDS = [
    "env-machine-gamma",
    "env-machine-app",
    "env-machine-av",
    "env-machine-public",
]

# 新菜单配置
NEW_MENUS = [
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
]


async def update_menus():
    """更新菜单"""
    async with AsyncSessionLocal() as session:
        # 1. 删除旧菜单
        for menu_id in OLD_MENU_IDS:
            result = await session.execute(delete(Menu).where(Menu.id == menu_id))
            if result.rowcount > 0:
                print(f"删除菜单: {menu_id}")

        # 2. 创建新菜单
        for menu_data in NEW_MENUS:
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
                component=menu_data.get("component"),
                parent_id=menu_data.get("parent_id"),
                order=menu_data.get("order", 0),
                sort=menu_data.get("order", 0),
            )
            session.add(menu)
            print(f"创建菜单: {menu_data['title']}")

        # 3. 更新手工使用菜单的order
        result = await session.execute(
            select(Menu).where(Menu.id == "env-machine-manual")
        )
        manual_menu = result.scalar_one_or_none()
        if manual_menu:
            manual_menu.order = 2
            manual_menu.sort = 2
            print(f"更新菜单顺序: 手工使用 -> order=2")

        await session.commit()
        print("\n菜单更新完成！请刷新前端页面查看。")


if __name__ == "__main__":
    asyncio.run(update_menus())