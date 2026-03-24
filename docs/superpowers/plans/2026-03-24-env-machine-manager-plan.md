# 执行机管理模块实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现执行机管理模块，包括机器注册、申请、释放、状态监控和定时任务。

**Architecture:** 采用分层架构，数据模型继承 BaseModel，服务层继承 BaseService，使用 APScheduler 4.x 管理定时任务，Redis 实现机器池缓存和分布式锁。

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async), Pydantic, APScheduler 4.0.0a6, Redis 5.0.1

---

## 文件结构

```
backend-fastapi/
├── core/env_machine/
│   ├── __init__.py           # 模块初始化
│   ├── model.py              # EnvMachine 数据模型
│   ├── schema.py             # 请求/响应 Schema
│   ├── service.py            # 基础 CRUD 服务
│   ├── pool_manager.py       # 机器池缓存管理
│   ├── lock_manager.py       # Redis 分布式锁
│   ├── scheduler.py          # 定时任务管理
│   └── api.py                # 路由接口
├── alembic/versions/
│   └── xxx_add_env_machine_table.py  # 数据库迁移
├── core/router.py            # 添加路由注册
└── utils/auth_middleware.py  # 添加认证白名单
```

---

### Task 1: 数据模型 (model.py)

**Files:**
- Create: `backend-fastapi/core/env_machine/__init__.py`
- Create: `backend-fastapi/core/env_machine/model.py`

- [ ] **Step 1: 创建 __init__.py**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
执行机管理模块
"""
```

- [ ] **Step 2: 创建 model.py**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2026-03-24
@File: model.py
@Desc: EnvMachine Model - 执行机模型
"""
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import Column, String, Text, Boolean, DateTime, Index, JSON

from app.base_model import BaseModel


class EnvMachine(BaseModel):
    """
    执行机模型 - 用于管理自动化测试执行机

    字段说明：
    - namespace: 机器分类，如 meeting_xxx / manual / public
    - ip: 机器 IP（支持 IPv6）
    - port: 机器端口
    - mark: 机器标签，多个用逗号分隔
    - device_type: 机器类型（windows/mac/android/ios）
    - device_sn: 设备 SN（移动端必填）
    - available: 是否启用
    - status: 状态（online/using/offline）
    - note: 备注
    - sync_time: 同步时间
    - extra_message: 扩展信息，按标签存储
    - version: 机器版本
    - last_keepusing_time: 最后保持使用时间
    """
    __tablename__ = "env_machine"

    # 机器分类
    namespace = Column(String(64), nullable=False, index=True, comment="机器分类")

    # 机器 IP（支持 IPv6）
    ip = Column(String(45), nullable=False, comment="机器IP")

    # 机器端口
    port = Column(String(10), nullable=False, comment="机器端口")

    # 机器标签，多个用逗号分隔
    mark = Column(String(255), nullable=True, comment="机器标签")

    # 机器类型：windows / mac / android / ios
    device_type = Column(String(20), nullable=False, comment="机器类型")

    # 设备 SN（移动端必填）
    device_sn = Column(String(64), nullable=True, comment="设备SN")

    # 是否启用
    available = Column(Boolean, default=False, comment="是否启用")

    # 状态：online / using / offline
    status = Column(String(20), default="online", nullable=False, comment="状态")

    # 备注
    note = Column(Text, nullable=True, comment="备注")

    # 同步时间
    sync_time = Column(DateTime, default=datetime.now, nullable=False, comment="同步时间")

    # 扩展信息，按标签存储 JSON
    extra_message = Column(JSON, nullable=True, comment="扩展信息")

    # 机器版本
    version = Column(String(32), nullable=True, comment="机器版本")

    # 最后保持使用时间
    last_keepusing_time = Column(DateTime, nullable=True, comment="最后保持使用时间")

    # 复合唯一索引：namespace + ip + device_type + device_sn
    __table_args__ = (
        Index('ix_env_machine_unique', 'namespace', 'ip', 'device_type', 'device_sn', unique=True),
        Index('ix_env_machine_status', 'status'),
        Index('ix_env_machine_sync_time', 'sync_time'),
    )

    def __repr__(self):
        return f"<EnvMachine {self.namespace}:{self.ip}:{self.device_type}>"

    def get_status_display(self) -> str:
        """获取状态的显示名称"""
        status_map = {
            "online": "在线",
            "using": "使用中",
            "offline": "离线",
        }
        return status_map.get(self.status, "未知")

    def to_cache_dict(self) -> Dict[str, Any]:
        """转换为缓存字典格式"""
        return {
            "id": self.id,
            "ip": self.ip,
            "port": self.port,
            "mark": self.mark or "",
            "device_type": self.device_type,
            "device_sn": self.device_sn,
            "status": self.status,
            "available": self.available,
            "extra_message": self.extra_message or {},
            "namespace": self.namespace,
        }
```

- [ ] **Step 3: 提交**

```bash
git add backend-fastapi/core/env_machine/__init__.py backend-fastapi/core/env_machine/model.py
git commit -m "feat(env_machine): 添加 EnvMachine 数据模型"
```

---

### Task 2: 请求/响应 Schema (schema.py)

**Files:**
- Create: `backend-fastapi/core/env_machine/schema.py`

- [ ] **Step 1: 创建 schema.py**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2026-03-24
@File: schema.py
@Desc: EnvMachine Schema - 执行机数据验证模式
"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ==================== 注册接口 Schema ====================

class EnvRegisterRequest(BaseModel):
    """注册接口请求"""
    ip: str = Field(..., description="机器IP")
    port: str = Field(..., description="机器端口")
    namespace: str = Field(..., description="机器分类")
    version: Optional[str] = Field(None, description="机器版本")
    devices: Dict[str, List[str]] = Field(..., description="设备列表，key为device_type，value为device_sn列表")

    @field_validator("devices")
    @classmethod
    def validate_devices(cls, v):
        """验证设备列表"""
        valid_types = ["windows", "mac", "android", "ios"]
        for device_type in v.keys():
            if device_type not in valid_types:
                raise ValueError(f"设备类型必须是以下之一: {', '.join(valid_types)}")
        return v


# ==================== 申请接口 Schema ====================

class EnvMachineAllocation(BaseModel):
    """分配的机器信息"""
    id: str = Field(..., description="机器ID")
    ip: str = Field(..., description="机器IP")
    port: str = Field(..., description="机器端口")
    device_type: str = Field(..., description="机器类型")
    device_sn: Optional[str] = Field(None, description="设备SN")

    # 动态扩展字段，从 extra_message 合并
    model_config = ConfigDict(extra="allow")


# ==================== 保持使用/释放接口 Schema ====================

class EnvMachineIdItem(BaseModel):
    """机器ID项"""
    id: str = Field(..., description="机器ID")


# ==================== 统一响应 Schema ====================

class EnvSuccessResponse(BaseModel):
    """成功响应"""
    status: str = "success"
    data: Any = None


class EnvFailResponse(BaseModel):
    """失败响应"""
    status: str = "fail"
    result: str = Field(..., description="错误描述")


# ==================== 机器信息响应 Schema ====================

class EnvMachineResponse(BaseModel):
    """机器信息响应"""
    id: str
    namespace: str
    ip: str
    port: str
    mark: Optional[str] = None
    device_type: str
    device_sn: Optional[str] = None
    available: bool
    status: str
    status_display: Optional[str] = None
    note: Optional[str] = None
    sync_time: Optional[datetime] = None
    extra_message: Optional[Dict[str, Any]] = None
    version: Optional[str] = None
    last_keepusing_time: Optional[datetime] = None
    sort: int = 0
    is_deleted: bool = False
    sys_create_datetime: Optional[datetime] = None
    sys_update_datetime: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/env_machine/schema.py
git commit -m "feat(env_machine): 添加请求/响应 Schema"
```

---

### Task 3: Redis 分布式锁管理器 (lock_manager.py)

**Files:**
- Create: `backend-fastapi/core/env_machine/lock_manager.py`

- [ ] **Step 1: 创建 lock_manager.py**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2026-03-24
@File: lock_manager.py
@Desc: Redis 分布式锁管理器
"""
import uuid
import asyncio
import logging
from typing import List

from utils.redis import RedisClient

logger = logging.getLogger(__name__)


class LockManager:
    """
    Redis 分布式锁管理器

    使用 SET NX EX 实现分布式锁
    """

    LOCK_PREFIX = "env_lock:"
    LOCK_TTL = 10  # 锁过期时间（秒）
    RETRY_INTERVAL = 0.1  # 重试间隔（秒）
    RETRY_TIMEOUT = 3  # 重试超时（秒）

    def __init__(self):
        self._lock_values: dict = {}  # 存储当前持有的锁的值

    def _make_key(self, namespace: str) -> str:
        """生成锁的 key"""
        return f"{self.LOCK_PREFIX}{namespace}"

    def _generate_lock_value(self) -> str:
        """生成锁的唯一值"""
        return str(uuid.uuid4())

    async def acquire_lock(
        self,
        namespace: str,
        timeout: float = None
    ) -> bool:
        """
        获取单个命名空间的锁

        Args:
            namespace: 命名空间
            timeout: 超时时间（秒）

        Returns:
            是否成功获取锁
        """
        if timeout is None:
            timeout = self.RETRY_TIMEOUT

        key = self._make_key(namespace)
        value = self._generate_lock_value()
        client = await RedisClient.get_client()

        start_time = asyncio.get_event_loop().time()

        while True:
            # 尝试设置锁（SET NX EX）
            result = await client.set(key, value, nx=True, ex=self.LOCK_TTL)

            if result:
                self._lock_values[key] = value
                logger.debug(f"成功获取锁: {key}")
                return True

            # 检查是否超时
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                logger.warning(f"获取锁超时: {key}")
                return False

            # 等待后重试
            await asyncio.sleep(self.RETRY_INTERVAL)

    async def acquire_locks(
        self,
        namespaces: List[str],
        timeout: float = None
    ) -> bool:
        """
        获取多个命名空间的锁（按字母序获取，避免死锁）

        Args:
            namespaces: 命名空间列表
            timeout: 超时时间（秒）

        Returns:
            是否成功获取所有锁
        """
        if timeout is None:
            timeout = self.RETRY_TIMEOUT

        # 按字母序排序
        sorted_namespaces = sorted(set(namespaces))
        acquired = []

        try:
            for ns in sorted_namespaces:
                if not await self.acquire_lock(ns, timeout):
                    # 获取失败，释放已获取的锁
                    logger.warning(f"获取锁失败，回滚已获取的锁: {acquired}")
                    for acquired_ns in acquired:
                        await self.release_lock(acquired_ns)
                    return False
                acquired.append(ns)

            return True
        except Exception as e:
            logger.error(f"获取锁异常: {str(e)}")
            # 异常时释放已获取的锁
            for acquired_ns in acquired:
                await self.release_lock(acquired_ns)
            return False

    async def release_lock(self, namespace: str) -> bool:
        """
        释放单个命名空间的锁

        Args:
            namespace: 命名空间

        Returns:
            是否成功释放锁
        """
        key = self._make_key(namespace)
        client = await RedisClient.get_client()

        # 只释放自己持有的锁（使用 Lua 脚本保证原子性）
        value = self._lock_values.get(key)
        if not value:
            return False

        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """

        result = await client.eval(lua_script, 1, key, value)

        if key in self._lock_values:
            del self._lock_values[key]

        if result:
            logger.debug(f"成功释放锁: {key}")
            return True
        else:
            logger.warning(f"锁已被其他进程释放或过期: {key}")
            return False

    async def release_locks(self, namespaces: List[str]) -> int:
        """
        释放多个命名空间的锁

        Args:
            namespaces: 命名空间列表

        Returns:
            成功释放的锁数量
        """
        count = 0
        for ns in namespaces:
            if await self.release_lock(ns):
                count += 1
        return count


# 全局锁管理器实例
lock_manager = LockManager()
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/env_machine/lock_manager.py
git commit -m "feat(env_machine): 添加 Redis 分布式锁管理器"
```

---

### Task 4: 机器池缓存管理器 (pool_manager.py)

**Files:**
- Create: `backend-fastapi/core/env_machine/pool_manager.py`

- [ ] **Step 1: 创建 pool_manager.py**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2026-03-24
@File: pool_manager.py
@Desc: 机器池缓存管理器
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utils.redis import CacheManager
from core.env_machine.model import EnvMachine

logger = logging.getLogger(__name__)


class PoolManager:
    """
    机器池缓存管理器

    管理机器池的 Redis 缓存，包括加载、更新、申请、释放
    使用 CacheManager 统一管理缓存操作
    """

    POOL_PREFIX = "env_pool:"
    MANUAL_NAMESPACE = "manual"
    PUBLIC_NAMESPACE = "public"

    def __init__(self):
        # 使用 CacheManager 管理缓存
        self._cache = CacheManager(prefix="")

    def _make_pool_key(self, namespace: str) -> str:
        """生成机器池的 key"""
        return f"{self.POOL_PREFIX}{namespace}"

    def _machine_to_json(self, machine: EnvMachine) -> str:
        """将机器对象转换为 JSON 字符串"""
        return json.dumps(machine.to_cache_dict(), ensure_ascii=False, default=str)

    async def load_pool_from_db(self, db: AsyncSession) -> int:
        """
        从数据库加载机器池到 Redis

        Args:
            db: 数据库会话

        Returns:
            加载的机器数量
        """
        # 清空现有缓存
        await self._cache.delete_pattern(f"{self.POOL_PREFIX}*")

        # 查询所有 online + 启用的机器
        result = await db.execute(
            select(EnvMachine).where(
                EnvMachine.status == "online",
                EnvMachine.available == True,  # noqa: E712
                EnvMachine.is_deleted == False,  # noqa: E712
                EnvMachine.namespace != self.MANUAL_NAMESPACE
            )
        )
        machines = result.scalars().all()

        # 按命名空间分组写入 Redis
        count = 0
        for machine in machines:
            key = self._make_pool_key(machine.namespace)
            await self._cache.hset(key, machine.id, machine.to_cache_dict())
            count += 1

        logger.info(f"机器池加载完成，共 {count} 台机器")
        return count

    async def add_machine_to_pool(self, machine: EnvMachine) -> bool:
        """
        将机器添加到缓存池

        Args:
            machine: 机器对象

        Returns:
            是否成功添加
        """
        # manual 命名空间不加入缓存
        if machine.namespace == self.MANUAL_NAMESPACE:
            return True

        # 只有 online + 启用 的机器才加入缓存
        if machine.status != "online" or not machine.available:
            return await self.remove_machine_from_pool(machine)

        key = self._make_pool_key(machine.namespace)
        await self._cache.hset(key, machine.id, machine.to_cache_dict())
        logger.debug(f"机器加入缓存: {machine.id}")
        return True

    async def remove_machine_from_pool(self, machine: EnvMachine) -> bool:
        """
        从缓存池移除机器

        Args:
            machine: 机器对象

        Returns:
            是否成功移除
        """
        if machine.namespace == self.MANUAL_NAMESPACE:
            return True

        key = self._make_pool_key(machine.namespace)
        await self._cache.hdel(key, machine.id)
        logger.debug(f"机器移出缓存: {machine.id}")
        return True

    async def update_machine_in_pool(self, machine: EnvMachine) -> bool:
        """
        更新缓存池中的机器

        Args:
            machine: 机器对象

        Returns:
            是否成功更新
        """
        # 根据状态决定是添加还是移除
        if machine.status == "online" and machine.available:
            return await self.add_machine_to_pool(machine)
        else:
            return await self.remove_machine_from_pool(machine)

    async def get_pool_machines(self, namespace: str) -> Dict[str, Dict[str, Any]]:
        """
        获取指定命名空间的所有机器

        Args:
            namespace: 命名空间

        Returns:
            机器字典 {machine_id: machine_info}
        """
        key = self._make_pool_key(namespace)
        data = await self._cache.hgetall(key)

        if not data:
            return {}

        # CacheManager.hgetall 已经解析了 JSON，直接返回
        return data

    async def allocate_machines(
        self,
        namespace: str,
        request: Dict[str, str],
        used_ips: Set[str],
        used_sns: Set[str]
    ) -> tuple:
        """
        分配机器

        Args:
            namespace: 命名空间
            request: 请求 {"userA": "windows", "userB": "web"}
            used_ips: 已使用的 IP 集合
            used_sns: 已使用的 device_sn 集合

        Returns:
            (分配结果, 是否成功)
        """
        # 获取候选机器
        namespace_machines = await self.get_pool_machines(namespace)
        public_machines = await self.get_pool_machines(self.PUBLIC_NAMESPACE)

        result = {}

        for user_key, mark in request.items():
            machine = None

            # 优先从 namespace 池分配
            machine = self._find_available_machine(
                namespace_machines, mark, used_ips, used_sns
            )

            # 不够时从 public 池补充
            if not machine:
                machine = self._find_available_machine(
                    public_machines, mark, used_ips, used_sns
                )

            if not machine:
                logger.warning(f"机器不足，无法分配: {user_key} -> {mark}")
                return None, False

            # 记录占用
            if machine["device_type"] in ("android", "ios"):
                used_sns.add(machine["device_sn"])
            else:
                used_ips.add(machine["ip"])

            result[user_key] = machine

        return result, True

    def _find_available_machine(
        self,
        machines: Dict[str, Dict[str, Any]],
        mark: str,
        used_ips: Set[str],
        used_sns: Set[str]
    ) -> Optional[Dict[str, Any]]:
        """
        查找可用的机器

        Args:
            machines: 机器字典
            mark: 需要的标签
            used_ips: 已使用的 IP 集合
            used_sns: 已使用的 device_sn 集合

        Returns:
            可用的机器信息或 None
        """
        for mid, info in machines.items():
            # 状态必须是 online
            if info.get("status") != "online":
                continue

            # 必须启用
            if not info.get("available"):
                continue

            # 标签匹配（完全匹配）
            machine_marks = [m.strip() for m in (info.get("mark") or "").split(",")]
            if mark not in machine_marks:
                continue

            # 排除已占用
            if info["device_type"] in ("android", "ios"):
                if info.get("device_sn") in used_sns:
                    continue
            else:
                if info.get("ip") in used_ips:
                    continue

            return info

        return None

    def build_allocation_response(
        self,
        allocation: Dict[str, Dict[str, Any]],
        request: Dict[str, str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        构建分配响应

        Args:
            allocation: 分配结果
            request: 原始请求

        Returns:
            响应字典
        """
        result = {}

        for user_key, machine in allocation.items():
            mark = request[user_key]

            # 基础字段
            machine_info = {
                "id": machine["id"],
                "ip": machine["ip"],
                "port": machine["port"],
                "device_type": machine["device_type"],
                "device_sn": machine.get("device_sn"),
            }

            # 合并 extra_message 中对应标签的信息
            extra_message = machine.get("extra_message") or {}
            mark_extra = extra_message.get(mark, {})

            machine_info.update(mark_extra)

            result[user_key] = machine_info

        return result


# 全局机器池管理器实例
pool_manager = PoolManager()
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/env_machine/pool_manager.py
git commit -m "feat(env_machine): 添加机器池缓存管理器"
```

---

### Task 5: 定时任务管理器 (scheduler.py)

**Files:**
- Create: `backend-fastapi/core/env_machine/scheduler.py`

- [ ] **Step 1: 创建 scheduler.py**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2026-03-24
@File: scheduler.py
@Desc: 执行机定时任务管理
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler import AsyncScheduler
from sqlalchemy import select, update

from app.database import AsyncSessionLocal
from core.env_machine.model import EnvMachine
from core.env_machine.pool_manager import pool_manager

logger = logging.getLogger(__name__)


class EnvScheduler:
    """
    执行机定时任务管理器

    管理延迟释放任务和离线检测任务
    """

    RELEASE_JOB_PREFIX = "release_"
    OFFLINE_CHECK_JOB_ID = "env_offline_check"

    _scheduler: Optional[AsyncScheduler] = None

    def set_scheduler(self, scheduler: AsyncScheduler):
        """设置调度器实例"""
        self._scheduler = scheduler

    def _get_release_job_id(self, machine_id: str) -> str:
        """获取释放任务的 ID"""
        return f"{self.RELEASE_JOB_PREFIX}{machine_id}"

    async def create_release_job(self, machine_id: str, delay_minutes: int = 1) -> bool:
        """
        创建延迟释放任务

        Args:
            machine_id: 机器 ID
            delay_minutes: 延迟时间（分钟）

        Returns:
            是否成功创建
        """
        if not self._scheduler:
            logger.error("调度器未初始化")
            return False

        job_id = self._get_release_job_id(machine_id)
        run_time = datetime.now() + timedelta(minutes=delay_minutes)

        try:
            # APScheduler 4.x: 先配置任务，再添加调度
            await self._scheduler.configure_task(
                job_id,
                func=self._release_machine_job,
                kwargs={"machine_id": machine_id}
            )

            await self._scheduler.add_schedule(
                func_or_task_id=job_id,
                trigger=DateTrigger(run_date=run_time),
                id=job_id,
            )

            logger.debug(f"创建延迟释放任务: {job_id}, 执行时间: {run_time}")
            return True
        except Exception as e:
            logger.error(f"创建延迟释放任务失败 {job_id}: {str(e)}")
            return False

    async def delay_release_job(self, machine_id: str, delay_minutes: int = 1) -> bool:
        """
        延迟释放任务

        Args:
            machine_id: 机器 ID
            delay_minutes: 延迟时间（分钟）

        Returns:
            是否成功延迟
        """
        if not self._scheduler:
            logger.error("调度器未初始化")
            return False

        job_id = self._get_release_job_id(machine_id)
        run_time = datetime.now() + timedelta(minutes=delay_minutes)

        try:
            # 移除旧调度，添加新调度
            try:
                await self._scheduler.remove_schedule(job_id)
            except Exception:
                pass

            await self._scheduler.add_schedule(
                func_or_task_id=job_id,
                trigger=DateTrigger(run_date=run_time),
                id=job_id,
            )

            logger.debug(f"延迟释放任务: {job_id}, 新执行时间: {run_time}")
            return True
        except Exception as e:
            logger.error(f"延迟释放任务失败 {job_id}: {str(e)}")
            return False

    async def cancel_release_job(self, machine_id: str) -> bool:
        """
        取消释放任务

        Args:
            machine_id: 机器 ID

        Returns:
            是否成功取消
        """
        if not self._scheduler:
            return False

        job_id = self._get_release_job_id(machine_id)

        try:
            await self._scheduler.remove_schedule(job_id)
            logger.debug(f"取消释放任务: {job_id}")
            return True
        except Exception:
            # 任务不存在时忽略
            return False

    async def _release_machine_job(self, machine_id: str):
        """
        释放机器任务（内部方法）

        Args:
            machine_id: 机器 ID
        """
        logger.info(f"执行延迟释放任务: {machine_id}")

        try:
            async with AsyncSessionLocal() as db:
                # 查询机器
                result = await db.execute(
                    select(EnvMachine).where(EnvMachine.id == machine_id)
                )
                machine = result.scalar_one_or_none()

                if not machine:
                    logger.warning(f"机器不存在: {machine_id}")
                    return

                # 只有 using 状态才释放
                if machine.status == "using":
                    machine.status = "online"
                    await db.commit()

                    # 更新缓存
                    await pool_manager.update_machine_in_pool(machine)
                    logger.info(f"机器已释放: {machine_id}")
                else:
                    logger.debug(f"机器状态非 using，跳过释放: {machine_id}, 状态: {machine.status}")

        except Exception as e:
            logger.error(f"执行延迟释放任务失败 {machine_id}: {str(e)}")

    async def start_offline_check(self) -> bool:
        """
        启动离线检测任务

        Returns:
            是否成功启动
        """
        if not self._scheduler:
            logger.error("调度器未初始化")
            return False

        try:
            # 注册任务
            await self._scheduler.configure_task(
                self.OFFLINE_CHECK_JOB_ID,
                func=self._offline_check_job
            )

            # 添加调度（每 2 分钟）
            await self._scheduler.add_schedule(
                func_or_task_id=self.OFFLINE_CHECK_JOB_ID,
                trigger=IntervalTrigger(minutes=2),
                id=self.OFFLINE_CHECK_JOB_ID,
            )

            logger.info("离线检测任务已启动（每 2 分钟）")
            return True
        except Exception as e:
            logger.error(f"启动离线检测任务失败: {str(e)}")
            return False

    async def _offline_check_job(self):
        """
        离线检测任务（内部方法）
        """
        logger.info("执行离线检测任务")

        try:
            async with AsyncSessionLocal() as db:
                threshold = datetime.now() - timedelta(minutes=10)

                # 查询 sync_time 超过 10 分钟的机器
                result = await db.execute(
                    select(EnvMachine).where(
                        EnvMachine.sync_time < threshold,
                        EnvMachine.status.in_(["online", "using"]),
                        EnvMachine.is_deleted == False  # noqa: E712
                    )
                )
                machines = result.scalars().all()

                if not machines:
                    logger.debug("没有需要离线的机器")
                    return

                for machine in machines:
                    # 取消延迟释放任务（如果有）
                    await self.cancel_release_job(machine.id)

                    # 更新状态
                    machine.status = "offline"

                await db.commit()

                # 同步 Redis 缓存
                for machine in machines:
                    await pool_manager.remove_machine_from_pool(machine)

                logger.info(f"离线检测完成，共 {len(machines)} 台机器离线")

        except Exception as e:
            logger.error(f"执行离线检测任务失败: {str(e)}")

    async def reset_using_machines(self) -> int:
        """
        重置所有 using 状态的机器为 online

        用于服务启动时恢复状态

        Returns:
            重置的机器数量
        """
        try:
            async with AsyncSessionLocal() as db:
                # 查询所有 using 状态的机器
                result = await db.execute(
                    select(EnvMachine).where(
                        EnvMachine.status == "using",
                        EnvMachine.is_deleted == False  # noqa: E712
                    )
                )
                machines = result.scalars().all()

                count = len(machines)

                if count > 0:
                    # 批量更新
                    await db.execute(
                        update(EnvMachine)
                        .where(EnvMachine.status == "using")
                        .values(status="online")
                    )
                    await db.commit()

                    logger.info(f"重置 {count} 台 using 状态的机器为 online")

                return count

        except Exception as e:
            logger.error(f"重置 using 机器失败: {str(e)}")
            return 0


# 全局调度器实例
env_scheduler = EnvScheduler()
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/env_machine/scheduler.py
git commit -m "feat(env_machine): 添加定时任务管理器"
```

---

### Task 6: 基础服务层 (service.py)

**Files:**
- Create: `backend-fastapi/core/env_machine/service.py`

- [ ] **Step 1: 创建 service.py**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2026-03-24
@File: service.py
@Desc: EnvMachine Service - 执行机基础服务层
"""
from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_service import BaseService
from core.env_machine.model import EnvMachine


class EnvMachineService(BaseService[EnvMachine, dict, dict]):
    """
    执行机服务层
    继承 BaseService，提供基础 CRUD 操作
    """

    model = EnvMachine

    @classmethod
    async def get_by_unique_key(
        cls,
        db: AsyncSession,
        namespace: str,
        ip: str,
        device_type: str,
        device_sn: Optional[str] = None
    ) -> Optional[EnvMachine]:
        """
        根据唯一键查询机器

        Args:
            db: 数据库会话
            namespace: 命名空间
            ip: IP 地址
            device_type: 设备类型
            device_sn: 设备 SN

        Returns:
            机器对象或 None
        """
        conditions = [
            EnvMachine.namespace == namespace,
            EnvMachine.ip == ip,
            EnvMachine.device_type == device_type,
            EnvMachine.is_deleted == False,  # noqa: E712
        ]

        if device_sn:
            conditions.append(EnvMachine.device_sn == device_sn)
        else:
            conditions.append(EnvMachine.device_sn.is_(None))

        result = await db.execute(
            select(EnvMachine).where(and_(*conditions))
        )
        return result.scalar_one_or_none()

    @classmethod
    async def register_machine(
        cls,
        db: AsyncSession,
        namespace: str,
        ip: str,
        port: str,
        device_type: str,
        device_sn: Optional[str] = None,
        version: Optional[str] = None
    ) -> EnvMachine:
        """
        注册或更新机器

        Args:
            db: 数据库会话
            namespace: 命名空间
            ip: IP 地址
            port: 端口
            device_type: 设备类型
            device_sn: 设备 SN
            version: 版本

        Returns:
            机器对象
        """
        now = datetime.now()

        # 查询是否存在
        machine = await cls.get_by_unique_key(db, namespace, ip, device_type, device_sn)

        if machine:
            # 更新
            machine.sync_time = now
            machine.status = "online"
            machine.port = port
            if version:
                machine.version = version
        else:
            # 新增
            machine = EnvMachine(
                namespace=namespace,
                ip=ip,
                port=port,
                device_type=device_type,
                device_sn=device_sn,
                version=version,
                status="online",
                available=False,  # 新注册的机器默认不启用
                sync_time=now,
            )
            db.add(machine)

        await db.commit()
        await db.refresh(machine)

        return machine

    @classmethod
    async def update_status(
        cls,
        db: AsyncSession,
        machine_id: str,
        status: str
    ) -> Optional[EnvMachine]:
        """
        更新机器状态

        Args:
            db: 数据库会话
            machine_id: 机器 ID
            status: 新状态

        Returns:
            更新后的机器对象或 None
        """
        machine = await cls.get_by_id(db, machine_id)
        if not machine:
            return None

        machine.status = status
        await db.commit()
        await db.refresh(machine)

        return machine

    @classmethod
    async def update_keepusing_time(
        cls,
        db: AsyncSession,
        machine_id: str
    ) -> Optional[EnvMachine]:
        """
        更新保持使用时间

        Args:
            db: 数据库会话
            machine_id: 机器 ID

        Returns:
            更新后的机器对象或 None
        """
        machine = await cls.get_by_id(db, machine_id)
        if not machine:
            return None

        machine.last_keepusing_time = datetime.now()
        await db.commit()
        await db.refresh(machine)

        return machine

    @classmethod
    async def get_machines_by_ids(
        cls,
        db: AsyncSession,
        machine_ids: List[str]
    ) -> List[EnvMachine]:
        """
        批量获取机器

        Args:
            db: 数据库会话
            machine_ids: 机器 ID 列表

        Returns:
            机器列表
        """
        if not machine_ids:
            return []

        result = await db.execute(
            select(EnvMachine).where(
                EnvMachine.id.in_(machine_ids),
                EnvMachine.is_deleted == False  # noqa: E712
            )
        )
        return list(result.scalars().all())
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/env_machine/service.py
git commit -m "feat(env_machine): 添加基础服务层"
```

---

### Task 7: API 路由层 (api.py)

**Files:**
- Create: `backend-fastapi/core/env_machine/api.py`

- [ ] **Step 1: 创建 api.py**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2026-03-24
@File: api.py
@Desc: EnvMachine API - 执行机管理接口
"""
import logging
from datetime import datetime
from typing import Dict

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from core.env_machine.service import EnvMachineService
from core.env_machine.pool_manager import pool_manager
from core.env_machine.lock_manager import lock_manager
from core.env_machine.scheduler import env_scheduler
from core.env_machine.schema import (
    EnvRegisterRequest,
    EnvSuccessResponse,
    EnvFailResponse,
    EnvMachineIdItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/env", tags=["执行机管理"])


# ==================== 注册接口 ====================

@router.post("/register", response_model=EnvSuccessResponse, summary="机器注册")
async def register_machine(
    data: EnvRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    机器注册接口

    平台每5分钟会收到 worker 的注册信息，根据 namespace、ip、device_type、device_sn 查询：
    1. 不存在则插入（状态 online，启用 False）
    2. 存在则更新 sync_time、status=online
    """
    try:
        # 遍历设备类型
        for device_type, device_sns in data.devices.items():
            if device_type in ("windows", "mac"):
                # windows/mac：device_sn 为 null，每个 IP 插入一条记录
                machine = await EnvMachineService.register_machine(
                    db=db,
                    namespace=data.namespace,
                    ip=data.ip,
                    port=data.port,
                    device_type=device_type,
                    device_sn=None,
                    version=data.version
                )
                # 同步更新 Redis 缓存
                await pool_manager.update_machine_in_pool(machine)

            elif device_type in ("android", "ios"):
                # android/ios：根据 device_sn 列表，每个 sn 插入一条记录
                for device_sn in device_sns:
                    if device_sn:
                        machine = await EnvMachineService.register_machine(
                            db=db,
                            namespace=data.namespace,
                            ip=data.ip,
                            port=data.port,
                            device_type=device_type,
                            device_sn=device_sn,
                            version=data.version
                        )
                        # 同步更新 Redis 缓存
                        await pool_manager.update_machine_in_pool(machine)

        return EnvSuccessResponse(status="success", data=None)

    except Exception as e:
        logger.error(f"机器注册失败: {str(e)}")
        return EnvFailResponse(status="fail", result=str(e))


# ==================== 申请接口 ====================

@router.post("/{namespace}/application", summary="机器申请")
async def apply_machines(
    namespace: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    机器申请接口

    根据 namespace 查询机器列表，根据请求中的 user key 和标签分配机器。
    优先使用 namespace 机器，不够时从 public 补充。
    """
    try:
        # 解析请求体（动态 key）
        body = await request.json()

        if not body:
            return EnvFailResponse(status="fail", result="invalid request")

        # 确定需要锁定的命名空间
        namespaces_to_lock = [namespace]
        if namespace != "public":
            namespaces_to_lock.append("public")

        # 获取分布式锁
        if not await lock_manager.acquire_locks(namespaces_to_lock):
            return EnvFailResponse(status="fail", result="system busy, please retry")

        try:
            # 分配机器
            used_ips = set()
            used_sns = set()

            allocation, success = await pool_manager.allocate_machines(
                namespace=namespace,
                request=body,
                used_ips=used_ips,
                used_sns=used_sns
            )

            if not success:
                return EnvFailResponse(status="fail", result="env not enough")

            # 更新数据库状态
            machine_ids = [m["id"] for m in allocation.values()]
            machines = await EnvMachineService.get_machines_by_ids(db, machine_ids)

            now = datetime.now()
            for machine in machines:
                machine.status = "using"
                machine.last_keepusing_time = now

                # 从缓存移除
                await pool_manager.remove_machine_from_pool(machine)

                # 创建延迟释放任务
                await env_scheduler.create_release_job(machine.id)

            await db.commit()

            # 构建响应
            response_data = pool_manager.build_allocation_response(allocation, body)

            return EnvSuccessResponse(status="success", data=response_data)

        finally:
            # 释放锁
            await lock_manager.release_locks(namespaces_to_lock)

    except Exception as e:
        logger.error(f"机器申请失败: {str(e)}")
        return EnvFailResponse(status="fail", result=str(e))


# ==================== 保持使用接口 ====================

@router.post("/keepusing", response_model=EnvSuccessResponse, summary="保持使用")
async def keepusing_machines(
    data: list[EnvMachineIdItem],
    db: AsyncSession = Depends(get_db)
):
    """
    保持使用接口

    更新 last_keepusing_time，延迟释放任务执行时间。
    """
    try:
        for item in data:
            # 更新保持使用时间
            machine = await EnvMachineService.update_keepusing_time(db, item.id)

            if machine and machine.status == "using":
                # 延迟释放任务
                await env_scheduler.delay_release_job(item.id)

        return EnvSuccessResponse(status="success", data=None)

    except Exception as e:
        logger.error(f"保持使用失败: {str(e)}")
        return EnvFailResponse(status="fail", result=str(e))


# ==================== 释放接口 ====================

@router.post("/release", response_model=EnvSuccessResponse, summary="释放机器")
async def release_machines(
    data: list[EnvMachineIdItem],
    db: AsyncSession = Depends(get_db)
):
    """
    释放机器接口

    取消延迟释放任务，更新状态为 online（如果当前是 offline 则不变）。
    """
    try:
        for item in data:
            machine = await EnvMachineService.get_by_id(db, item.id)

            if not machine:
                continue

            # 取消延迟释放任务
            await env_scheduler.cancel_release_job(item.id)

            # 如果状态是 using，更新为 online
            if machine.status == "using":
                machine.status = "online"
                await db.commit()
                await db.refresh(machine)

            # 同步更新 Redis 缓存
            await pool_manager.update_machine_in_pool(machine)

        return EnvSuccessResponse(status="success", data=None)

    except Exception as e:
        logger.error(f"释放机器失败: {str(e)}")
        return EnvFailResponse(status="fail", result=str(e))
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/env_machine/api.py
git commit -m "feat(env_machine): 添加 API 路由层"
```

---

### Task 8: 注册路由

**Files:**
- Modify: `backend-fastapi/core/router.py`

- [ ] **Step 1: 修改 router.py 添加路由注册**

在 `backend-fastapi/core/router.py` 中：

1. 在导入部分添加：
```python
from core.env_machine.api import router as env_machine_router
```

2. 在注册部分添加：
```python
router.include_router(env_machine_router)
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/router.py
git commit -m "feat(env_machine): 注册执行机管理路由"
```

---

### Task 9: 添加认证白名单

**Files:**
- Modify: `backend-fastapi/utils/auth_middleware.py`

- [ ] **Step 1: 修改 auth_middleware.py 添加白名单**

在 `DEFAULT_WHITE_LIST` 中添加执行机管理接口的白名单：

```python
DEFAULT_WHITE_LIST = [
    # 认证相关
    "/api/core/login",
    "/api/core/refresh_token",
    # 文档相关
    "/docs",
    "/redoc",
    "/openapi.json",
    # 健康检查
    "/",
    "/health",
    # 执行机管理接口（供外部 worker 调用）
    "/api/core/env/register",
]
```

在 `DEFAULT_WHITE_LIST_PATTERNS` 中添加正则匹配：

```python
DEFAULT_WHITE_LIST_PATTERNS = [
    r"^/docs.*",
    r"^/redoc.*",
    *OAUTH_WHITE_LIST_PATTERNS,
    *WEBSOCKET_WHITE_LIST_PATTERNS,
    # 执行机管理接口
    r"^/api/core/env/.*",  # 所有执行机管理接口
]
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/utils/auth_middleware.py
git commit -m "feat(env_machine): 添加执行机管理接口认证白名单"
```

---

### Task 10: 服务启动初始化

**Files:**
- Modify: `backend-fastapi/main.py`

- [ ] **Step 1: 修改 main.py 添加启动初始化**

在 `lifespan` 函数中，在 `await scheduler_service.load_jobs_from_db()` 之后添加：

```python
# 初始化执行机模块
from core.env_machine.scheduler import env_scheduler
from core.env_machine.pool_manager import pool_manager
from app.database import AsyncSessionLocal

# 设置调度器
env_scheduler.set_scheduler(scheduler)

# 重置 using 状态的机器
await env_scheduler.reset_using_machines()

# 加载机器池到 Redis
async with AsyncSessionLocal() as db:
    await pool_manager.load_pool_from_db(db)

# 启动离线检测任务
await env_scheduler.start_offline_check()
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/main.py
git commit -m "feat(env_machine): 添加服务启动初始化"
```

---

### Task 11: 数据库迁移

**Files:**
- Create: `backend-fastapi/alembic/versions/xxx_add_env_machine_table.py`

- [ ] **Step 1: 生成迁移文件**

运行命令：
```bash
cd backend-fastapi && alembic revision --autogenerate -m "add env_machine table"
```

- [ ] **Step 2: 执行迁移**

运行命令：
```bash
cd backend-fastapi && alembic upgrade head
```

- [ ] **Step 3: 提交**

```bash
git add backend-fastapi/alembic/versions/
git commit -m "feat(env_machine): 添加数据库迁移文件"
```

---

### Task 12: 最终提交

- [ ] **Step 1: 确认所有文件已提交**

```bash
git status
```

- [ ] **Step 2: 推送到远程仓库（如果需要）**

```bash
git push origin main
```

---

## 测试清单

实现完成后需要测试：

1. **注册接口**
   - POST `/api/core/env/register`
   - 测试新机器注册
   - 测试已存在机器更新

2. **申请接口**
   - POST `/api/core/env/{namespace}/application`
   - 测试机器分配
   - 测试机器不足场景
   - 测试 public 机器借用

3. **保持使用接口**
   - POST `/api/core/env/keepusing`
   - 测试延迟释放任务

4. **释放接口**
   - POST `/api/core/env/release`
   - 测试状态更新
   - 测试缓存同步

5. **定时任务**
   - 测试延迟释放任务执行
   - 测试离线检测任务