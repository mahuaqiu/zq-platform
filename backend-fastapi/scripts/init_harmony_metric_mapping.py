#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""初始化 Harmony 性能指标映射。

脚本是幂等的：已存在的 hwinfo_key 会跳过，适合在部署后重复执行。
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import AsyncSessionLocal
from core.performance_monitor.model import PerformanceMetricMapping


HARMONY_METRIC_MAPPINGS = [
    {"hwinfo_key": "Harmony CPU Usage", "display_name": "系统 CPU", "unit": "%", "category": "harmony_cpu", "is_primary": True, "sort": 1},
    {"hwinfo_key": "Harmony CPU User", "display_name": "CPU 用户态", "unit": "%", "category": "harmony_cpu", "is_primary": True, "sort": 2},
    {"hwinfo_key": "Harmony CPU System", "display_name": "CPU 系统态", "unit": "%", "category": "harmony_cpu", "is_primary": True, "sort": 3},
    {"hwinfo_key": "Harmony CPU Idle", "display_name": "CPU 空闲", "unit": "%", "category": "harmony_cpu", "is_primary": False, "sort": 4},
    {"hwinfo_key": "Harmony Mem Total", "display_name": "内存总量", "unit": "MB", "category": "harmony_memory", "is_primary": True, "sort": 10},
    {"hwinfo_key": "Harmony Mem Used", "display_name": "内存使用", "unit": "MB", "category": "harmony_memory", "is_primary": True, "sort": 11},
    {"hwinfo_key": "Harmony Mem Available", "display_name": "内存可用", "unit": "MB", "category": "harmony_memory", "is_primary": True, "sort": 12},
    {"hwinfo_key": "Harmony Net Upload", "display_name": "上行速率", "unit": "KB/s", "category": "harmony_network", "is_primary": False, "sort": 20},
    {"hwinfo_key": "Harmony Net Download", "display_name": "下行速率", "unit": "KB/s", "category": "harmony_network", "is_primary": False, "sort": 21},
    {"hwinfo_key": "Harmony Power", "display_name": "估算功耗", "unit": "W", "category": "harmony_power", "is_primary": False, "sort": 30},
    {"hwinfo_key": "Harmony CPU Temp", "display_name": "CPU 温度", "unit": "°C", "category": "harmony_thermal", "is_primary": False, "sort": 40},
    {"hwinfo_key": "Harmony GPU Usage", "display_name": "GPU 使用率", "unit": "%", "category": "harmony_gpu", "is_primary": False, "sort": 50},
]


async def init_harmony_metric_mapping() -> None:
    """写入 Harmony 稳定指标键。"""
    async with AsyncSessionLocal() as session:
        added = 0
        skipped = 0
        for mapping_data in HARMONY_METRIC_MAPPINGS:
            result = await session.execute(
                select(PerformanceMetricMapping).where(
                    PerformanceMetricMapping.hwinfo_key == mapping_data["hwinfo_key"]
                )
            )
            if result.scalar_one_or_none():
                skipped += 1
                continue
            session.add(PerformanceMetricMapping(**mapping_data))
            added += 1
        await session.commit()
        print(f"Harmony 指标映射完成：新增 {added} 条，跳过 {skipped} 条")


if __name__ == "__main__":
    asyncio.run(init_harmony_metric_mapping())
