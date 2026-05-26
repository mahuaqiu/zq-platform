#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Linux 性能采集模块

提供 SSH 连接池管理和 Linux 设备性能数据采集功能。
使用 vmstat 和 free 命令采集 CPU 和内存指标。
"""
import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable

import paramiko
from paramiko import SSHClient, AutoAddPolicy

logger = logging.getLogger(__name__)


# ===== SSH 连接池配置 =====
CONNECT_TIMEOUT = 5  # SSH 连接超时（秒）
COMMAND_TIMEOUT = 10  # 命令执行超时（秒）
MAX_RETRIES = 2  # 最大重试次数
MAX_CONNECTIONS = 10  # 最大并发连接数


class SSHConnectionPool:
    """
    SSH 连接池管理类

    维护 SSH 长连接，支持连接复用、自动重连和并发限制。
    """

    def __init__(self):
        # 活跃连接存储: {device_id: SSHClient}
        self._connections: Dict[str, SSHClient] = {}
        # 线程锁，保护并发访问
        self._lock = threading.Lock()
        # 认证信息缓存: {device_id: {"host": str, "port": int, "account": str, "password": str}}
        self._auth_cache: Dict[str, Dict[str, Any]] = {}

    def get_connection(
        self,
        device_id: str,
        host: str,
        port: int,
        account: str,
        password: str
    ) -> SSHClient:
        """
        获取或创建 SSH 连接

        Args:
            device_id: 设备ID
            host: SSH 主机地址
            port: SSH 端口
            account: SSH 账号
            password: SSH 密码

        Returns:
            SSHClient 实例

        Raises:
            Exception: 连接失败时抛出异常
        """
        with self._lock:
            # 检查并发限制
            if len(self._connections) >= MAX_CONNECTIONS and device_id not in self._connections:
                raise Exception(f"SSH 连接池已满（最大 {MAX_CONNECTIONS} 个连接）")

            # 缓存认证信息（用于重连）
            self.cache_auth(device_id, host, port, account, password)

            # 检查是否已有连接
            if device_id in self._connections:
                client = self._connections[device_id]
                # 验证连接有效性
                if self._is_connection_valid(client):
                    return client
                else:
                    # 连接失效，关闭并重新连接
                    logger.warning(f"设备 {device_id} SSH 连接失效，尝试重连...")
                    self._close_client(client)
                    del self._connections[device_id]

            # 创建新连接
            client = self._create_connection(host, port, account, password)
            self._connections[device_id] = client
            logger.info(f"设备 {device_id} SSH 连接建立成功: {host}:{port}")
            return client

    def _create_connection(
        self,
        host: str,
        port: int,
        account: str,
        password: str
    ) -> SSHClient:
        """
        创建新的 SSH 连接（带重试）

        Args:
            host: SSH 主机地址
            port: SSH 端口
            account: SSH 账号
            password: SSH 密码

        Returns:
            SSHClient 实例

        Raises:
            Exception: 重试失败后抛出异常
        """
        last_exception = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                client = SSHClient()
                client.set_missing_host_key_policy(AutoAddPolicy())
                client.connect(
                    hostname=host,
                    port=port,
                    username=account,
                    password=password,
                    timeout=CONNECT_TIMEOUT,
                    allow_agent=False,
                    look_for_keys=False
                )
                return client
            except Exception as e:
                last_exception = e
                logger.warning(f"SSH 连接失败（第 {attempt}/{MAX_RETRIES} 次）: {host}:{port} - {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(1)  # 重试间隔

        raise Exception(f"SSH 连接失败（已重试 {MAX_RETRIES} 次）: {last_exception}")

    def _is_connection_valid(self, client: SSHClient) -> bool:
        """
        检查 SSH 连接是否有效

        Args:
            client: SSHClient 实例

        Returns:
            True if valid, False otherwise
        """
        try:
            # 执行简单命令测试连接
            transport = client.get_transport()
            if transport is None or not transport.is_active():
                return False
            # 发送心跳包
            transport.send_ignore()
            return True
        except Exception:
            return False

    def cache_auth(
        self,
        device_id: str,
        host: str,
        port: int,
        account: str,
        password: str
    ) -> None:
        """
        缓存认证信息（用于重连）

        Args:
            device_id: 设备ID
            host: SSH 主机地址
            port: SSH 端口
            account: SSH 账号
            password: SSH 密码
        """
        self._auth_cache[device_id] = {
            "host": host,
            "port": port,
            "account": account,
            "password": password
        }

    def reconnect(self, device_id: str) -> Optional[SSHClient]:
        """
        重连指定设备

        Args:
            device_id: 设备ID

        Returns:
            SSHClient 实例，如果无认证缓存则返回 None
        """
        with self._lock:
            auth = self._auth_cache.get(device_id)
            if not auth:
                logger.warning(f"设备 {device_id} 无认证缓存，无法重连")
                return None

            # 关闭旧连接
            if device_id in self._connections:
                self._close_client(self._connections[device_id])
                del self._connections[device_id]

            # 创建新连接
            try:
                client = self._create_connection(
                    auth["host"],
                    auth["port"],
                    auth["account"],
                    auth["password"]
                )
                self._connections[device_id] = client
                logger.info(f"设备 {device_id} SSH 重连成功")
                return client
            except Exception as e:
                logger.error(f"设备 {device_id} SSH 重连失败: {e}")
                return None

    def close_connection(self, device_id: str) -> bool:
        """
        关闭指定设备的连接

        Args:
            device_id: 设备ID

        Returns:
            True if closed, False if not found
        """
        with self._lock:
            if device_id in self._connections:
                self._close_client(self._connections[device_id])
                del self._connections[device_id]
                logger.info(f"设备 {device_id} SSH 连接已关闭")
                return True
            return False

    def close_all(self) -> None:
        """
        关闭所有连接
        """
        with self._lock:
            for device_id, client in self._connections.items():
                self._close_client(client)
                logger.info(f"设备 {device_id} SSH 连接已关闭")
            self._connections.clear()

    def _close_client(self, client: SSHClient) -> None:
        """
        关闭单个 SSH 客户端

        Args:
            client: SSHClient 实例
        """
        try:
            client.close()
        except Exception as e:
            logger.warning(f"关闭 SSH 连接时出错: {e}")

    def is_connected(self, device_id: str) -> bool:
        """
        检查指定设备是否有活跃连接

        Args:
            device_id: 设备ID

        Returns:
            True if connected, False otherwise
        """
        with self._lock:
            if device_id not in self._connections:
                return False
            return self._is_connection_valid(self._connections[device_id])


class LinuxDataCollector:
    """
    Linux 数据采集类

    直接读取 /proc/stat 和 /proc/meminfo 文件采集性能数据。
    毫秒级采集，无需等待采样时间。
    """

    # 缓存上次 CPU 累计值，用于计算瞬时使用率
    _last_cpu_stats: Dict[str, Dict[str, float]] = {}
    _cpu_lock = threading.Lock()

    @staticmethod
    def parse_proc_stat(output: str, device_id: str) -> Dict[str, float]:
        """
        解析 /proc/stat 输出，计算 CPU 使用率

        /proc/stat 第一行格式：
        cpu  user nice system idle iowait irq softirq steal guest guest_nice
        cpu  123456 789 45678 987654 1234 567 890 123 45 67 89

        通过两次读取的差值计算瞬时 CPU 使用率

        Args:
            output: /proc/stat 内容
            device_id: 设备ID（用于缓存状态）

        Returns:
            CPU 指标字典：
            - cpu_us: 用户空间 CPU 使用率 %
            - cpu_sy: 内核空间 CPU 使用率 %
            - cpu_id: CPU 空闲率 %
            - cpu_wa: IO 等待 CPU 使用率 %
            - cpu_st: 虚拟化开销 CPU 使用率 %
            - cpu_hi: 硬中断 CPU 使用率 %
            - cpu_si: 软中断 CPU 使用率 %
            - cpu_ni: 低优先级用户进程 CPU 使用率 %
        """
        result = {
            "cpu_us": 0.0,
            "cpu_sy": 0.0,
            "cpu_id": 0.0,
            "cpu_wa": 0.0,
            "cpu_st": 0.0,
            "cpu_hi": 0.0,
            "cpu_si": 0.0,
            "cpu_ni": 0.0,
        }

        lines = output.strip().split('\n')
        if not lines:
            logger.warning(f"/proc/stat 输出为空")
            return result

        # 找到第一行 cpu 数据
        cpu_line = None
        for line in lines:
            if line.startswith('cpu '):
                cpu_line = line
                break

        if not cpu_line:
            logger.warning(f"/proc/stat 未找到 cpu 行")
            return result

        # 解析数据：cpu  user nice system idle iowait irq softirq steal guest guest_nice
        parts = cpu_line.split()
        if len(parts) < 8:
            logger.warning(f"/proc/stat cpu 行数据不足: {cpu_line}")
            return result

        try:
            # 累计值（单位：USER_HZ，通常为 1/100 秒）
            user = float(parts[1])      # user
            nice = float(parts[2])      # nice
            system = float(parts[3])    # system
            idle = float(parts[4])      # idle
            iowait = float(parts[5]) if len(parts) > 5 else 0.0   # iowait
            irq = float(parts[6]) if len(parts) > 6 else 0.0      # irq (硬中断)
            softirq = float(parts[7]) if len(parts) > 7 else 0.0  # softirq (软中断)
            steal = float(parts[8]) if len(parts) > 8 else 0.0    # steal

            # 当前累计值
            current_stats = {
                "user": user,
                "nice": nice,
                "system": system,
                "idle": idle,
                "iowait": iowait,
                "irq": irq,
                "softirq": softirq,
                "steal": steal,
            }

            # 计算总时间
            total = user + nice + system + idle + iowait + irq + softirq + steal

            with LinuxDataCollector._cpu_lock:
                # 获取上次累计值
                last_stats = LinuxDataCollector._last_cpu_stats.get(device_id)

                if last_stats:
                    # 计算差值（瞬时使用率）
                    delta_total = total - sum(last_stats.values())
                    if delta_total > 0:
                        delta_user = user - last_stats["user"]
                        delta_nice = nice - last_stats["nice"]
                        delta_system = system - last_stats["system"]
                        delta_idle = idle - last_stats["idle"]
                        delta_iowait = iowait - last_stats["iowait"]
                        delta_irq = irq - last_stats["irq"]
                        delta_softirq = softirq - last_stats["softirq"]
                        delta_steal = steal - last_stats["steal"]

                        # 计算百分比
                        result["cpu_us"] = (delta_user + delta_nice) / delta_total * 100  # user + nice
                        result["cpu_sy"] = delta_system / delta_total * 100
                        result["cpu_id"] = delta_idle / delta_total * 100
                        result["cpu_wa"] = delta_iowait / delta_total * 100
                        result["cpu_hi"] = delta_irq / delta_total * 100
                        result["cpu_si"] = delta_softirq / delta_total * 100
                        result["cpu_st"] = delta_steal / delta_total * 100
                        result["cpu_ni"] = delta_nice / delta_total * 100

                # 更新缓存
                LinuxDataCollector._last_cpu_stats[device_id] = current_stats

        except (ValueError, KeyError) as e:
            logger.warning(f"/proc/stat 解析失败: {e}")

        return result

    @staticmethod
    def parse_proc_meminfo(output: str) -> Dict[str, float]:
        """
        解析 /proc/meminfo 输出，提取内存指标

        /proc/meminfo 格式示例：
        MemTotal:        7982340 kB
        MemFree:         1234567 kB
        MemAvailable:    6543210 kB
        Buffers:          123456 kB
        Cached:          567890 kB
        SwapTotal:       2048000 kB
        SwapFree:        2048000 kB

        Args:
            output: /proc/meminfo 内容

        Returns:
            内存指标字典（单位：MB）：
            - mem_total: 总内存
            - mem_free: 空闲内存
            - mem_available: 可用内存
            - mem_buffers: buffers 内存
            - mem_cached: cached 内存
            - swap_total: 总 Swap
            - swap_free: 空闲 Swap
        """
        result = {
            "mem_total": 0.0,
            "mem_free": 0.0,
            "mem_available": 0.0,
            "mem_buffers": 0.0,
            "mem_cached": 0.0,
            "swap_total": 0.0,
            "swap_free": 0.0,
        }

        lines = output.strip().split('\n')
        if not lines:
            logger.warning(f"/proc/meminfo 输出为空")
            return result

        for line in lines:
            parts = line.split()
            if len(parts) < 2:
                continue

            key = parts[0].rstrip(':')
            try:
                # 值单位为 kB，转换为 MB
                value_kb = float(parts[1])
                value_mb = value_kb / 1024

                if key == "MemTotal":
                    result["mem_total"] = value_mb
                elif key == "MemFree":
                    result["mem_free"] = value_mb
                elif key == "MemAvailable":
                    result["mem_available"] = value_mb
                elif key == "Buffers":
                    result["mem_buffers"] = value_mb
                elif key == "Cached":
                    result["mem_cached"] = value_mb
                elif key == "SwapTotal":
                    result["swap_total"] = value_mb
                elif key == "SwapFree":
                    result["swap_free"] = value_mb
            except ValueError as e:
                logger.warning(f"/proc/meminfo 解析失败: {line} - {e}")

        return result

    @staticmethod
    def execute_command(client: SSHClient, command: str) -> str:
        """
        执行 SSH 命令

        Args:
            client: SSHClient 实例
            command: 要执行的命令

        Returns:
            命令输出字符串

        Raises:
            Exception: 命令执行失败
        """
        try:
            stdin, stdout, stderr = client.exec_command(command, timeout=COMMAND_TIMEOUT)
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')

            if error and not output:
                raise Exception(f"命令执行错误: {error}")

            return output
        except Exception as e:
            raise Exception(f"命令执行失败: {e}")

    @classmethod
    def collect(cls, client: SSHClient, device_id: str = "default") -> Dict[str, Any]:
        """
        执行采集，返回结构化数据

        直接读取 /proc/stat 和 /proc/meminfo，毫秒级采集

        Args:
            client: SSHClient 实例
            device_id: 设备ID（用于缓存 CPU 状态，计算瞬时使用率）

        Returns:
            采集数据字典：
            - cpu_usage: CPU 使用率（us + sy）%
            - gpu_usage: None（Linux 不采集 GPU）
            - memory_usage: 内存使用量 GB（mem_total - mem_available）
            - commit_memory: 0（Linux 不区分提交内存）
            - hwinfo_raw: 扁平化的原始数据

        Raises:
            Exception: 采集失败
        """
        # 直接读取 /proc/stat（毫秒级）
        stat_output = cls.execute_command(client, "cat /proc/stat")
        cpu_metrics = cls.parse_proc_stat(stat_output, device_id)

        # 直接读取 /proc/meminfo（毫秒级）
        meminfo_output = cls.execute_command(client, "cat /proc/meminfo")
        mem_metrics = cls.parse_proc_meminfo(meminfo_output)

        # 计算综合指标
        # CPU 使用率 = us + sy（用户 + 内核）
        cpu_usage = cpu_metrics['cpu_us'] + cpu_metrics['cpu_sy']

        # 内存使用量（GB）= 总内存 - 可用内存
        memory_usage_mb = mem_metrics['mem_total'] - mem_metrics['mem_available']
        memory_usage_gb = memory_usage_mb / 1024

        # 构建 hwinfo_raw（扁平化格式，兼容现有结构）
        hwinfo_raw = {}

        # CPU 指标（百分比）
        hwinfo_raw["Linux CPU User"] = {"value": cpu_metrics['cpu_us'], "unit": "%"}
        hwinfo_raw["Linux CPU System"] = {"value": cpu_metrics['cpu_sy'], "unit": "%"}
        hwinfo_raw["Linux CPU Idle"] = {"value": cpu_metrics['cpu_id'], "unit": "%"}
        hwinfo_raw["Linux CPU Wait"] = {"value": cpu_metrics['cpu_wa'], "unit": "%"}
        hwinfo_raw["Linux CPU Steal"] = {"value": cpu_metrics['cpu_st'], "unit": "%"}
        hwinfo_raw["Linux CPU Hi"] = {"value": cpu_metrics['cpu_hi'], "unit": "%"}
        hwinfo_raw["Linux CPU Si"] = {"value": cpu_metrics['cpu_si'], "unit": "%"}
        hwinfo_raw["Linux CPU Nice"] = {"value": cpu_metrics['cpu_ni'], "unit": "%"}
        hwinfo_raw["Linux CPU Usage"] = {"value": cpu_usage, "unit": "%"}

        # 内存指标（MB）
        hwinfo_raw["Linux Memory Total"] = {"value": mem_metrics['mem_total'], "unit": "MB"}
        hwinfo_raw["Linux Memory Free"] = {"value": mem_metrics['mem_free'], "unit": "MB"}
        hwinfo_raw["Linux Memory Available"] = {"value": mem_metrics['mem_available'], "unit": "MB"}
        hwinfo_raw["Linux Memory Buffers"] = {"value": mem_metrics['mem_buffers'], "unit": "MB"}
        hwinfo_raw["Linux Memory Cached"] = {"value": mem_metrics['mem_cached'], "unit": "MB"}
        hwinfo_raw["Linux Memory Usage"] = {"value": memory_usage_mb, "unit": "MB"}

        # Swap 指标（MB）
        hwinfo_raw["Linux Swap Total"] = {"value": mem_metrics['swap_total'], "unit": "MB"}
        hwinfo_raw["Linux Swap Free"] = {"value": mem_metrics['swap_free'], "unit": "MB"}
        hwinfo_raw["Linux Swap Used"] = {"value": mem_metrics['swap_total'] - mem_metrics['swap_free'], "unit": "MB"}

        return {
            "cpu_usage": cpu_usage,
            "gpu_usage": None,  # Linux 不采集 GPU
            "memory_usage": memory_usage_gb,
            "commit_memory": 0,  # Linux 不区分提交内存
            "hwinfo_raw": hwinfo_raw,
        }


# ===== 全局连接池实例 =====
ssh_pool = SSHConnectionPool()


# ===== 后台采集任务管理 =====
# 采集任务存储: {device_id: {"task": asyncio.Task, "collect_id": str, "running": bool}}
_collect_tasks: Dict[str, Dict[str, Any]] = {}
# 任务锁
_task_lock = threading.Lock()


def start_linux_collect_task(
    device_id: str,
    collect_id: str,
    interval: int,
    db_session_factory: Callable,
    ssh_auth: Dict[str, Any],
    timeout: int = 43200  # 最大采集时间（秒），默认12小时
) -> bool:
    """
    启动 Linux 后台采集任务

    Args:
        device_id: 设备ID
        collect_id: 采集记录ID
        interval: 采集间隔（秒）
        db_session_factory: 数据库会话工厂函数
        ssh_auth: SSH 认证信息 {"host": str, "port": int, "account": str, "password": str}

    Returns:
        True if started, False if already running
    """
    with _task_lock:
        # 检查是否已有任务运行
        if device_id in _collect_tasks and _collect_tasks[device_id]["running"]:
            logger.warning(f"设备 {device_id} 已有采集任务运行")
            return False

        # 创建采集任务
        async def collect_loop():
            """采集循环"""
            from app.database import AsyncSessionLocal
            from core.performance_monitor.model import PerformanceCollect, PerformanceData
            from sqlalchemy import select

            start_time_utc = datetime.now(timezone.utc)
            start_time_naive = start_time_utc.replace(tzinfo=None)

            try:
                # 建立 SSH 连接
                client = ssh_pool.get_connection(
                    device_id,
                    ssh_auth["host"],
                    ssh_auth["port"],
                    ssh_auth["account"],
                    ssh_auth["password"]
                )

                relative_time = 0
                retry_count = 0

                while _collect_tasks.get(device_id, {}).get("running", False):
                    # 检查是否超时
                    if relative_time >= timeout:
                        logger.info(f"设备 {device_id} 采集达到最大时间 {timeout} 秒，自动停止")
                        await stop_collect_in_db(collect_id, "stopped")
                        break

                    try:
                        # 采集数据（传入 device_id 用于缓存 CPU 状态）
                        data = LinuxDataCollector.collect(client, device_id)

                        # 存储到数据库
                        async with AsyncSessionLocal() as db:
                            # 创建 PerformanceData 记录
                            perf_data = PerformanceData(
                                collect_id=collect_id,
                                timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
                                relative_time=relative_time,
                                cpu_usage=data["cpu_usage"],
                                gpu_usage=data["gpu_usage"],
                                memory_usage=data["memory_usage"],
                                commit_memory=data["commit_memory"],
                                process_handles=None,  # Linux 不采集进程句柄
                                target_processes=None,
                                top10_cpu=None,
                                top10_gpu=None,
                                hwinfo_raw=data["hwinfo_raw"],
                            )
                            db.add(perf_data)
                            await db.commit()

                        logger.info(f"设备 {device_id} 采集成功: CPU={data['cpu_usage']}%, Mem={data['memory_usage']}GB")
                        retry_count = 0  # 成功后重置重试计数

                    except Exception as e:
                        retry_count += 1
                        logger.error(f"设备 {device_id} 采集失败（第 {retry_count} 次）: {e}")

                        if retry_count >= MAX_RETRIES:
                            # 尝试重连 SSH
                            logger.warning(f"设备 {device_id} 达到最大重试次数，尝试 SSH 重连...")
                            new_client = ssh_pool.reconnect(device_id)
                            if new_client:
                                client = new_client
                                retry_count = 0
                            else:
                                # 重连失败，停止采集
                                logger.error(f"设备 {device_id} SSH 重连失败，停止采集")
                                await stop_collect_in_db(collect_id, "error")
                                break

                    # 更新相对时间
                    relative_time += interval

                    # 等待下一次采集
                    await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"设备 {device_id} 采集任务异常退出: {e}")
                await stop_collect_in_db(collect_id, "error")
                ssh_pool.close_connection(device_id)

            finally:
                # 清理任务状态
                with _task_lock:
                    if device_id in _collect_tasks:
                        _collect_tasks[device_id]["running"] = False

        # 启动任务
        task = asyncio.create_task(collect_loop())
        _collect_tasks[device_id] = {
            "task": task,
            "collect_id": collect_id,
            "running": True,
        }

        logger.info(f"设备 {device_id} Linux 采集任务已启动，间隔 {interval} 秒")
        return True


async def stop_collect_in_db(collect_id: str, status: str = "stopped") -> None:
    """
    更新数据库中的采集状态

    Args:
        collect_id: 采集记录ID
        status: 状态（stopped/error）
    """
    from app.database import AsyncSessionLocal
    from core.performance_monitor.model import PerformanceCollect

    async with AsyncSessionLocal() as db:
        collect = await db.get(PerformanceCollect, collect_id)
        if collect:
            collect.status = status
            collect.end_time = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.commit()


def stop_linux_collect_task(device_id: str) -> bool:
    """
    停止 Linux 后台采集任务

    Args:
        device_id: 设备ID

    Returns:
        True if stopped, False if not running
    """
    with _task_lock:
        if device_id not in _collect_tasks:
            logger.warning(f"设备 {device_id} 无运行中的采集任务")
            return False

        task_info = _collect_tasks[device_id]
        if not task_info["running"]:
            logger.warning(f"设备 {device_id} 采集任务已停止")
            return False

        # 标记停止
        task_info["running"] = False

        # 关闭 SSH 连接
        ssh_pool.close_connection(device_id)

        logger.info(f"设备 {device_id} Linux 采集任务已停止")
        return True


def is_collecting(device_id: str) -> bool:
    """
    检查设备是否有正在运行的采集任务

    Args:
        device_id: 设备ID

    Returns:
        True if collecting, False otherwise
    """
    with _task_lock:
        if device_id not in _collect_tasks:
            return False
        return _collect_tasks[device_id].get("running", False)


def get_collect_task_info(device_id: str) -> Optional[Dict[str, Any]]:
    """
    获取采集任务信息

    Args:
        device_id: 设备ID

    Returns:
        任务信息字典，如果无任务则返回 None
    """
    with _task_lock:
        return _collect_tasks.get(device_id)