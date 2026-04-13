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

from sqlalchemy import select, insert
from app.database import AsyncSessionLocal
from core.menu.model import Menu
from core.role.model import Role, role_menu

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
]


async def init_menus():
    """初始化菜单并分配给管理员角色"""
    async with AsyncSessionLocal() as session:
        # 查询管理员角色
        result = await session.execute(
            select(Role).where(Role.code == "admin")
        )
        admin_role = result.scalar_one_or_none()

        if not admin_role:
            print("警告：未找到管理员角色（code=admin），无法分配菜单权限")
            admin_role_id = None
        else:
            admin_role_id = admin_role.id
            print(f"找到管理员角色: {admin_role.name} (id={admin_role_id})")

        # 创建菜单
        for menu_data in MENUS:
            result = await session.execute(
                select(Menu).where(Menu.id == menu_data["id"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"菜单已存在，跳过: {menu_data['title']}")

                # 检查并分配权限（如果管理员角色存在且未分配）
                if admin_role_id:
                    await assign_menu_to_role(session, admin_role_id, menu_data["id"])
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

            # 给管理员角色分配菜单权限
            if admin_role_id:
                await assign_menu_to_role(session, admin_role_id, menu_data["id"], is_new=True)

        await session.commit()
        print("\n菜单初始化完成！请刷新前端页面查看。")


async def assign_menu_to_role(session, role_id: str, menu_id: str, is_new: bool = False):
    """给角色分配菜单权限"""
    from sqlalchemy import text

    # 检查是否已分配
    result = await session.execute(
        text("SELECT role_id FROM core_role_menu WHERE role_id = :role_id AND menu_id = :menu_id"),
        {"role_id": role_id, "menu_id": menu_id}
    )
    existing = result.fetchone()

    if existing:
        if not is_new:
            print(f"  - 菜单权限已分配: {menu_id}")
        return

    # 分配权限
    await session.execute(
        insert(role_menu).values(role_id=role_id, menu_id=menu_id)
    )
    print(f"  - 已分配菜单权限给管理员: {menu_id}")


if __name__ == "__main__":
    asyncio.run(init_menus())