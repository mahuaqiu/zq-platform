#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新设备管理菜单结构
执行方式: cd backend-fastapi && python scripts/update_device_menu_structure.py

调整内容：
1. 删除"概览"一级菜单及其子菜单
2. 删除"手工使用"菜单
3. 将设备监控移动到设备管理下面
4. 重新排序：设备监控(1)、设备列表(2)、升级管理(3)、配置管理(4)

注意：超级管理员（is_superuser=True）自动拥有所有菜单权限，无需额外分配
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select, delete
from app.database import AsyncSessionLocal
from core.menu.model import Menu


async def update_menu_structure():
    """更新菜单结构"""
    async with AsyncSessionLocal() as session:
        # 1. 删除"概览"一级菜单
        result = await session.execute(
            select(Menu).where(Menu.id == "overview-root")
        )
        overview_root = result.scalar_one_or_none()
        if overview_root:
            await session.execute(delete(Menu).where(Menu.id == "overview-root"))
            print("[删除] 概览一级菜单 (overview-root)")

        # 2. 删除旧的设备监控菜单（在概览下面的）
        result = await session.execute(
            select(Menu).where(Menu.id == "device-monitor")
        )
        old_device_monitor = result.scalar_one_or_none()
        if old_device_monitor:
            await session.execute(delete(Menu).where(Menu.id == "device-monitor"))
            print("[删除] 旧的设备监控菜单 (device-monitor)")

        # 3. 删除"手工使用"菜单
        result = await session.execute(
            select(Menu).where(Menu.id == "env-machine-manual")
        )
        manual_menu = result.scalar_one_or_none()
        if manual_menu:
            await session.execute(delete(Menu).where(Menu.id == "env-machine-manual"))
            print("[删除] 手工使用菜单 (env-machine-manual)")

        # 4. 查找设备管理父菜单
        result = await session.execute(
            select(Menu).where(Menu.id == "env-machine-root")
        )
        parent = result.scalar_one_or_none()
        if not parent:
            print("[错误] 未找到设备管理父菜单 (env-machine-root)")
            return

        # 5. 创建新的设备监控菜单（在设备管理下面）
        result = await session.execute(
            select(Menu).where(Menu.id == "env-machine-monitor")
        )
        existing_monitor = result.scalar_one_or_none()

        if existing_monitor:
            # 更新排序
            existing_monitor.order = 1
            existing_monitor.sort = 1
            print("[更新] 设备监控菜单排序为 1")
        else:
            # 创建新菜单
            new_monitor = Menu(
                id="env-machine-monitor",
                name="EnvMachineMonitor",
                title="设备监控",
                path="/env-machine/monitor",
                type="menu",
                component="/views/device-monitor/index",
                parent_id=parent.id,
                order=1,
                sort=1,
            )
            session.add(new_monitor)
            print("[创建] 设备监控菜单 (env-machine-monitor)")

        # 6. 更新设备列表排序
        result = await session.execute(
            select(Menu).where(Menu.id == "env-machine-list")
        )
        list_menu = result.scalar_one_or_none()
        if list_menu:
            list_menu.order = 2
            list_menu.sort = 2
            print("[更新] 设备列表排序为 2")

        # 7. 更新升级管理排序和移除图标
        result = await session.execute(
            select(Menu).where(Menu.id == "env-machine-upgrade")
        )
        upgrade_menu = result.scalar_one_or_none()
        if upgrade_menu:
            upgrade_menu.order = 3
            upgrade_menu.sort = 3
            upgrade_menu.icon = ""
            print("[更新] 升级管理排序为 3，移除图标")

        # 8. 更新配置管理排序和移除图标
        result = await session.execute(
            select(Menu).where(Menu.id == "env-machine-config")
        )
        config_menu = result.scalar_one_or_none()
        if config_menu:
            config_menu.order = 4
            config_menu.sort = 4
            config_menu.icon = ""
            print("[更新] 配置管理排序为 4，移除图标")

        await session.commit()
        print("\n菜单结构更新完成！")
        print("新菜单顺序：设备监控、设备列表、升级管理、配置管理")
        print("超级管理员用户请刷新前端页面查看。")


if __name__ == "__main__":
    asyncio.run(update_menu_structure())