#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调整菜单显示和排序
执行方式: cd backend-fastapi && python scripts/update_menu_order.py

调整内容：
1. 隐藏"特性质量统计"菜单
2. 调整一级菜单排序：
   - 设备管理: 1
   - 测试报告: 2
   - AI助手: 3
   - 定时任务: 4
   - 用户中心: 5
   - 系统管理: 6
"""
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from core.menu.model import Menu


async def update_menu():
    """更新菜单"""
    async with AsyncSessionLocal() as session:
        # 1. 隐藏"特性质量统计"菜单
        result = await session.execute(
            select(Menu).where(Menu.id == "feature-analysis-root")
        )
        feature_menu = result.scalar_one_or_none()
        if feature_menu:
            feature_menu.hide_in_menu = True
            print("[隐藏] 特性质量统计菜单")
        else:
            print("[提示] 未找到特性质量统计菜单")

        # 2. 调整一级菜单排序
        menu_order = {
            "env-machine-root": ("设备管理", 1),
            "test-report-root": ("测试报告", 2),
            "ai-assistant-root": ("AI助手", 3),
            "scheduler-root": ("定时任务", 4),
            "user-center": ("用户中心", 5),
            "system": ("系统管理", 6),
        }

        for menu_id, (name, order) in menu_order.items():
            result = await session.execute(
                select(Menu).where(Menu.id == menu_id)
            )
            menu = result.scalar_one_or_none()
            if menu:
                menu.order = order
                menu.sort = order
                print(f"[更新] {name} 排序为 {order}")
            else:
                print(f"[提示] 未找到 {name} 菜单 (id: {menu_id})")

        await session.commit()
        print("\n菜单调整完成！请刷新前端页面查看。")


if __name__ == "__main__":
    asyncio.run(update_menu())