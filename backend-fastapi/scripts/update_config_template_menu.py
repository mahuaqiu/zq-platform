#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新配置管理菜单标题为"设备配置"
执行方式: cd backend-fastapi && python scripts/update_config_template_menu.py
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from core.menu.model import Menu


async def update_menu_title():
    async with AsyncSessionLocal() as session:
        # 查找配置管理菜单
        result = await session.execute(
            select(Menu).where(Menu.id == "env-machine-config")
        )
        menu = result.scalar_one_or_none()

        if not menu:
            print("[错误] 未找到配置管理菜单 (env-machine-config)")
            return

        # 更新标题
        menu.title = "设备配置"
        await session.commit()
        print("[OK] 菜单标题已更新为 '设备配置'")


if __name__ == "__main__":
    asyncio.run(update_menu_title())