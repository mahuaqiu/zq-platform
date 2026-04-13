#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
初始化 AI助手 Skill 子菜单
执行方式: cd backend-fastapi && python scripts/init_ai_skill_menu.py
"""
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from core.menu.model import Menu


async def init_ai_skill_menu():
    """初始化 AI Skill 菜单"""
    async with AsyncSessionLocal() as session:
        # 查找 AI助手父菜单
        result = await session.execute(
            select(Menu).where(Menu.id == "ai-assistant-root")
        )
        parent_menu = result.scalar_one_or_none()

        if not parent_menu:
            print("未找到 AI助手父菜单，请先运行 init_ai_assistant_menu.py")
            return

        # 检查 Skill 菜单是否已存在
        result = await session.execute(
            select(Menu).where(Menu.id == "ai-assistant-skill")
        )
        existing = result.scalar_one_or_none()

        if existing:
            print("Skill 菜单已存在，跳过创建")
            return

        # 创建 Skill 子菜单
        skill_menu = Menu(
            id="ai-assistant-skill",
            name="AIAssistantSkill",
            title="Skill管理",
            path="/ai-assistant/skill",
            type="menu",
            component="/views/ai-assistant/skill/index",
            parent_id="ai-assistant-root",
            order=3,
            sort=3,
        )
        session.add(skill_menu)
        await session.commit()

        print("Skill 菜单创建成功！")
        print(f"  - ID: ai-assistant-skill")
        print(f"  - 名称: Skill管理")
        print(f"  - 路径: /ai-assistant/skill")
        print(f"  - 父菜单: AI助手")


if __name__ == "__main__":
    asyncio.run(init_ai_skill_menu())