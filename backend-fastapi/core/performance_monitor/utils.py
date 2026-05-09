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
    result = {
        "cpu_usage": None,
        "gpu_usage": None,
        "commit_memory": None,
        "process_cpu": None,
        "process_gpu": None,
        "process_memory": None,
    }

    # 从 hwinfo_raw 提取系统指标（尝试多个键名）
    if hwinfo_raw:
        # CPU 使用率
        for key in ["CPU Total Usage", "CPU Total", "Total CPU Usage"]:
            if key in hwinfo_raw:
                value = hwinfo_raw[key].get("value")
                if value is not None:
                    result["cpu_usage"] = float(value)
                    break

        # GPU 使用率
        for key in ["GPU Core Usage", "GPU Usage", "GPU Total Usage"]:
            if key in hwinfo_raw:
                value = hwinfo_raw[key].get("value")
                if value is not None:
                    result["gpu_usage"] = float(value)
                    break

        # 提交内存
        for key in ["Commit Memory", "Commit Memory Total"]:
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