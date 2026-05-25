# Linux 性能采集功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有性能监控模块基础上，新增 Linux 服务器性能采集能力，支持通过 SSH 长连接采集系统级 CPU/内存数据。

**Architecture:** 后端新增 linux_collector.py 模块处理 SSH 连接池和数据采集，修改现有 API 添加 Linux 设备分支；前端修改设备列表页面隐藏 Linux 启用按钮，修改采集弹窗简化 Linux 采集流程。

**Tech Stack:** Python/FastAPI + paramiko (SSH) + Vue 3 + Element Plus

---

## 文件结构

| 文件 | 负责内容 |
|-----|---------|
| `backend-fastapi/core/performance_monitor/linux_collector.py` | SSH 连接池管理 + 数据采集 |
| `backend-fastapi/core/performance_monitor/api.py` | start/stop 路由添加 Linux 分支 |
| `backend-fastapi/core/performance_monitor/schema.py` | 添加 Linux 采集相关 Schema |
| `backend-fastapi/core/env_machine/api.py` | 批量启用过滤 Linux 设备 |
| `backend-fastapi/core/env_machine/schema.py` | Linux 设备校验规则放宽 |
| `backend-fastapi/scripts/init_linux_metric_mapping.py` | 初始化 Linux 指标映射数据 |
| `web/apps/web-ele/src/views/env-machine/list.vue` | 隐藏 Linux 设备启用按钮 |
| `web/apps/web-ele/src/views/performance-monitor/components/CollectDialog.vue` | Linux 简化采集弹窗 |
| `web/apps/web-ele/src/views/performance-monitor/index.vue` | 设备选择支持 Linux |

---

## Task 1: 添加 paramiko 依赖

**Files:**
- Modify: `backend-fastapi/requirements.txt`

- [ ] **Step 1: 在 requirements.txt 添加 paramiko**

```python
# 在文件末尾添加
paramiko>=3.0.0
```

- [ ] **Step 2: 安装依赖**

Run: `cd backend-fastapi && pip install paramiko>=3.0.0`
Expected: 成功安装 paramiko

- [ ] **Step 3: 提交**

```bash
git add backend-fastapi/requirements.txt
git commit -m "chore: 添加 paramiko SSH 依赖"
```

---

## Task 2: 创建 linux_collector.py 模块

**Files:**
- Create: `backend-fastapi/core/performance_monitor/linux_collector.py`

- [ ] **Step 1: 创建 SSH 连接池类**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Linux 性能采集模块 - SSH 连接池和数据采集
"""
import asyncio
import logging
import time
from typing import Dict, Optional, Any

import paramiko

logger = logging.getLogger(__name__)


class SSHConnectionPool:
    """SSH 连接池管理"""
    
    # 连接配置
    CONNECT_TIMEOUT = 10  # 连接超时（秒）
    COMMAND_TIMEOUT = 30  # 命令超时（秒）
    MAX_RETRIES = 3       # 最大重连次数
    MAX_CONNECTIONS = 10  # 最大并发连接数
    
    # 活跃连接存储
    _connections: Dict[str, paramiko.SSHClient] = {}
    _lock = asyncio.Lock()
    
    @classmethod
    async def get_connection(
        cls,
        device_id: str,
        host: str,
        port: int,
        account: str,
        password: str
    ) -> Optional[paramiko.SSHClient]:
        """获取或创建 SSH 连接"""
        async with cls._lock:
            # 检查并发限制
            if len(cls._connections) >= cls.MAX_CONNECTIONS:
                raise RuntimeError(f"SSH 连接池已满，最大并发 {cls.MAX_CONNECTIONS} 台")
            
            # 如果已有连接，检查是否有效
            if device_id in cls._connections:
                client = cls._connections[device_id]
                try:
                    # 测试连接有效性
                    client.exec_command("echo test", timeout=5)
                    return client
                except Exception:
                    # 连接无效，移除并重新创建
                    logger.warning(f"SSH 连接无效，重新创建: device_id={device_id}")
                    cls._close_client(client)
                    del cls._connections[device_id]
            
            # 创建新连接
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            for attempt in range(cls.MAX_RETRIES):
                try:
                    client.connect(
                        hostname=host,
                        port=port,
                        username=account,
                        password=password,
                        timeout=cls.CONNECT_TIMEOUT,
                        look_for_keys=False,
                        allow_agent=False
                    )
                    cls._connections[device_id] = client
                    logger.info(f"SSH 连接成功: device_id={device_id}, host={host}:{port}")
                    return client
                except paramiko.AuthenticationException:
                    logger.error(f"SSH 认证失败: device_id={device_id}")
                    raise RuntimeError("SSH 认证失败，请检查账号密码")
                except Exception as e:
                    logger.warning(f"SSH 连接失败 (attempt {attempt + 1}): {e}")
                    if attempt < cls.MAX_RETRIES - 1:
                        await asyncio.sleep(1)
                    else:
                        raise RuntimeError(f"SSH 连接失败: {str(e)}")
            
            return None
    
    @classmethod
    async def close_connection(cls, device_id: str):
        """关闭指定连接"""
        async with cls._lock:
            if device_id in cls._connections:
                client = cls._connections[device_id]
                cls._close_client(client)
                del cls._connections[device_id]
                logger.info(f"SSH 连接已关闭: device_id={device_id}")
    
    @classmethod
    async def close_all(cls):
        """关闭所有连接"""
        async with cls._lock:
            for device_id, client in cls._connections.items():
                cls._close_client(client)
                logger.info(f"SSH 连接已关闭: device_id={device_id}")
            cls._connections.clear()
    
    @classmethod
    def _close_client(cls, client: paramiko.SSHClient):
        """关闭单个 SSH 客户端"""
        try:
            client.close()
        except Exception as e:
            logger.warning(f"关闭 SSH 客户端异常: {e}")
    
    @classmethod
    def is_connected(cls, device_id: str) -> bool:
        """检查连接是否存在"""
        return device_id in cls._connections
    
    # 认证信息缓存（用于重连）
    _auth_cache: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    def cache_auth(cls, device_id: str, host: str, port: int, account: str, password: str):
        """缓存认证信息（用于重连）"""
        cls._auth_cache[device_id] = {
            "host": host,
            "port": port,
            "account": account,
            "password": password,
        }
    
    @classmethod
    async def reconnect(cls, device_id: str) -> Optional[paramiko.SSHClient]:
        """重连指定设备"""
        auth = cls._auth_cache.get(device_id)
        if not auth:
            logger.warning(f"无认证缓存，无法重连: device_id={device_id}")
            return None
        
        # 先关闭旧连接
        await cls.close_connection(device_id)
        
        # 使用缓存的认证信息重新连接
        try:
            return await cls.get_connection(
                device_id=device_id,
                host=auth["host"],
                port=auth["port"],
                account=auth["account"],
                password=auth["password"]
            )
        except Exception as e:
            logger.error(f"重连失败: device_id={device_id}, error={e}")
            return None
```

- [ ] **Step 2: 创建数据采集类**

继续在同一文件添加：

```python
class LinuxDataCollector:
    """Linux 数据采集"""
    
    @staticmethod
    def parse_vmstat(output: str) -> Dict[str, float]:
        """解析 vmstat 输出，提取 CPU 指标"""
        lines = output.strip().split('\n')
        if len(lines) < 3:
            return {}
        
        # vmstat 1 2 输出格式：
        # procs -----------memory---------- ---swap-- -----io---- -system-- ------cpu-----
        #  r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs  us  sy  id  wa  st
        #  0  0      0 4757520 135376 7909200    0    0     0     0   10   15  0.0 0.0 100  0.0 0.0
        
        # 取最后一行（避免首行平均值）
        data_line = lines[-1].strip()
        parts = data_line.split()
        
        if len(parts) < 17:
            return {}
        
        # CPU 指标位置：us(12), sy(13), id(14), wa(15), st(16)
        try:
            return {
                "cpu_us": float(parts[12]),
                "cpu_sy": float(parts[13]),
                "cpu_id": float(parts[14]),
                "cpu_wa": float(parts[15]),
                "cpu_st": float(parts[16]),
                # 注：vmstat 不直接输出 hi/si，需从其他来源获取或默认 0
                "cpu_hi": 0.0,
                "cpu_si": 0.0,
                "cpu_ni": 0.0,  # vmstat 不输出 ni
            }
        except (ValueError, IndexError) as e:
            logger.warning(f"解析 vmstat 失败: {e}")
            return {}
    
    @staticmethod
    def parse_free(output: str) -> Dict[str, float]:
        """解析 free -m 输出，提取内存指标"""
        lines = output.strip().split('\n')
        if len(lines) < 3:
            return {}
        
        # free -m 输出格式：
        #               total        used        free      shared  buff/cache   available
        # Mem:           7909        2069        4757         135        1353        5839
        # Swap:          2048           0        2048
        
        result = {}
        
        for line in lines[1:]:
            parts = line.strip().split()
            if len(parts) < 6:
                continue
            
            label = parts[0].rstrip(':')
            
            try:
                if label == 'Mem':
                    result["mem_total"] = float(parts[1])
                    result["mem_used"] = float(parts[2])
                    result["mem_free"] = float(parts[3])
                    result["mem_buff_cache"] = float(parts[5]) if len(parts) > 5 else 0.0
                    # available 列
                    result["swap_avail_mem"] = float(parts[6]) if len(parts) > 6 else 0.0
                elif label == 'Swap':
                    result["swap_total"] = float(parts[1])
                    result["swap_used"] = float(parts[2])
                    result["swap_free"] = float(parts[3])
            except (ValueError, IndexError) as e:
                logger.warning(f"解析 free 失败: {e}")
        
        return result
    
    @classmethod
    async def collect(cls, client: paramiko.SSHClient) -> Dict[str, Any]:
        """执行采集，返回结构化数据"""
        try:
            # 执行 vmstat 1 2（采集 1 秒间隔的 2 个样本，取第二个）
            stdin, stdout, stderr = client.exec_command(
                "vmstat 1 2",
                timeout=SSHConnectionPool.COMMAND_TIMEOUT
            )
            vmstat_output = stdout.read().decode('utf-8')
            
            # 执行 free -m
            stdin, stdout, stderr = client.exec_command(
                "free -m",
                timeout=SSHConnectionPool.COMMAND_TIMEOUT
            )
            free_output = stdout.read().decode('utf-8')
            
            # 解析数据
            cpu_data = cls.parse_vmstat(vmstat_output)
            mem_data = cls.parse_free(free_output)
            
            # 合并为扁平化结构（兼容 hwinfo_raw 格式）
            hwinfo_raw = {"source": "linux"}
            hwinfo_raw.update(cpu_data)
            hwinfo_raw.update(mem_data)
            
            # 计算核心指标
            cpu_usage = 100.0 - cpu_data.get("cpu_id", 100.0)
            memory_usage = mem_data.get("mem_used", 0.0) / 1024  # MiB -> GB
            
            return {
                "cpu_usage": cpu_usage,
                "gpu_usage": None,  # Linux 无 GPU 指标
                "memory_usage": memory_usage,
                "commit_memory": 0.0,  # Linux 无此概念
                "hwinfo_raw": hwinfo_raw,
            }
        except Exception as e:
            logger.error(f"Linux 数据采集失败: {e}")
            raise RuntimeError(f"数据采集失败: {str(e)}")
```

- [ ] **Step 3: 创建后台采集任务函数**

继续在同一文件添加：

```python
# 后台采集任务存储
_collect_tasks: Dict[str, asyncio.Task] = {}


async def start_linux_collect_task(
    device_id: str,
    collect_id: str,
    interval: int,
    db_session_factory
):
    """启动 Linux 后台采集任务"""
    from sqlalchemy.ext.asyncio import AsyncSession
    from datetime import datetime
    from core.performance_monitor.model import PerformanceData, PerformanceCollect
    from core.performance_monitor.service import PerformanceDataService
    
    # 获取 SSH 连接（应该在 start_collect 时已创建）
    client = SSHConnectionPool._connections.get(device_id)
    if not client:
        logger.error(f"SSH 连接不存在: device_id={device_id}")
        return
    
    # 获取采集开始时间
    start_time = datetime.now()
    relative_time = 0
    
    logger.info(f"Linux 采集任务启动: device_id={device_id}, collect_id={collect_id}, interval={interval}")
    
    async def collect_loop():
        """采集循环"""
        nonlocal relative_time
        
        while SSHConnectionPool.is_connected(device_id):
            try:
                # 执行采集
                data = await LinuxDataCollector.collect(client)
                
                # 写入数据库
                async with db_session_factory() as db:
                    # 检查采集状态
                    collect = await db.get(PerformanceCollect, collect_id)
                    if not collect or collect.status != "running":
                        logger.info(f"采集已停止: collect_id={collect_id}")
                        break
                    
                    # 创建数据记录
                    perf_data = PerformanceData(
                        collect_id=collect_id,
                        timestamp=datetime.now(),
                        relative_time=relative_time,
                        cpu_usage=data["cpu_usage"],
                        gpu_usage=data["gpu_usage"],
                        memory_usage=data["memory_usage"],
                        commit_memory=data["commit_memory"],
                        hwinfo_raw=data["hwinfo_raw"],
                    )
                    db.add(perf_data)
                    await db.commit()
                
                relative_time += interval
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"采集异常: device_id={device_id}, error={e}")
                # 尝试重连
                try:
                    await SSHConnectionPool.reconnect(device_id)
                    client = SSHConnectionPool._connections.get(device_id)
                    if not client:
                        break
                except Exception:
                    logger.error(f"重连失败，停止采集: device_id={device_id}")
                    async with db_session_factory() as db:
                        collect = await db.get(PerformanceCollect, collect_id)
                        if collect:
                            collect.status = "error"
                            collect.end_time = datetime.now()
                            await db.commit()
                    break
    
    # 启动采集循环任务
    task = asyncio.create_task(collect_loop())
    _collect_tasks[device_id] = task


async def stop_linux_collect_task(device_id: str):
    """停止 Linux 后台采集任务"""
    task = _collect_tasks.get(device_id)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        del _collect_tasks[device_id]
        logger.info(f"Linux 采集任务已取消: device_id={device_id}")
    
    # 关闭 SSH 连接
    await SSHConnectionPool.close_connection(device_id)
```

- [ ] **Step 4: 提交**

```bash
git add backend-fastapi/core/performance_monitor/linux_collector.py
git commit -m "feat: 创建 Linux 性能采集模块 - SSH 连接池和数据采集"
```

---

## Task 3: 修改 performance_monitor schema.py

**Files:**
- Modify: `backend-fastapi/core/performance_monitor/schema.py`

- [ ] **Step 1: 添加 Linux 采集认证信息 Schema**

在文件末尾添加：

```python
# ===== Linux 采集 Schema =====


class LinuxAuthInfo(BaseModel):
    """Linux SSH 认证信息"""
    account: str = Field(default="root", description="SSH 账号")
    password: str = Field(..., description="SSH 密码")
    port: int = Field(default=22, ge=1, le=65535, description="SSH 端口")
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/performance_monitor/schema.py
git commit -m "feat: 添加 Linux SSH 认证信息 Schema"
```

---

## Task 4: 修改 performance_monitor api.py

**Files:**
- Modify: `backend-fastapi/core/performance_monitor/api.py`

- [ ] **Step 1: 导入 linux_collector 模块**

在文件开头的导入区域添加：

```python
from core.performance_monitor.linux_collector import (
    SSHConnectionPool,
    LinuxDataCollector,
    start_linux_collect_task,
    stop_linux_collect_task,
)
```

- [ ] **Step 2: 修改 start_collect 路由添加 Linux 分支**

找到 `start_collect` 函数（约第 87-122 行），修改为：

```python
@router.post("/collect/start")
async def start_collect(request: CollectStartRequest, db: AsyncSession = Depends(get_db)):
    """开始采集"""
    # 1. 从数据库获取设备信息
    stmt = select(EnvMachine).where(EnvMachine.id == request.device_id, EnvMachine.is_deleted == False)
    result = await db.execute(stmt)
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    # 2. 保存采集记录到数据库
    collect_id = await PerformanceCollectService.start_collect(db, request)

    # 3. 根据设备类型选择采集方式
    if device.device_type == 'linux':
        # Linux 设备：SSH 采集
        # 从 extra_message 获取认证信息
        auth = device.extra_message or {}
        account = auth.get('account', 'root')
        password = auth.get('password', '')
        port = auth.get('port', 22)
        
        if not password:
            await PerformanceCollectService.stop_collect(db, collect_id, request.device_id)
            raise HTTPException(status_code=400, detail="Linux 设备未配置 SSH 密码")
        
        try:
            # 建立 SSH 连接
            await SSHConnectionPool.get_connection(
                device_id=request.device_id,
                host=device.ip,
                port=port,
                account=account,
                password=password
            )
            
            # 缓存认证信息（用于重连）
            SSHConnectionPool.cache_auth(
                device_id=request.device_id,
                host=device.ip,
                port=port,
                account=account,
                password=password
            )
            
            # 启动后台采集任务
            from app.database import async_session_factory
            await start_linux_collect_task(
                device_id=request.device_id,
                collect_id=collect_id,
                interval=request.interval,
                db_session_factory=async_session_factory
            )
            
        except RuntimeError as e:
            await PerformanceCollectService.stop_collect(db, collect_id, request.device_id)
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            await PerformanceCollectService.stop_collect(db, collect_id, request.device_id)
            raise HTTPException(status_code=500, detail=f"SSH 连接失败: {str(e)}")
    else:
        # Windows/Mac 设备：Worker API 采集
        worker_url = f"http://{device.ip}:{device.port}/api/worker/{request.device_id}/collect/start"
        try:
            async with httpx.AsyncClient(timeout=10.0, trust_env=False, verify=False) as client:
                worker_request = {
                    "collect_id": collect_id,
                    "interval": request.interval,
                    "timeout": 43200,
                    "target_processes": request.target_processes or []
                }
                resp = await client.post(worker_url, json=worker_request)
                if resp.status_code != 200:
                    await PerformanceCollectService.stop_collect(db, collect_id, request.device_id)
                    raise HTTPException(status_code=resp.status_code, detail=f"Worker 返回错误: {resp.text}")
        except httpx.ConnectError:
            await PerformanceCollectService.stop_collect(db, collect_id, request.device_id)
            raise HTTPException(status_code=503, detail=f"无法连接到 Worker: {device.ip}:{device.port}")
        except httpx.TimeoutException:
            await PerformanceCollectService.stop_collect(db, collect_id, request.device_id)
            raise HTTPException(status_code=504, detail="Worker 响应超时")

    return {"collect_id": collect_id, "status": "started"}
```

- [ ] **Step 3: 修改 stop_collect 路由添加 Linux 分支**

找到 `stop_collect` 函数（约第 125-150 行），修改为：

```python
@router.post("/collect/stop")
async def stop_collect(request: CollectStopRequest, db: AsyncSession = Depends(get_db)):
    """停止采集"""
    # 1. 从数据库获取设备信息
    stmt = select(EnvMachine).where(EnvMachine.id == request.device_id, EnvMachine.is_deleted == False)
    result = await db.execute(stmt)
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    # 2. 更新数据库状态
    success = await PerformanceCollectService.stop_collect(db, request.collect_id, request.device_id)

    # 3. 根据设备类型选择停止方式
    if device.device_type == 'linux':
        # Linux 设备：停止 SSH 采集任务
        await stop_linux_collect_task(request.device_id)
    else:
        # Windows/Mac 设备：调用 Worker API
        worker_url = f"http://{device.ip}:{device.port}/api/worker/{request.device_id}/collect/stop"
        try:
            async with httpx.AsyncClient(timeout=10.0, trust_env=False, verify=False) as client:
                worker_request = {"collect_id": request.collect_id} if request.collect_id else {}
                resp = await client.post(worker_url, json=worker_request)
                if resp.status_code != 200:
                    raise HTTPException(status_code=resp.status_code, detail=f"Worker 返回错误: {resp.text}")
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail=f"无法连接到 Worker: {device.ip}:{device.port}")
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Worker 响应超时")

    return {"status": "stopped" if success else "not_found"}
```

- [ ] **Step 4: 提交**

```bash
git add backend-fastapi/core/performance_monitor/api.py
git commit -m "feat: 采集 API 添加 Linux 设备分支支持"
```

---

## Task 5: 修改 env_machine api.py - 批量启用过滤 Linux

**Files:**
- Modify: `backend-fastapi/core/env_machine/api.py`

- [ ] **Step 1: 修改 batch_enable 路由**

找到 `batch_enable_env_machines` 函数（约第 1132-1160 行），修改为：

```python
@router.post("/batch-enable", response_model=BatchEnableResponse, summary="批量启用设备")
async def batch_enable_env_machines(
    data: BatchEnableRequest,
    db: AsyncSession = Depends(get_db)
) -> BatchEnableResponse:
    """
    批量启用设备（带校验）

    校验规则：
    - 标签字段必须存在
    - 扩展信息字段必须存在且为有效 dict
    - 每个标签在扩展信息中必须有对应配置
    - Linux 设备不支持启用（自动跳过）

    不满足条件的设备会被跳过，返回跳过原因。
    """
    # 查询所有设备，过滤 Linux 设备
    machines = await EnvMachineService.get_by_ids(db, data.ids)
    
    # 过滤 Linux 设备
    linux_ids = [m.id for m in machines if m.device_type == 'linux']
    other_ids = [m.id for m in machines if m.device_type != 'linux']
    
    # Linux 设备跳过
    linux_skipped = [{"id": id, "ip": "", "reason": "Linux 设备不支持启用"} for id in linux_ids]
    
    # 其他设备执行启用校验
    success_count, skipped_items = await EnvMachineService.batch_enable_with_validation(
        db, other_ids
    )
    
    # 合并跳过列表
    all_skipped = linux_skipped + skipped_items

    # 同步 Redis 缓存（将启用的设备加入申请池）
    enabled_machines = await EnvMachineService.get_by_ids(db, other_ids)
    for machine in enabled_machines:
        if machine.available:
            await EnvPoolManager.sync_machine_to_cache(machine)

    return BatchEnableResponse(
        success_count=success_count,
        skipped_count=len(all_skipped),
        skipped_items=[SkippedItem(**item) for item in all_skipped]
    )
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/env_machine/api.py
git commit -m "feat: 批量启用过滤 Linux 设备"
```

---

## Task 6: 修改 env_machine schema.py - Linux 设备校验规则

**Files:**
- Modify: `backend-fastapi/core/env_machine/schema.py`

- [ ] **Step 1: 修改 EnvMachineCreateRequest 支持 linux**

找到 `EnvMachineCreateRequest` 类（约第 43-51 行），修改为：

```python
class EnvMachineCreateRequest(BaseModel):
    """新增执行机请求 Schema"""
    namespace: str = Field(..., description="机器分类")
    device_type: str = Field(..., description="机器类型：windows/mac/ios/android/linux")
    asset_number: Optional[str] = Field(None, description="资产编号（Linux 可选）")
    ip: Optional[str] = Field(None, description="IP地址（Windows/Mac/Linux）")
    device_sn: Optional[str] = Field(None, description="设备SN（iOS/Android）")
    note: Optional[str] = Field(None, description="备注")
    is_virtual: bool = Field(default=True, description="是否为虚拟设备")
    extra_message: Optional[Dict[str, Any]] = Field(None, description="扩展信息（Linux 设备存储 SSH 认证）")
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/env_machine/schema.py
git commit -m "feat: 设备 Schema 支持 Linux 类型"
```

---

## Task 7: 创建 Linux 指标映射初始化脚本

**Files:**
- Create: `backend-fastapi/scripts/init_linux_metric_mapping.py`

- [ ] **Step 1: 创建初始化脚本**

```python
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
from app.database import async_session_factory
from core.performance_monitor.model import PerformanceMetricMapping
from sqlalchemy import select


# Linux 指标映射数据
LINUX_METRIC_MAPPINGS = [
    {"hwinfo_key": "cpu_us", "display_name": "CPU用户态", "unit": "%", "display_unit": "%", "category": "cpu", "is_primary": True, "sort": 1},
    {"hwinfo_key": "cpu_sy", "display_name": "CPU系统态", "unit": "%", "display_unit": "%", "category": "cpu", "is_primary": True, "sort": 2},
    {"hwinfo_key": "cpu_id", "display_name": "CPU空闲", "unit": "%", "display_unit": "%", "category": "cpu", "is_primary": True, "sort": 3},
    {"hwinfo_key": "cpu_wa", "display_name": "CPU等待IO", "unit": "%", "display_unit": "%", "category": "cpu", "sort": 4},
    {"hwinfo_key": "cpu_hi", "display_name": "CPU硬件中断", "unit": "%", "display_unit": "%", "category": "cpu", "sort": 5},
    {"hwinfo_key": "cpu_si", "display_name": "CPU软件中断", "unit": "%", "display_unit": "%", "category": "cpu", "sort": 6},
    {"hwinfo_key": "cpu_st", "display_name": "CPU虚拟化偷取", "unit": "%", "display_unit": "%", "category": "cpu", "sort": 7},
    {"hwinfo_key": "cpu_ni", "display_name": "CPU优先级进程", "unit": "%", "display_unit": "%", "category": "cpu", "sort": 8},
    {"hwinfo_key": "mem_total", "display_name": "内存总量", "unit": "MiB", "display_unit": "GB", "category": "memory", "is_primary": True, "sort": 10},
    {"hwinfo_key": "mem_free", "display_name": "内存空闲", "unit": "MiB", "display_unit": "GB", "category": "memory", "is_primary": True, "sort": 11},
    {"hwinfo_key": "mem_used", "display_name": "内存使用", "unit": "MiB", "display_unit": "GB", "category": "memory", "is_primary": True, "sort": 12},
    {"hwinfo_key": "mem_buff_cache", "display_name": "内存缓冲缓存", "unit": "MiB", "display_unit": "GB", "category": "memory", "sort": 13},
    {"hwinfo_key": "swap_total", "display_name": "Swap总量", "unit": "MiB", "display_unit": "GB", "category": "swap", "sort": 20},
    {"hwinfo_key": "swap_free", "display_name": "Swap空闲", "unit": "MiB", "display_unit": "GB", "category": "swap", "sort": 21},
    {"hwinfo_key": "swap_used", "display_name": "Swap使用", "unit": "MiB", "display_unit": "GB", "category": "swap", "sort": 22},
    {"hwinfo_key": "swap_avail_mem", "display_name": "可用内存", "unit": "MiB", "display_unit": "GB", "category": "swap", "sort": 23},
]


async def init_linux_metric_mapping():
    """初始化 Linux 指标映射"""
    async with async_session_factory() as db:
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
```

- [ ] **Step 2: 运行初始化脚本**

Run: `cd backend-fastapi && python scripts/init_linux_metric_mapping.py`
Expected: 输出添加和跳过的记录数

- [ ] **Step 3: 提交**

```bash
git add backend-fastapi/scripts/init_linux_metric_mapping.py
git commit -m "feat: 创建 Linux 指标映射初始化脚本"
```

---

## Task 8: 前端 - 设备列表隐藏 Linux 启用按钮

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/list.vue`

- [ ] **Step 1: 找到启用按钮位置并添加条件判断**

在设备列表的操作列中，找到启用按钮，添加 `device_type !== 'linux'` 条件：

```vue
<!-- 启用按钮 - Linux 设备隐藏 -->
<el-button
  v-if="row.device_type !== 'linux'"
  type="success"
  size="small"
  @click="handleEnable(row)"
>
  启用
</el-button>
```

- [ ] **Step 2: 批量启用时过滤 Linux 设备**

在批量启用函数中添加过滤逻辑：

```typescript
async function handleBatchEnable() {
  // 过滤 Linux 设备
  const filteredIds = selectedRows.value
    .filter(row => row.device_type !== 'linux')
    .map(row => row.id);
  
  if (filteredIds.length === 0) {
    ElMessage.warning('没有可启用的设备（Linux 设备不支持启用）');
    return;
  }
  
  // 调用批量启用 API
  const result = await batchEnable(filteredIds);
  // ...
}
```

- [ ] **Step 3: 提交**

```bash
git add web/apps/web-ele/src/views/env-machine/list.vue
git commit -m "feat: 设备列表隐藏 Linux 启用按钮"
```

---

## Task 9: 前端 - 采集弹窗简化 Linux 流程

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/components/CollectDialog.vue`

- [ ] **Step 1: 根据 device_type 显示不同内容**

修改 template 部分：

```vue
<template>
  <el-dialog
    :model-value="props.visible"
    @update:model-value="(v: boolean) => emit('update:visible', v)"
    width="500px"
    destroy-on-close
    align-center
    :close-on-click-modal="false"
    class="collect-dialog"
  >
    <!-- 弹窗标题 -->
    <template #header>
      <div class="dialog-title">
        {{ deviceInfo?.device_type === 'linux' ? '开始 Linux 性能采集' : '开始性能采集' }}
      </div>
    </template>
    
    <!-- 设备信息 -->
    <div class="device-info">
      <div class="device-label">目标设备</div>
      <div class="device-name">{{ deviceDisplay }}</div>
    </div>

    <!-- Linux 设备：简化弹窗 -->
    <div v-if="deviceInfo?.device_type === 'linux'" class="linux-collect-section">
      <div class="section-title">Linux 系统级采集</div>
      <div class="config-tip">
        Linux 设备仅采集系统级 CPU/内存数据，无需选择目标进程
      </div>
      
      <!-- 采集配置 -->
      <div class="config-section">
        <div class="config-item">
          <div class="config-label">采集间隔</div>
          <el-select v-model="interval" size="small" style="width: 100%">
            <el-option
              v-for="opt in intervalOptions"
              :key="opt"
              :label="`${opt}秒`"
              :value="opt"
            />
          </el-select>
        </div>
        <div class="config-tip">
          <b>说明：</b>采集间隔越小，数据越精细，但占用更多存储空间。点击"停止采集"手动结束。
        </div>
      </div>
    </div>

    <!-- Windows/Mac 设备：现有进程选择逻辑 -->
    <div v-else class="process-section">
      <!-- ... 现有的进程选择逻辑保持不变 ... -->
    </div>

    <template #footer>
      <div class="dialog-footer">
        <button class="cancel-btn" @click="emit('update:visible', false)">取消</button>
        <button class="start-btn" :disabled="loading" @click="handleStart">
          {{ loading ? '加载中...' : '开始采集' }}
        </button>
      </div>
    </template>
  </el-dialog>
</template>
```

- [ ] **Step 2: 修改 handleStart 函数**

```typescript
async function handleStart() {
  // Linux 设备无需选择进程
  if (deviceInfo?.device_type !== 'linux' && selectedCount.value === 0) {
    ElMessage.warning('请选择目标进程');
    return;
  }

  try {
    loading.value = true;
    const result = await startCollect({
      device_id: props.deviceId,
      interval: interval.value,
      // Linux 设备不传 target_processes
      target_processes: deviceInfo?.device_type === 'linux' ? undefined : finalTargetProcesses.value,
    });
    
    ElMessage.success('采集已开始');
    emit('started', result.collect_id);
    emit('update:visible', false);
  } catch (error) {
    ElMessage.error('开始采集失败');
  } finally {
    loading.value = false;
  }
}
```

- [ ] **Step 3: 提交**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/CollectDialog.vue
git commit -m "feat: 采集弹窗简化 Linux 设备流程"
```

---

## Task 10: 前端 - 性能监控页面支持 Linux 设备选择

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/index.vue`

- [ ] **Step 1: 设备列表添加 Linux 类型过滤**

在设备查询 API 调用中添加 device_type 参数：

```typescript
async function fetchDevices() {
  // 查询设备时包含 linux 类型
  const result = await getEnvMachineList({
    // device_type 参数可以不传，获取所有类型
    // 或者在过滤时显示 linux 设备
  });
  
  // 设备列表显示时添加类型标识
  deviceList.value = result.items.map(item => ({
    ...item,
    typeLabel: item.device_type === 'linux' ? '[Linux]' : ''
  }));
}
```

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/performance-monitor/index.vue
git commit -m "feat: 性能监控页面支持 Linux 设备选择"
```

---

## Task 8.5: 前端 - 设备编辑弹窗隐藏 Linux 启用开关

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/list.vue`

- [ ] **Step 1: 找到编辑弹窗的启用开关并添加条件判断**

在设备编辑弹窗中找到"是否启用"表单项，添加 Linux 设备隐藏条件：

```vue
<!-- 是否启用 - Linux 设备隐藏 -->
<el-form-item v-if="formData.device_type !== 'linux'" label="是否启用">
  <el-switch v-model="formData.available" />
</el-form-item>
```

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/env-machine/list.vue
git commit -m "feat: 设备编辑弹窗隐藏 Linux 启用开关"
```

---

## Task 10.5: 前端 - GPU 图表条件渲染

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/index.vue`

- [ ] **Step 1: GPU 图表区域添加条件判断**

找到 GPU 图表组件，添加 `gpu_usage` 存在时才显示的条件：

```vue
<!-- GPU 图表 - 仅在有 GPU 数据时显示 -->
<div v-if="hasGpuData" class="gpu-chart-section">
  <!-- GPU 图表内容 -->
</div>
```

在 script 中添加判断逻辑：

```typescript
const hasGpuData = computed(() => {
  // 检查采集数据中是否有 GPU 数据
  // Linux 设备无 GPU 指标，gpu_usage 为 null
  return collectData.value.some(item => item.gpu_usage !== null);
});
```

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/performance-monitor/index.vue
git commit -m "feat: GPU 图表条件渲染 - Linux 设备无 GPU 时隐藏"
```

---

## Task 11: 集成测试

- [ ] **Step 1: 测试 Linux 设备导入**

1. 在设备列表页面导入一台 Linux 设备
2. 验证 `extra_message` 格式正确（account, password, port）
3. 验证设备列表不显示启用按钮

- [ ] **Step 2: 测试批量启用过滤**

1. 选择包含 Linux 设备的多个设备
2. 点击批量启用
3. 验证 Linux 设备被跳过并返回提示

- [ ] **Step 3: 测试 Linux 采集**

1. 在性能监控页面选择 Linux 设备
2. 打开采集弹窗，验证无进程选择区域
3. 点击开始采集
4. 验证数据写入 performance_data 表
5. 验证图表展示 CPU/内存曲线

- [ ] **Step 4: 测试停止采集**

1. 点击停止采集
2. 验证 SSH 连接关闭
3. 验证采集状态更新为 stopped

---

## Task 12: 最终提交

- [ ] **Step 1: 确认所有变更已提交**

Run: `git status`
Expected: 无未提交变更

- [ ] **Step 2: 推送到远程**

```bash
git push origin main
```