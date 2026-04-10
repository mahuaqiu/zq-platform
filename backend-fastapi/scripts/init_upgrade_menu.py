#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
初始化升级管理菜单
执行方式: cd backend-fastapi && python scripts/init_upgrade_menu.py

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


async def init_upgrade_menu():
    """初始化升级管理菜单"""
    async with AsyncSessionLocal() as session:
        # 查找设备管理父菜单
        result = await session.execute(select(Menu).where(Menu.path == "/env-machine"))
        parent = result.scalar_one_or_none()

        if not parent:
            print("未找到设备管理父菜单")
            return

        # 检查是否已存在升级管理菜单
        result = await session.execute(
            select(Menu).where(Menu.path == "/env-machine/upgrade")
        )
        existing = result.scalar_one_or_none()

        if existing:
            print("升级管理菜单已存在，跳过")
            return

        # 创建升级管理子菜单
        menu = Menu(
            id="env-machine-upgrade",
            name="EnvMachineUpgrade",
            title="升级管理",
            path="/env-machine/upgrade",
            type="menu",
            component="/views/env-machine/upgrade",
            icon="ant-design:cloud-upload-outlined",
            parent_id=parent.id,
            order=100,
            sort=100,
        )
        session.add(menu)
        await session.commit()
        print("升级管理菜单创建成功！超级管理员用户请刷新前端页面查看。")


if __name__ == "__main__":
    asyncio.run(init_upgrade_menu())