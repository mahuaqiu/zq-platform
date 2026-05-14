#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控辅助函数
"""
from typing import Dict, Any, Optional, List


def extract_core_metrics(
    hwinfo_raw: Optional[Dict[str, Any]],
    aggregated: Optional[List[Dict[str, Any]]]
) -> Dict[str, Optional[float]]:
    """
    从 hwinfo_raw 和 aggregated 汇总数据中提取核心指标

    Args:
        hwinfo_raw: HWiNFO原始传感器数据（字典格式）
        aggregated: 目标进程汇总列表（v0.3.1 新字段）

    Returns:
        包含核心指标的字典：
        - cpu_usage: 系统CPU使用率（从 hwinfo_raw "Total CPU Usage" 取）
        - gpu_usage: 系统GPU使用率（从 hwinfo_raw "GPU D3D Usage" 取）
        - process_cpu: 进程总CPU使用率（从 aggregated 汇总）
        - process_gpu: 进程总GPU使用率（从 aggregated 汇总）
        - process_memory: 进程总物理内存 MB（从 aggregated 汇总）
        - process_committed_memory: 进程总虚拟内存 MB（从 aggregated 汇总）
    """
    result: Dict[str, Optional[float]] = {
        "cpu_usage": None,
        "gpu_usage": None,
        "process_cpu": None,
        "process_gpu": None,
        "process_memory": None,
        "process_committed_memory": None,
    }

    # 从 hwinfo_raw 提取系统指标
    if hwinfo_raw:
        # 系统CPU使用率 - 使用 "Total CPU Usage"
        if "Total CPU Usage" in hwinfo_raw:
            value = hwinfo_raw["Total CPU Usage"].get("value")
            if value is not None:
                result["cpu_usage"] = float(value)

        # 系统GPU使用率 - 使用 "GPU D3D Usage"
        if "GPU D3D Usage" in hwinfo_raw:
            value = hwinfo_raw["GPU D3D Usage"].get("value")
            if value is not None:
                result["gpu_usage"] = float(value)

    # 从 aggregated 汇总进程指标
    if aggregated:
        total_cpu = 0.0
        total_gpu = 0.0
        total_memory = 0.0
        total_committed = 0.0

        for proc in aggregated:
            total_cpu += float(proc.get("cpu_percent_total", 0))
            total_gpu += float(proc.get("gpu_percent_total", 0))
            total_memory += float(proc.get("working_set_mb_total", 0))
            total_committed += float(proc.get("committed_memory_mb_total", 0))

        result["process_cpu"] = total_cpu
        result["process_gpu"] = total_gpu
        result["process_memory"] = total_memory
        result["process_committed_memory"] = total_committed

    return result


def convert_aggregated_to_target_processes(
    aggregated: Optional[List[Dict[str, Any]]],
    processes: Optional[List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """
    将 v0.3.1 的 aggregated/processes 转换为旧版本的 target_processes 格式
    用于前端兼容显示

    Args:
        aggregated: 进程汇总列表
        processes: 进程实例列表

    Returns:
        旧版本格式的 target_processes 列表：
        [
            {
                "name": "进程名",
                "total_cpu": 总CPU使用率,
                "total_gpu": 总GPU使用率,
                "total_memory": 总物理内存 MB,
                "total_committed_memory": 总虚拟内存 MB,
                "instances": [
                    {"pid": PID, "cpu": CPU使用率, "memory": 物理内存MB, "gpu": GPU使用率, "committed_memory": 虚拟内存MB}
                ]
            }
        ]
    """
    if not aggregated:
        return []

    # 按 name 构建 instances 映射
    instances_map: Dict[str, List[Dict[str, Any]]] = {}
    if processes:
        for p in processes:
            name = p.get("name", "")
            if name not in instances_map:
                instances_map[name] = []
            instances_map[name].append({
                "pid": p.get("pid", 0),
                "cpu": p.get("cpu_percent", 0),
                "memory": p.get("working_set_mb", 0),
                "gpu": p.get("gpu_percent", 0),
                "committed_memory": p.get("committed_memory_mb", 0),
            })

    # 构建 target_processes 格式
    result = []
    for agg in aggregated:
        name = agg.get("name", "")
        proc_data = {
            "name": name,
            "total_cpu": agg.get("cpu_percent_total", 0),
            "total_gpu": agg.get("gpu_percent_total", 0),
            "total_memory": agg.get("working_set_mb_total", 0),
            "total_committed_memory": agg.get("committed_memory_mb_total", 0),
            "instances": instances_map.get(name, []),
        }
        result.append(proc_data)

    return result


def convert_top_n_to_top10(
    top_n: Optional[List[Dict[str, Any]]],
    metric_type: str = "cpu"
) -> List[Dict[str, Any]]:
    """
    将 v0.3.1 的 top_n_cpu/top_n_gpu 转换为旧版本的 top10_cpu/top10_gpu 格式

    Args:
        top_n: Top N 进程列表
        metric_type: 指标类型 "cpu" 或 "gpu"

    Returns:
        旧版本格式的 top10 列表：
        [{"name": "进程名", "cpu": CPU使用率 或 "gpu": GPU使用率}]
    """
    if not top_n:
        return []

    result = []
    for p in top_n:
        item = {"name": p.get("name", "")}
        if metric_type == "cpu":
            item["cpu"] = p.get("cpu_percent", 0)
        else:
            item["gpu"] = p.get("gpu_percent", 0)
        result.append(item)

    return result