#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
初始化 AI助手菜单
执行方式: cd backend-fastapi && python scripts/init_ai_assistant_menu.py
"""
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from core.menu.model import Menu

MENUS = [
    {
        "id": "ai-assistant-root",
        "name": "AIAssistant",
        "title": "AI助手",
        "path": "/ai-assistant",
        "type": "catalog",
        "icon": "ep:chat-dot-round",
        "order": 50,
        "parent_id": None,
    },
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
]


async def init_menus():
    """初始化菜单"""
    async with AsyncSessionLocal() as session:
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
        print("\n菜单初始化完成！")


if __name__ == "__main__":
    asyncio.run(init_menus())