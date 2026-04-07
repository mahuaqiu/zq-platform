#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试报告工具函数
"""
import re
from typing import Optional, Tuple

from app.config import settings


def parse_task_base_name(task_name: str) -> str:
    """
    解析任务基础名称（去除日期后缀）

    示例：
    - "登录模块回归测试_2026-03-29" → "登录模块回归测试"
    - "支付模块测试_20260329" → "支付模块测试"
    - "订单测试-2026-03-29" → "订单测试"

    :param task_name: 任务名称
    :return: 任务基础名称
    """
    if not task_name:
        return task_name

    # 匹配常见日期后缀格式
    patterns = [
        r'[_\-\s]+\d{4}[-_]?\d{2}[-_]?\d{2}$',  # _2026-03-29, _20260329, -2026-03-29
        r'[_\-\s]+\d{4}年\d{1,2}月\d{1,2}日$',    # _2026年3月29日
    ]

    result = task_name
    for pattern in patterns:
        result = re.sub(pattern, '', result)

    return result.strip()


def calculate_pass_rate(total: int, fail: int) -> str:
    """
    计算通过率

    :param total: 用例总数
    :param fail: 失败数
    :return: 通过率字符串，如 "90%"
    """
    if total <= 0:
        return "0%"
    passed = total - fail
    rate = (passed / total) * 100
    return f"{rate:.1f}%".replace(".0%", "%")


def format_compare_change(change: Optional[int]) -> Tuple[str, str]:
    """
    格式化同比变化

    :param change: 变化值（正数上升，负数下降，None首次）
    :return: (显示文本, 颜色类)
    """
    if change is None:
        return "--", "text-gray-400"
    if change > 0:
        return f"↑{change}", "text-red-500"
    elif change < 0:
        return f"↓{abs(change)}", "text-green-500"
    else:
        return "→0", "text-gray-500"


def should_store_task(task_project_id: Optional[str]) -> bool:
    """
    检查任务是否应该存储

    根据聚合配置判断：
    - 空配置时存储所有任务
    - 有配置时只存储配置中的子任务
    - 无效参数返回 False（不存储）

    :param task_project_id: 任务项目ID
    :return: 是否应该存储该任务
    """
    # 边界情况：无效参数不存储
    if not task_project_id:
        return False

    aggregation_map = settings.task_aggregation_map
    all_sub_tasks = set()
    for sub_tasks in aggregation_map.values():
        all_sub_tasks.update(sub_tasks)

    if not all_sub_tasks:
        return True

    return task_project_id in all_sub_tasks