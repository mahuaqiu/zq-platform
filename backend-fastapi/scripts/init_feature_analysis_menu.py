#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
特性质量统计菜单初始化脚本

使用方法:
    python scripts/init_feature_analysis_menu.py
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from core.menu.model import Menu


async def init_menus():
    """初始化特性质量统计菜单"""
    async with AsyncSessionLocal() as db:
        try:
            # 检查一级菜单是否已存在
            result = await db.execute(
                select(Menu).where(Menu.name == "FeatureQuality")
            )
            existing = result.scalar_one_or_none()

            if existing:
                print("菜单已存在，跳过初始化")
                return

            # 创建一级菜单：特性质量统计
            parent_menu = Menu(
                id="feature_quality_catalog",
                name="FeatureQuality",
                title="特性质量统计",
                path="/feature-quality",
                type="catalog",
                icon="lucide:chart-pie",
                order=50,  # 放在概览之前
                hideInMenu=False,
                hideChildrenInMenu=False,
            )
            db.add(parent_menu)
            await db.flush()

            # 创建二级菜单：需求进展
            progress_menu = Menu(
                id="feature_progress_menu",
                name="FeatureProgress",
                title="需求进展",
                path="/feature-quality/progress",
                type="menu",
                component="feature-analysis/progress/index",
                parent_id=parent_menu.id,
                order=1,
                hideInMenu=False,
            )
            db.add(progress_menu)

            # 创建二级菜单：需求质量评价（占位）
            eval_menu = Menu(
                id="feature_quality_eval_menu",
                name="FeatureQualityEval",
                title="需求质量评价",
                path="/feature-quality/eval",
                type="menu",
                component="",  # 占位，后续实现
                parent_id=parent_menu.id,
                order=2,
                hideInMenu=False,
            )
            db.add(eval_menu)

            # 创建二级菜单：修改引入问题（占位）
            bug_menu = Menu(
                id="feature_bug_intro_menu",
                name="FeatureBugIntro",
                title="修改引入问题",
                path="/feature-quality/bug-intro",
                type="menu",
                component="",  # 占位，后续实现
                parent_id=parent_menu.id,
                order=3,
                hideInMenu=False,
            )
            db.add(bug_menu)

            await db.commit()
            print("菜单初始化成功！")
            print("- 特性质量统计（一级菜单）")
            print("  - 需求进展")
            print("  - 需求质量评价（占位）")
            print("  - 修改引入问题（占位）")

        except Exception as e:
            await db.rollback()
            print(f"初始化失败: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(init_menus())