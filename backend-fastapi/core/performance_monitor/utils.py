#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控辅助函数
"""
from typing import Dict, Any, Optional, List


def extract_core_metrics(hwinfo_raw: Optional[Dict[str, Any]], target_processes: Optional[List[Dict[str, Any]]]) -> Dict[str, Optional[float]]:
    """
    从 hwinfo_raw 和进程数据中提取核心指标

    Args:
        hwinfo_raw: HWiNFO原始传感器数据（字典格式）
        target_processes: 目标进程列表

    Returns:
        包含核心指标的字典：cpu_usage, gpu_usage, commit_memory, process_cpu, process_gpu, process_memory
    """
    result: Dict[str, Optional[float]] = {
        "cpu_usage": None,
        "gpu_usage": None,
        "commit_memory": None,
        "process_cpu": None,
        "process_gpu": None,
        "process_memory": None,
    }

    # 从 hwinfo_raw 提取系统指标（尝试多个键名）
    if hwinfo_raw:
        # CPU 使用率 - 扩展匹配键名
        cpu_keys = [
            "CPU Total Usage",
            "CPU Total",
            "Total CPU Usage",
            "CPU Usage",
            "Total CPU",
            "CPU: Utilization",
            "CPU [#0]: Utilization",
        ]
        for key in cpu_keys:
            if key in hwinfo_raw:
                value = hwinfo_raw[key].get("value")
                if value is not None:
                    result["cpu_usage"] = float(value)
                    break

        # 如果标准键名都不存在，尝试计算所有核心的平均使用率
        if result["cpu_usage"] is None:
            core_usages = []
            for key in hwinfo_raw.keys():
                # 匹配 "Core X T0 Usage" 或 "Core X Usage" 格式
                if key.startswith("Core ") and ("Usage" in key or "Utility" in key):
                    value = hwinfo_raw[key].get("value")
                    if value is not None:
                        core_usages.append(float(value))
            if core_usages:
                # 取所有核心的平均值
                result["cpu_usage"] = sum(core_usages) / len(core_usages)

        # GPU 使用率 - 扩展匹配键名
        gpu_keys = [
            "GPU Core Usage",
            "GPU Usage",
            "GPU Total Usage",
            "GPU Core Load",
            "GPU Utilization",
            "GPU D3D Usage",
        ]
        for key in gpu_keys:
            if key in hwinfo_raw:
                value = hwinfo_raw[key].get("value")
                if value is not None:
                    result["gpu_usage"] = float(value)
                    break

        # 提交内存 - 扩展匹配键名
        commit_keys = [
            "Commit Memory",
            "Commit Memory Total",
            "Committed Memory",
            "Commit Total",
        ]
        for key in commit_keys:
            if key in hwinfo_raw:
                value = hwinfo_raw[key].get("value")
                unit = hwinfo_raw[key].get("unit", "MB")
                if value is not None:
                    # 根据单位转换（统一为 GB）
                    if unit == "MB":
                        result["commit_memory"] = float(value) / 1024
                    elif unit == "GB":
                        result["commit_memory"] = float(value)
                    else:
                        result["commit_memory"] = float(value)
                    break

    # 从进程数据汇总进程指标
    if target_processes:
        result["process_cpu"] = sum(float(p.get("total_cpu", 0)) for p in target_processes)
        result["process_gpu"] = sum(float(p.get("total_gpu", 0)) for p in target_processes)
        result["process_memory"] = sum(float(p.get("total_memory", 0)) for p in target_processes)

    return result