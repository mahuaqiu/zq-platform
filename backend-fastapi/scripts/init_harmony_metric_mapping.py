#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""初始化/升级 Harmony 性能指标映射（perfharmony 0.2.0，SP_daemon 白名单制）。

脚本是幂等的，适合在部署后重复执行：
- 新键不存在则插入；
- 已存在则刷新中文别名/单位/分类/排序（0.2.0 系统内存单位由 MB 改为 GB）；
- 0.2.0 已下线的旧键（磁盘 IO、估算功耗、CPU 温度、GPU Usage、旧网络键）软删除。

逐核主频 Harmony CPU{n} Freq 核数随设备动态变化，不在此预注册，
前端按模式匹配翻译（CPU{n} 主频 / MHz）。
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import AsyncSessionLocal
from core.performance_monitor.model import PerformanceMetricMapping


# 键名/单位与 perfharmony src/parse/sp_daemon.rs 白名单一一对应。
HARMONY_METRIC_MAPPINGS = [
    # CPU（%、MHz）
    {"hwinfo_key": "Harmony CPU Usage", "display_name": "系统 CPU 使用率", "unit": "%", "category": "harmony_cpu", "is_primary": True, "sort": 1},
    {"hwinfo_key": "Harmony CPU User", "display_name": "CPU 用户态", "unit": "%", "category": "harmony_cpu", "is_primary": True, "sort": 2},
    {"hwinfo_key": "Harmony CPU System", "display_name": "CPU 系统态", "unit": "%", "category": "harmony_cpu", "is_primary": True, "sort": 3},
    {"hwinfo_key": "Harmony CPU Idle", "display_name": "CPU 空闲", "unit": "%", "category": "harmony_cpu", "is_primary": False, "sort": 4},
    {"hwinfo_key": "Harmony CPU Freq Avg", "display_name": "CPU 平均主频", "unit": "MHz", "category": "harmony_cpu", "is_primary": False, "sort": 5},
    # 内存（系统内存统一 GB）
    {"hwinfo_key": "Harmony Mem Total", "display_name": "内存总量", "unit": "GB", "category": "harmony_memory", "is_primary": True, "sort": 10},
    {"hwinfo_key": "Harmony Mem Used", "display_name": "内存使用（总内存−可用内存）", "unit": "GB", "category": "harmony_memory", "is_primary": True, "sort": 11},
    {"hwinfo_key": "Harmony Mem Available", "display_name": "内存可用", "unit": "GB", "category": "harmony_memory", "is_primary": True, "sort": 12},
    {"hwinfo_key": "Harmony DDR Freq", "display_name": "DDR 内存频率", "unit": "MHz", "category": "harmony_memory", "is_primary": False, "sort": 13},
    # GPU（%、MHz）
    {"hwinfo_key": "Harmony GPU Load", "display_name": "GPU 负载", "unit": "%", "category": "harmony_gpu", "is_primary": True, "sort": 20},
    {"hwinfo_key": "Harmony GPU Freq", "display_name": "GPU 频率", "unit": "MHz", "category": "harmony_gpu", "is_primary": False, "sort": 21},
    # 温度（°C）
    {"hwinfo_key": "Harmony Battery Temp", "display_name": "电池温度", "unit": "°C", "category": "harmony_thermal", "is_primary": False, "sort": 40},
    {"hwinfo_key": "Harmony SoC Temp", "display_name": "SoC 温度", "unit": "°C", "category": "harmony_thermal", "is_primary": False, "sort": 41},
    {"hwinfo_key": "Harmony Shell Front Temp", "display_name": "壳温（前面板）", "unit": "°C", "category": "harmony_thermal", "is_primary": False, "sort": 42},
    {"hwinfo_key": "Harmony Shell Back Temp", "display_name": "壳温（后面板）", "unit": "°C", "category": "harmony_thermal", "is_primary": False, "sort": 43},
    {"hwinfo_key": "Harmony Shell Frame Temp", "display_name": "壳温（边框）", "unit": "°C", "category": "harmony_thermal", "is_primary": False, "sort": 44},
    {"hwinfo_key": "Harmony System Temp", "display_name": "系统温度", "unit": "°C", "category": "harmony_thermal", "is_primary": False, "sort": 45},
    # 电池（mA，绝对值，符号仅表示充放电方向）
    {"hwinfo_key": "Harmony Battery Current", "display_name": "电池电流", "unit": "mA", "category": "harmony_power", "is_primary": False, "sort": 50},
    # 网络（KB/s）
    {"hwinfo_key": "Harmony Net Up", "display_name": "网络上行速率", "unit": "KB/s", "category": "harmony_network", "is_primary": False, "sort": 60},
    {"hwinfo_key": "Harmony Net Down", "display_name": "网络下行速率", "unit": "KB/s", "category": "harmony_network", "is_primary": False, "sort": 61},
    # 显示（帧率/刷新率）
    {"hwinfo_key": "Harmony FPS", "display_name": "实时帧率", "unit": "fps", "category": "harmony_display", "is_primary": False, "sort": 70},
    {"hwinfo_key": "Harmony Refresh Rate", "display_name": "屏幕刷新率", "unit": "Hz", "category": "harmony_display", "is_primary": False, "sort": 71},
]

# 0.2.0 已下线的旧键（SP_daemon 不提供或键名变更），软删除避免前端继续显示。
OBSOLETE_HWINFO_KEYS = [
    "Harmony Net Upload",
    "Harmony Net Download",
    "Harmony Disk Read",
    "Harmony Disk Write",
    "Harmony Power",
    "Harmony CPU Temp",
    "Harmony GPU Usage",
]


async def init_harmony_metric_mapping() -> None:
    """写入/刷新 Harmony 0.2.0 指标键，软删除旧键。"""
    async with AsyncSessionLocal() as session:
        added = 0
        updated = 0
        for mapping_data in HARMONY_METRIC_MAPPINGS:
            result = await session.execute(
                select(PerformanceMetricMapping).where(
                    PerformanceMetricMapping.hwinfo_key == mapping_data["hwinfo_key"]
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.display_name = mapping_data["display_name"]
                existing.unit = mapping_data["unit"]
                existing.category = mapping_data["category"]
                existing.is_primary = mapping_data["is_primary"]
                existing.sort = mapping_data["sort"]
                existing.is_deleted = False
                updated += 1
                continue
            session.add(PerformanceMetricMapping(**mapping_data))
            added += 1

        removed = 0
        for obsolete_key in OBSOLETE_HWINFO_KEYS:
            result = await session.execute(
                select(PerformanceMetricMapping).where(
                    PerformanceMetricMapping.hwinfo_key == obsolete_key,
                    PerformanceMetricMapping.is_deleted == False,  # noqa: E712
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.is_deleted = True
                removed += 1

        await session.commit()
        print(f"Harmony 指标映射完成：新增 {added} 条，刷新 {updated} 条，下线 {removed} 条")


if __name__ == "__main__":
    asyncio.run(init_harmony_metric_mapping())
