#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File: version.py
@Desc: 版本号比较工具 - 分段数值比较

直接用字符串比较版本号会出现 "10.0" < "9.0" 的错误排序，
这里把版本号按 . _ - + 分隔后逐段比较：数字段按数值比较，
非数字段按字符串比较，缺失的段视为 0（例如 1.2 vs 1.2.0 相等）。
"""
import re
from typing import List, Tuple

# 每段统一表示为 (类型序, 数值, 字符串)，可直接元组比较：
# 数字段类型序为 1，非数字段（预发布标识如 rc/beta）为 0，
# 使预发布版本排在正式版之前（1.0.0-rc1 < 1.0.0）
_VersionSegment = Tuple[int, int, str]

# 缺失段的填充值：低于任何数字段（数值位为 0）、高于预发布段（类型序为 1）
_PAD_SEGMENT: _VersionSegment = (1, 0, "")


def _version_key(version: str) -> List[_VersionSegment]:
    """把版本号转换为可逐段比较的 key 列表"""
    key: List[_VersionSegment] = []
    for part in re.split(r"[._\-+]", str(version).strip()):
        if part.isdigit():
            key.append((1, int(part), ""))
        elif part:
            key.append((0, 0, part))
    return key


def compare_versions(left: str, right: str) -> int:
    """
    比较两个版本号

    Args:
        left: 版本号，如 "9.0"、"10.1.2"
        right: 版本号

    Returns:
        int: left > right 返回 1，相等返回 0，left < right 返回 -1

    Examples:
        >>> compare_versions("10.0", "9.0")
        1
        >>> compare_versions("1.2.3", "1.2.10")
        -1
        >>> compare_versions("1.2", "1.2.0")
        0
    """
    left_key = _version_key(left)
    right_key = _version_key(right)

    width = max(len(left_key), len(right_key))
    left_key += [_PAD_SEGMENT] * (width - len(left_key))
    right_key += [_PAD_SEGMENT] * (width - len(right_key))

    if left_key > right_key:
        return 1
    if left_key < right_key:
        return -1
    return 0
