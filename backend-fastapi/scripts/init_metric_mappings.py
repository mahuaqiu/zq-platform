#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
初始化默认指标映射数据
执行方式: cd backend-fastapi && python scripts/init_metric_mappings.py

功能：初始化 HWiNFO 传感器键名到中文显示名称的映射
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from core.performance_monitor.model import PerformanceMetricMapping


DEFAULT_MAPPINGS = [
    # 系统级指标（常用）
    {"hwinfo_key": "CPU Total Usage", "display_name": "CPU总使用率", "category": "system", "is_primary": True, "unit": "%"},
    {"hwinfo_key": "CPU Total", "display_name": "CPU总使用率", "category": "system", "is_primary": True, "unit": "%"},
    {"hwinfo_key": "GPU Core Usage", "display_name": "GPU核心使用率", "category": "system", "is_primary": True, "unit": "%"},
    {"hwinfo_key": "GPU Usage", "display_name": "GPU使用率", "category": "system", "is_primary": True, "unit": "%"},
    {"hwinfo_key": "Commit Memory", "display_name": "提交内存", "category": "system", "is_primary": True, "unit": "MB"},
    {"hwinfo_key": "CPU Package", "display_name": "CPU温度", "category": "system", "is_primary": True, "unit": "°C"},
    {"hwinfo_key": "CPU Package Power", "display_name": "CPU功耗", "category": "system", "is_primary": True, "unit": "W"},
    {"hwinfo_key": "GPU Temperature", "display_name": "GPU温度", "category": "system", "is_primary": True, "unit": "°C"},
    {"hwinfo_key": "GPU Power", "display_name": "GPU功耗", "category": "system", "is_primary": False, "unit": "W"},
    {"hwinfo_key": "Memory Usage", "display_name": "内存使用率", "category": "system", "is_primary": False, "unit": "%"},
]


async def init_mappings():
    """初始化指标映射数据"""
    async with AsyncSessionLocal() as session:
        added_count = 0
        skipped_count = 0

        for mapping in DEFAULT_MAPPINGS:
            # 检查是否已存在
            existing = await session.execute(
                select(PerformanceMetricMapping).where(
                    PerformanceMetricMapping.hwinfo_key == mapping["hwinfo_key"]
                )
            )
            if existing.scalar_one_or_none():
                skipped_count += 1
                print(f"跳过已存在的映射: {mapping['hwinfo_key']}")
                continue

            # 创建新映射
            obj = PerformanceMetricMapping(**mapping)
            session.add(obj)
            added_count += 1
            print(f"添加映射: {mapping['hwinfo_key']} -> {mapping['display_name']}")

        await session.commit()
        print(f"\n初始化完成！新增: {added_count} 条，跳过: {skipped_count} 条")


if __name__ == "__main__":
    print("开始初始化指标映射数据...")
    asyncio.run(init_mappings())