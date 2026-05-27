#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
初始化 Linux 性能指标映射数据
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from core.performance_monitor.model import PerformanceMetricMapping
from sqlalchemy import select


# Linux 指标映射数据
LINUX_METRIC_MAPPINGS = [
    {"hwinfo_key": "cpu_us", "display_name": "CPU用户态", "unit": "%", "category": "cpu", "is_primary": True, "sort": 1},
    {"hwinfo_key": "cpu_sy", "display_name": "CPU系统态", "unit": "%", "category": "cpu", "is_primary": True, "sort": 2},
    {"hwinfo_key": "cpu_id", "display_name": "CPU空闲", "unit": "%", "category": "cpu", "is_primary": True, "sort": 3},
    {"hwinfo_key": "cpu_wa", "display_name": "CPU等待IO", "unit": "%", "category": "cpu", "sort": 4},
    {"hwinfo_key": "cpu_hi", "display_name": "CPU硬件中断", "unit": "%", "category": "cpu", "sort": 5},
    {"hwinfo_key": "cpu_si", "display_name": "CPU软件中断", "unit": "%", "category": "cpu", "sort": 6},
    {"hwinfo_key": "cpu_st", "display_name": "CPU虚拟化偷取", "unit": "%", "category": "cpu", "sort": 7},
    {"hwinfo_key": "cpu_ni", "display_name": "CPU优先级进程", "unit": "%", "category": "cpu", "sort": 8},
    {"hwinfo_key": "mem_total", "display_name": "内存总量", "unit": "MiB", "category": "memory", "is_primary": True, "sort": 10},
    {"hwinfo_key": "mem_free", "display_name": "内存空闲", "unit": "MiB", "category": "memory", "is_primary": True, "sort": 11},
    {"hwinfo_key": "mem_used", "display_name": "内存使用", "unit": "MiB", "category": "memory", "is_primary": True, "sort": 12},
    {"hwinfo_key": "mem_buff_cache", "display_name": "内存缓冲缓存", "unit": "MiB", "category": "memory", "sort": 13},
    {"hwinfo_key": "swap_total", "display_name": "Swap总量", "unit": "MiB", "category": "swap", "sort": 20},
    {"hwinfo_key": "swap_free", "display_name": "Swap空闲", "unit": "MiB", "category": "swap", "sort": 21},
    {"hwinfo_key": "swap_used", "display_name": "Swap使用", "unit": "MiB", "category": "swap", "sort": 22},
    {"hwinfo_key": "swap_avail_mem", "display_name": "可用内存", "unit": "MiB", "category": "swap", "sort": 23},
]


async def init_linux_metric_mapping():
    """初始化 Linux 指标映射"""
    async with AsyncSessionLocal() as db:
        added_count = 0
        skipped_count = 0

        for mapping_data in LINUX_METRIC_MAPPINGS:
            # 检查是否已存在
            stmt = select(PerformanceMetricMapping).where(
                PerformanceMetricMapping.hwinfo_key == mapping_data["hwinfo_key"]
            )
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                skipped_count += 1
                print(f"跳过已存在: {mapping_data['hwinfo_key']}")
                continue

            # 创建新映射
            mapping = PerformanceMetricMapping(**mapping_data)
            db.add(mapping)
            added_count += 1
            print(f"添加: {mapping_data['hwinfo_key']} -> {mapping_data['display_name']}")

        await db.commit()
        print(f"\n完成: 添加 {added_count} 条，跳过 {skipped_count} 条")


if __name__ == "__main__":
    asyncio.run(init_linux_metric_mapping())