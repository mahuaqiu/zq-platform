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
            parent_menu = result.scalar_one_or_none()

            if not parent_menu:
                # 创建一级菜单：特性质量统计
                parent_menu = Menu(
                    id="fq_catalog",
                    name="FeatureQuality",
                    title="特性质量统计",
                    path="/feature-quality",
                    type="catalog",
                    icon="lucide:chart-pie",
                    order=50,
                    hideInMenu=False,
                    hideChildrenInMenu=False,
                )
                db.add(parent_menu)
                await db.flush()
                print("创建一级菜单：特性质量统计")

            # 检查并更新/创建需求进展菜单
            result = await db.execute(
                select(Menu).where(Menu.name == "FeatureProgress")
            )
            progress_menu = result.scalar_one_or_none()
            if not progress_menu:
                progress_menu = Menu(
                    id="fq_progress",
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
                print("创建菜单：需求进展")
            else:
                print("菜单已存在：需求进展")

            # 检查并更新/创建需求质量评价菜单
            result = await db.execute(
                select(Menu).where(Menu.name == "FeatureQualityEval")
            )
            eval_menu = result.scalar_one_or_none()
            if not eval_menu:
                eval_menu = Menu(
                    id="fq_eval",
                    name="FeatureQualityEval",
                    title="需求质量评价",
                    path="/feature-quality/eval",
                    type="menu",
                    component="feature-analysis/eval/index",
                    parent_id=parent_menu.id,
                    order=2,
                    hideInMenu=False,
                )
                db.add(eval_menu)
                print("创建菜单：需求质量评价")
            else:
                # 更新已存在菜单的 component 字段
                eval_menu.component = "feature-analysis/eval/index"
                print("更新菜单：需求质量评价")

            # 检查并更新/创建修改引入问题菜单
            result = await db.execute(
                select(Menu).where(Menu.name == "FeatureBugIntro")
            )
            bug_menu = result.scalar_one_or_none()
            if not bug_menu:
                bug_menu = Menu(
                    id="fq_bug",
                    name="FeatureBugIntro",
                    title="修改引入问题",
                    path="/feature-quality/bug-intro",
                    type="menu",
                    component="feature-analysis/bug-intro/index",
                    parent_id=parent_menu.id,
                    order=3,
                    hideInMenu=False,
                )
                db.add(bug_menu)
                print("创建菜单：修改引入问题")
            else:
                # 更新已存在菜单的 component 字段
                bug_menu.component = "feature-analysis/bug-intro/index"
                print("更新菜单：修改引入问题")

            await db.commit()
            print("菜单初始化完成！")

        except Exception as e:
            await db.rollback()
            print(f"初始化失败: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(init_menus())