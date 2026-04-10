# Worker 升级管理功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Worker 执行机升级管理功能，支持版本配置、批量升级、延迟升级队列和状态管理。

**Architecture:** 后端采用 FastAPI + SQLAlchemy，新增 upgrade 子模块处理升级逻辑；前端采用 Vue 3 + Element Plus，新增升级管理页面。核心改动在 pool_manager.py 中处理 upgrading 状态过滤和延迟升级触发。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Vue 3, Element Plus, TypeScript, httpx（调用 Worker）

**Spec:** `docs/superpowers/specs/2026-04-10-worker-upgrade-design.md`

---

## 文件结构

### 后端新增
- `backend-fastapi/core/env_machine/upgrade_model.py` - 数据模型
- `backend-fastapi/core/env_machine/upgrade_schema.py` - Schema 定义
- `backend-fastapi/core/env_machine/upgrade_service.py` - 服务层
- `backend-fastapi/core/env_machine/upgrade_api.py` - API 路由

### 后端修改
- `backend-fastapi/core/env_machine/model.py` - 状态扩展
- `backend-fastapi/core/env_machine/pool_manager.py` - 申请/释放逻辑
- `backend-fastapi/core/env_machine/api.py` - 路由注册
- `backend-fastapi/core/router.py` - 模块注册
- `backend-fastapi/alembic/versions/20260410_add_upgrade_tables.py` - 迁移脚本

### 前端新增
- `web/apps/web-ele/src/views/env-machine/upgrade.vue` - 升级管理页面
- `web/apps/web-ele/src/api/core/env-machine-upgrade.ts` - API 接口
- `web/apps/web-ele/src/router/routes/modules/env-machine-upgrade.ts` - 路由配置

### 前端修改
- `web/apps/web-ele/src/views/env-machine/index.vue` - 升级按钮
- `web/apps/web-ele/src/views/env-machine/types.ts` - 状态定义

---

## Task 1: 创建数据库模型

**Files:**
- Create: `backend-fastapi/core/env_machine/upgrade_model.py`
- Modify: `backend-fastapi/core/env_machine/model.py`

- [ ] **Step 1: 创建 upgrade_model.py 文件**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time: 2026-04-10
@File: upgrade_model.py
@Desc: Worker 升级管理模型
"""
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Index

from app.base_model import BaseModel


class WorkerUpgradeConfig(BaseModel):
    """Worker 升级配置表 - 存储 Windows/Mac 最新版本信息"""
    __tablename__ = "worker_upgrade_config"

    device_type = Column(String(20), nullable=False, unique=True, comment="设备类型: windows/mac")
    version = Column(String(32), nullable=False, comment="目标版本号(时间戳格式)")
    download_url = Column(String(512), nullable=False, comment="安装包下载地址")
    note = Column(Text, nullable=True, comment="备注")


class WorkerUpgradeQueue(BaseModel):
    """Worker 升级队列 - 记录等待升级的机器"""
    __tablename__ = "worker_upgrade_queue"

    machine_id = Column(String(36), nullable=False, index=True, comment="机器ID")
    target_version = Column(String(32), nullable=False, comment="目标版本号")
    status = Column(String(20), nullable=False, default="waiting", comment="状态: waiting/completed/failed")
    device_type = Column(String(20), nullable=False, comment="设备类型")
    namespace = Column(String(64), nullable=False, comment="机器分类")
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment="入队时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")

    __table_args__ = (
        Index("ix_upgrade_queue_status", "status"),
    )
```

- [ ] **Step 2: 修改 model.py 新增 upgrading 状态**

在 `backend-fastapi/core/env_machine/model.py` 的 STATUS_DISPLAY 中新增：

```python
STATUS_DISPLAY = {
    "online": "在线",
    "using": "使用中",
    "offline": "离线",
    "upgrading": "升级中",  # 新增
}
```

- [ ] **Step 3: Commit**

```bash
git add backend-fastapi/core/env_machine/upgrade_model.py backend-fastapi/core/env_machine/model.py
git commit -m "feat(env_machine): add upgrade model and upgrading status"
```

---

## Task 2: 创建数据库迁移脚本

**Files:**
- Create: `backend-fastapi/alembic/versions/20260410_add_upgrade_tables.py`

- [ ] **Step 1: 生成迁移脚本**

```bash
cd backend-fastapi && alembic revision -m "add upgrade tables"
```

- [ ] **Step 2: 编辑迁移脚本内容**

打开生成的迁移文件，修改为：

```python
"""add upgrade tables

Revision ID: <生成的ID>
Revises: <上一个版本>
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa


def upgrade():
    # 创建 worker_upgrade_config 表
    op.create_table(
        'worker_upgrade_config',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('device_type', sa.String(20), nullable=False, unique=True),
        sa.Column('version', sa.String(32), nullable=False),
        sa.Column('download_url', sa.String(512), nullable=False),
        sa.Column('note', sa.Text, nullable=True),
        sa.Column('sort', sa.Integer, default=0),
        sa.Column('is_deleted', sa.Boolean, default=False),
        sa.Column('sys_create_datetime', sa.DateTime),
        sa.Column('sys_update_datetime', sa.DateTime),
        sa.Column('sys_creator_id', sa.String(36)),
        sa.Column('sys_modifier_id', sa.String(36)),
    )

    # 创建 worker_upgrade_queue 表
    op.create_table(
        'worker_upgrade_queue',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('machine_id', sa.String(36), nullable=False),
        sa.Column('target_version', sa.String(32), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='waiting'),
        sa.Column('device_type', sa.String(20), nullable=False),
        sa.Column('namespace', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('sort', sa.Integer, default=0),
        sa.Column('is_deleted', sa.Boolean, default=False),
        sa.Column('sys_create_datetime', sa.DateTime),
        sa.Column('sys_update_datetime', sa.DateTime),
        sa.Column('sys_creator_id', sa.String(36)),
        sa.Column('sys_modifier_id', sa.String(36)),
    )
    op.create_index('ix_upgrade_queue_status', 'worker_upgrade_queue', ['status'])
    op.create_index('ix_upgrade_queue_machine_id', 'worker_upgrade_queue', ['machine_id'])

    # 初始化配置数据
    op.execute("""
        INSERT INTO worker_upgrade_config (id, device_type, version, download_url, sort, is_deleted)
        VALUES ('windows-config-id', 'windows', '20260410150000', '', 0, False)
    """)
    op.execute("""
        INSERT INTO worker_upgrade_config (id, device_type, version, download_url, sort, is_deleted)
        VALUES ('mac-config-id', 'mac', '20260410150000', '', 0, False)
    """)


def downgrade():
    op.drop_table('worker_upgrade_queue')
    op.drop_table('worker_upgrade_config')
```

- [ ] **Step 3: 执行迁移**

```bash
cd backend-fastapi && alembic upgrade head
```

- [ ] **Step 4: Commit**

```bash
git add backend-fastapi/alembic/versions/
git commit -m "feat(env_machine): add upgrade tables migration"
```

---

## Task 3: 创建 Schema 定义

**Files:**
- Create: `backend-fastapi/core/env_machine/upgrade_schema.py`

- [ ] **Step 1: 创建 upgrade_schema.py 文件**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time: 2026-04-10
@File: upgrade_schema.py
@Desc: Worker 升级管理 Schema
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class UpgradeConfigResponse(BaseModel):
    """升级配置响应"""
    id: str = Field(..., description="配置ID")
    device_type: str = Field(..., description="设备类型: windows/mac")
    version: str = Field(..., description="目标版本号")
    download_url: str = Field(..., description="下载地址")
    note: Optional[str] = Field(None, description="备注")

    model_config = {"from_attributes": True}


class UpgradeConfigUpdateRequest(BaseModel):
    """更新升级配置请求"""
    version: str = Field(..., description="目标版本号")
    download_url: str = Field(..., description="下载地址")
    note: Optional[str] = Field(None, description="备注")


class WorkerUpgradeInfo(BaseModel):
    """Worker 获取升级信息响应"""
    version: str = Field(..., description="目标版本号")
    download_url: str = Field(..., description="下载地址")


class StartUpgradeRequest(BaseModel):
    """Worker 手动触发升级请求"""
    machine_id: str = Field(..., description="机器ID")
    version: str = Field(..., description="目标版本号")


class BatchUpgradeRequest(BaseModel):
    """批量升级请求"""
    machine_ids: Optional[List[str]] = Field(None, description="指定机器ID列表")
    namespace: Optional[str] = Field(None, description="设备类别筛选")
    device_type: Optional[str] = Field(None, description="设备类型筛选")


class UpgradeDetail(BaseModel):
    """升级详情"""
    machine_id: str = Field(..., description="机器ID")
    ip: str = Field(..., description="IP地址")
    status: str = Field(..., description="状态: upgraded/waiting/skipped/failed")
    message: str = Field(..., description="消息")


class BatchUpgradeResponse(BaseModel):
    """批量升级响应"""
    upgraded_count: int = Field(default=0, description="已升级数量")
    waiting_count: int = Field(default=0, description="等待队列数量")
    skipped_count: int = Field(default=0, description="跳过数量")
    failed_count: int = Field(default=0, description="失败数量")
    details: List[UpgradeDetail] = Field(default_factory=list, description="详情列表")


class UpgradeQueueItem(BaseModel):
    """升级队列项"""
    id: str = Field(..., description="队列ID")
    machine_id: str = Field(..., description="机器ID")
    ip: Optional[str] = Field(None, description="IP地址")
    device_type: str = Field(..., description="设备类型")
    target_version: str = Field(..., description="目标版本")
    status: str = Field(..., description="状态")
    created_at: Optional[datetime] = Field(None, description="入队时间")

    model_config = {"from_attributes": True}


class UpgradePreviewResponse(BaseModel):
    """升级预览响应"""
    upgradable_count: int = Field(default=0, description="可升级数量")
    waiting_count: int = Field(default=0, description="待队列数量")
    latest_count: int = Field(default=0, description="已最新数量")
    offline_count: int = Field(default=0, description="离线数量")
    machines: List[dict] = Field(default_factory=list, description="机器列表")
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/env_machine/upgrade_schema.py
git commit -m "feat(env_machine): add upgrade schema definitions"
```

---

## Task 4: 创建服务层逻辑

**Files:**
- Create: `backend-fastapi/core/env_machine/upgrade_service.py`

- [ ] **Step 1: 创建 upgrade_service.py 文件**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time: 2026-04-10
@File: upgrade_service.py
@Desc: Worker 升级管理服务层
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.env_machine.model import EnvMachine
from core.env_machine.upgrade_model import WorkerUpgradeConfig, WorkerUpgradeQueue
from core.env_machine.upgrade_schema import (
    UpgradeDetail,
    BatchUpgradeResponse,
    UpgradeQueueItem,
)

logger = logging.getLogger(__name__)

# Worker 升级接口超时时间（秒）
WORKER_UPGRADE_TIMEOUT = 10


class WorkerUpgradeConfigService:
    """升级配置服务"""

    @staticmethod
    async def get_all(db: AsyncSession) -> List[WorkerUpgradeConfig]:
        """获取所有配置"""
        result = await db.execute(
            select(WorkerUpgradeConfig).where(WorkerUpgradeConfig.is_deleted == False)
        )
        return result.scalars().all()

    @staticmethod
    async def get_by_device_type(db: AsyncSession, device_type: str) -> Optional[WorkerUpgradeConfig]:
        """根据设备类型获取配置"""
        result = await db.execute(
            select(WorkerUpgradeConfig).where(
                and_(
                    WorkerUpgradeConfig.device_type == device_type,
                    WorkerUpgradeConfig.is_deleted == False
                )
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update(db: AsyncSession, config_id: str, version: str, download_url: str, note: Optional[str] = None) -> WorkerUpgradeConfig:
        """更新配置"""
        result = await db.execute(
            select(WorkerUpgradeConfig).where(WorkerUpgradeConfig.id == config_id)
        )
        config = result.scalar_one_or_none()
        if config:
            config.version = version
            config.download_url = download_url
            config.note = note
            await db.commit()
            await db.refresh(config)
        return config


class WorkerUpgradeQueueService:
    """升级队列服务"""

    @staticmethod
    async def get_waiting_by_machine_id(db: AsyncSession, machine_id: str) -> Optional[WorkerUpgradeQueue]:
        """获取机器的等待队列项"""
        result = await db.execute(
            select(WorkerUpgradeQueue).where(
                and_(
                    WorkerUpgradeQueue.machine_id == machine_id,
                    WorkerUpgradeQueue.status == "waiting",
                    WorkerUpgradeQueue.is_deleted == False
                )
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def add_to_queue(db: AsyncSession, machine_id: str, target_version: str, device_type: str, namespace: str) -> WorkerUpgradeQueue:
        """添加到队列"""
        queue_item = WorkerUpgradeQueue(
            machine_id=machine_id,
            target_version=target_version,
            device_type=device_type,
            namespace=namespace,
            status="waiting",
            created_at=datetime.now(),
        )
        db.add(queue_item)
        await db.commit()
        await db.refresh(queue_item)
        return queue_item

    @staticmethod
    async def mark_completed(db: AsyncSession, queue_id: str) -> None:
        """标记为完成"""
        result = await db.execute(
            select(WorkerUpgradeQueue).where(WorkerUpgradeQueue.id == queue_id)
        )
        item = result.scalar_one_or_none()
        if item:
            item.status = "completed"
            item.completed_at = datetime.now()
            await db.commit()

    @staticmethod
    async def get_list(db: AsyncSession, namespace: Optional[str] = None, status: Optional[str] = None) -> Tuple[List[WorkerUpgradeQueue], int]:
        """获取队列列表"""
        conditions = [WorkerUpgradeQueue.is_deleted == False]
        if namespace:
            conditions.append(WorkerUpgradeQueue.namespace == namespace)
        if status:
            conditions.append(WorkerUpgradeQueue.status == status)

        result = await db.execute(
            select(WorkerUpgradeQueue).where(and_(*conditions)).order_by(WorkerUpgradeQueue.created_at.desc())
        )
        items = result.scalars().all()
        return items, len(items)

    @staticmethod
    async def delete_by_id(db: AsyncSession, queue_id: str) -> bool:
        """删除队列项"""
        result = await db.execute(
            select(WorkerUpgradeQueue).where(WorkerUpgradeQueue.id == queue_id)
        )
        item = result.scalar_one_or_none()
        if item and item.status == "waiting":
            item.is_deleted = True
            await db.commit()
            return True
        return False

    @staticmethod
    async def cleanup_completed(db: AsyncSession, days: int = 7) -> int:
        """清理 completed 记录"""
        threshold = datetime.now() - timedelta(days=days)
        result = await db.execute(
            select(WorkerUpgradeQueue).where(
                and_(
                    WorkerUpgradeQueue.status == "completed",
                    WorkerUpgradeQueue.completed_at < threshold
                )
            )
        )
        items = result.scalars().all()
        count = 0
        for item in items:
            item.is_deleted = True
            count += 1
        await db.commit()
        return count

    @staticmethod
    async def mark_timeout_waiting(db: AsyncSession, hours: int = 24) -> int:
        """标记超时的 waiting 为 failed"""
        threshold = datetime.now() - timedelta(hours=hours)
        result = await db.execute(
            select(WorkerUpgradeQueue).where(
                and_(
                    WorkerUpgradeQueue.status == "waiting",
                    WorkerUpgradeQueue.created_at < threshold
                )
            )
        )
        items = result.scalars().all()
        count = 0
        for item in items:
            item.status = "failed"
            count += 1
        await db.commit()
        return count


async def send_upgrade_to_worker(machine: EnvMachine, version: str, download_url: str) -> Tuple[bool, str]:
    """调用 Worker 升级接口"""
    url = f"http://{machine.ip}:{machine.port}/worker/upgrade"
    payload = {
        "version": version,
        "download_url": download_url,
    }

    try:
        async with httpx.AsyncClient(timeout=WORKER_UPGRADE_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "upgrading":
                    return True, "升级指令已下发"
                else:
                    return False, f"Worker 返回异常状态: {data.get('status')}"
            else:
                return False, f"Worker 返回错误状态码: {response.status_code}"
    except httpx.TimeoutException:
        return False, "Worker 响应超时"
    except Exception as e:
        logger.error(f"调用 Worker 升级接口失败: {e}")
        return False, f"网络错误: {str(e)}"


class UpgradeService:
    """升级管理服务"""

    @staticmethod
    async def batch_upgrade(
        db: AsyncSession,
        machine_ids: Optional[List[str]] = None,
        namespace: Optional[str] = None,
        device_type: Optional[str] = None,
    ) -> BatchUpgradeResponse:
        """批量升级"""
        # 获取版本配置
        configs = await WorkerUpgradeConfigService.get_all(db)
        config_map = {c.device_type: c for c in configs}

        # 查询机器
        conditions = [EnvMachine.is_deleted == False, EnvMachine.available == True]
        if machine_ids:
            conditions.append(EnvMachine.id.in_(machine_ids))
        if namespace:
            conditions.append(EnvMachine.namespace == namespace)
        if device_type:
            conditions.append(EnvMachine.device_type == device_type)

        result = await db.execute(select(EnvMachine).where(and_(*conditions)))
        machines = result.scalars().all()

        response = BatchUpgradeResponse()
        
        for machine in machines:
            config = config_map.get(machine.device_type)
            if not config:
                response.skipped_count += 1
                response.details.append(UpgradeDetail(
                    machine_id=machine.id,
                    ip=machine.ip,
                    status="skipped",
                    message="未找到对应设备类型的升级配置"
                ))
                continue

            # 版本比对
            if machine.version and machine.version >= config.version:
                response.skipped_count += 1
                response.details.append(UpgradeDetail(
                    machine_id=machine.id,
                    ip=machine.ip,
                    status="skipped",
                    message="已是最新版本"
                ))
                continue

            # 状态判断
            if machine.status == "online":
                # 直接升级
                success, message = await send_upgrade_to_worker(machine, config.version, config.download_url)
                if success:
                    machine.status = "upgrading"
                    response.upgraded_count += 1
                    response.details.append(UpgradeDetail(
                        machine_id=machine.id,
                        ip=machine.ip,
                        status="upgraded",
                        message=message
                    ))
                else:
                    response.failed_count += 1
                    response.details.append(UpgradeDetail(
                        machine_id=machine.id,
                        ip=machine.ip,
                        status="failed",
                        message=message
                    ))

            elif machine.status == "using":
                # 加入队列
                await WorkerUpgradeQueueService.add_to_queue(
                    db, machine.id, config.version, machine.device_type, machine.namespace
                )
                response.waiting_count += 1
                response.details.append(UpgradeDetail(
                    machine_id=machine.id,
                    ip=machine.ip,
                    status="waiting",
                    message="机器使用中，已加入升级队列"
                ))

            else:
                # offline, upgrading 状态跳过
                response.skipped_count += 1
                response.details.append(UpgradeDetail(
                    machine_id=machine.id,
                    ip=machine.ip,
                    status="skipped",
                    message=f"机器状态为 {machine.status}，无法升级"
                ))

        await db.commit()
        return response

    @staticmethod
    async def get_preview(db: AsyncSession, namespace: Optional[str] = None, device_type: Optional[str] = None) -> dict:
        """获取升级预览"""
        configs = await WorkerUpgradeConfigService.get_all(db)
        config_map = {c.device_type: c for c in configs}

        conditions = [EnvMachine.is_deleted == False, EnvMachine.available == True]
        if namespace:
            conditions.append(EnvMachine.namespace == namespace)
        if device_type:
            conditions.append(EnvMachine.device_type == device_type)

        result = await db.execute(select(EnvMachine).where(and_(*conditions)))
        machines = result.scalars().all()

        upgradable = []
        waiting = []
        latest = []
        offline = []

        for machine in machines:
            config = config_map.get(machine.device_type)
            upgrade_status = "待升级"

            if not config:
                upgrade_status = "无配置"
            elif machine.version and machine.version >= config.version:
                upgrade_status = "已最新"
            elif machine.status == "online":
                upgrade_status = "待升级"
            elif machine.status == "using":
                upgrade_status = "待队列"
            elif machine.status == "upgrading":
                upgrade_status = "升级中"
            else:
                upgrade_status = "离线"

            machine_info = {
                "id": machine.id,
                "ip": machine.ip,
                "device_type": machine.device_type,
                "version": machine.version or "-",
                "status": machine.status,
                "upgrade_status": upgrade_status,
            }

            if upgrade_status == "待升级":
                upgradable.append(machine_info)
            elif upgrade_status == "待队列":
                waiting.append(machine_info)
            elif upgrade_status in ["已最新", "升级中"]:
                latest.append(machine_info)
            else:
                offline.append(machine_info)

        return {
            "upgradable_count": len(upgradable),
            "waiting_count": len(waiting),
            "latest_count": len(latest),
            "offline_count": len(offline),
            "machines": upgradable + waiting + latest + offline,
        }
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/env_machine/upgrade_service.py
git commit -m "feat(env_machine): add upgrade service layer"
```

---

## Task 5: 创建 API 路由

**Files:**
- Create: `backend-fastapi/core/env_machine/upgrade_api.py`
- Modify: `backend-fastapi/core/env_machine/api.py`

- [ ] **Step 1: 创建 upgrade_api.py 文件**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time: 2026-04-10
@File: upgrade_api.py
@Desc: Worker 升级管理 API 路由
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from core.env_machine.model import EnvMachine
from core.env_machine.service import EnvMachineService
from core.env_machine.upgrade_schema import (
    UpgradeConfigResponse,
    UpgradeConfigUpdateRequest,
    WorkerUpgradeInfo,
    StartUpgradeRequest,
    BatchUpgradeRequest,
    BatchUpgradeResponse,
    UpgradeQueueItem,
    UpgradePreviewResponse,
)
from core.env_machine.upgrade_service import (
    WorkerUpgradeConfigService,
    WorkerUpgradeQueueService,
    UpgradeService,
    send_upgrade_to_worker,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upgrade", tags=["Worker升级管理"])


@router.get("/config", response_model=List[UpgradeConfigResponse], summary="获取升级配置列表")
async def get_upgrade_configs(db: AsyncSession = Depends(get_db)) -> List[UpgradeConfigResponse]:
    """获取所有升级配置"""
    configs = await WorkerUpgradeConfigService.get_all(db)
    return [UpgradeConfigResponse.model_validate(c) for c in configs]


@router.put("/config/{config_id}", response_model=UpgradeConfigResponse, summary="更新升级配置")
async def update_upgrade_config(
    config_id: str,
    data: UpgradeConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> UpgradeConfigResponse:
    """更新升级配置"""
    config = await WorkerUpgradeConfigService.update(
        db, config_id, data.version, data.download_url, data.note
    )
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    return UpgradeConfigResponse.model_validate(config)


@router.get("/worker/info", response_model=WorkerUpgradeInfo, summary="Worker获取升级信息")
async def get_worker_upgrade_info(
    device_type: str,
    db: AsyncSession = Depends(get_db),
) -> WorkerUpgradeInfo:
    """Worker 获取最新版本信息"""
    config = await WorkerUpgradeConfigService.get_by_device_type(db, device_type)
    if not config:
        raise HTTPException(status_code=404, detail="未找到该设备类型的升级配置")
    return WorkerUpgradeInfo(
        version=config.version,
        download_url=config.download_url,
    )


@router.post("/worker/start", summary="Worker手动触发升级")
async def worker_start_upgrade(
    data: StartUpgradeRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Worker 手动触发升级，将状态置为 upgrading"""
    machine = await EnvMachineService.get_by_id(db, data.machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="机器不存在")

    if machine.status != "online":
        raise HTTPException(status_code=400, detail=f"机器状态为 {machine.status}，无法升级")

    # 更新状态
    machine.status = "upgrading"
    await db.commit()

    # 更新 Redis 缓存（标记不可申请）
    from core.env_machine.pool_manager import EnvPoolManager
    await EnvPoolManager.remove_machine_from_cache(machine.id, machine.namespace)

    logger.info(f"Worker 手动触发升级: machine_id={data.machine_id}, version={data.version}")

    return {"status": "success", "message": "状态已更新为升级中"}


@router.post("/batch", response_model=BatchUpgradeResponse, summary="批量升级")
async def batch_upgrade(
    data: BatchUpgradeRequest,
    db: AsyncSession = Depends(get_db),
) -> BatchUpgradeResponse:
    """批量升级机器"""
    # 参数校验
    if data.machine_ids and (data.namespace or data.device_type):
        raise HTTPException(status_code=400, detail="machine_ids 与 namespace/device_type 不能同时使用")

    if not data.machine_ids and not data.namespace and not data.device_type:
        raise HTTPException(status_code=400, detail="请指定升级范围")

    response = await UpgradeService.batch_upgrade(
        db,
        machine_ids=data.machine_ids,
        namespace=data.namespace,
        device_type=data.device_type,
    )

    logger.info(f"批量升级完成: upgraded={response.upgraded_count}, waiting={response.waiting_count}, failed={response.failed_count}")

    return response


@router.get("/preview", response_model=UpgradePreviewResponse, summary="升级预览")
async def get_upgrade_preview(
    namespace: Optional[str] = None,
    device_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> UpgradePreviewResponse:
    """获取升级预览信息"""
    preview = await UpgradeService.get_preview(db, namespace, device_type)
    return UpgradePreviewResponse(**preview)


@router.get("/queue", summary="升级队列查询")
async def get_upgrade_queue(
    namespace: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """获取升级队列列表"""
    items, total = await WorkerUpgradeQueueService.get_list(db, namespace, status)

    # 补充 IP 信息
    result_list = []
    for item in items:
        machine = await EnvMachineService.get_by_id(db, item.machine_id)
        result_list.append(UpgradeQueueItem(
            id=item.id,
            machine_id=item.machine_id,
            ip=machine.ip if machine else "-",
            device_type=item.device_type,
            target_version=item.target_version,
            status=item.status,
            created_at=item.created_at,
        ))

    return {"items": result_list, "total": total}


@router.delete("/queue/{queue_id}", summary="移除升级队列")
async def remove_upgrade_queue(
    queue_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """移除升级队列项"""
    success = await WorkerUpgradeQueueService.delete_by_id(db, queue_id)
    if not success:
        raise HTTPException(status_code=400, detail="队列项不存在或状态非 waiting")
    return {"status": "success", "message": "队列项已移除"}
```

- [ ] **Step 2: 修改 api.py 注册升级路由**

在 `backend-fastapi/core/env_machine/api.py` 文件末尾添加：

```python
from core.env_machine.upgrade_api import router as upgrade_router

# 在文件末尾注册
api_router.include_router(upgrade_router)
```

- [ ] **Step 3: Commit**

```bash
git add backend-fastapi/core/env_machine/upgrade_api.py backend-fastapi/core/env_machine/api.py
git commit -m "feat(env_machine): add upgrade API routes"
```

---

## Task 6: 修改 pool_manager 申请/释放逻辑

**Files:**
- Modify: `backend-fastapi/core/env_machine/pool_manager.py`

- [ ] **Step 1: 阅读现有 pool_manager.py 代码**

先使用 Read 工具阅读 `backend-fastapi/core/env_machine/pool_manager.py`，了解 `allocate_machines` 和 `release_machine` 方法的现有结构和位置。

- [ ] **Step 2: 修改申请逻辑，排除 upgrading 状态**

在 `allocate_machines` 方法中，找到从 Redis 缓存获取机器的循环逻辑，在现有 status 检查之后添加：

```python
# 排除 upgrading 状态的机器（升级中不可申请）
if machine.status == "upgrading":
    continue
```

- [ ] **Step 3: 在 release_machine 方法末尾添加延迟升级触发逻辑**

在现有 `release_machine` 函数的末尾（return 语句之前），添加以下代码片段：

```python
    # 检查升级队列，触发延迟升级
    from core.env_machine.upgrade_service import (
        WorkerUpgradeConfigService,
        WorkerUpgradeQueueService,
        send_upgrade_to_worker,
    )
    
    queue_item = await WorkerUpgradeQueueService.get_waiting_by_machine_id(db, machine_id)
    if queue_item:
        # 获取版本配置
        config = await WorkerUpgradeConfigService.get_by_device_type(db, queue_item.device_type)
        if config:
            # 重新获取机器对象（状态已更新为 online）
            machine = await EnvMachineService.get_by_id(db, machine_id)
            success, message = await send_upgrade_to_worker(machine, config.version, config.download_url)
            if success:
                # 更新状态为 upgrading
                machine.status = "upgrading"
                # 从缓存移除（不可申请）
                await EnvPoolManager.remove_machine_from_cache(machine_id, namespace)
                # 更新队列状态
                await WorkerUpgradeQueueService.mark_completed(db, queue_item.id)
                logger.info(f"释放后触发升级: machine_id={machine_id}")
            else:
                logger.warning(f"释放后升级失败: machine_id={machine_id}, reason={message}")
```

注意：不要覆盖整个函数，只在末尾追加这段代码。

- [ ] **Step 4: Commit**

```bash
git add backend-fastapi/core/env_machine/pool_manager.py
git commit -m "feat(env_machine): add upgrading status filter and delayed upgrade trigger"
```

---

## Task 7: 创建前端 API 接口定义

**Files:**
- Create: `web/apps/web-ele/src/api/core/env-machine-upgrade.ts`

- [ ] **Step 1: 创建 env-machine-upgrade.ts 文件**

```typescript
import { requestClient } from '#/api/request';

/**
 * 升级配置
 */
export interface UpgradeConfig {
  id: string;
  device_type: string;
  version: string;
  download_url: string;
  note?: string;
}

/**
 * Worker 升级信息
 */
export interface WorkerUpgradeInfo {
  version: string;
  download_url: string;
}

/**
 * 批量升级请求参数
 */
export interface BatchUpgradeParams {
  machine_ids?: string[];
  namespace?: string;
  device_type?: string;
}

/**
 * 升级详情
 */
export interface UpgradeDetail {
  machine_id: string;
  ip: string;
  status: string;
  message: string;
}

/**
 * 批量升级响应
 */
export interface BatchUpgradeResponse {
  upgraded_count: number;
  waiting_count: number;
  skipped_count: number;
  failed_count: number;
  details: UpgradeDetail[];
}

/**
 * 升级预览响应
 */
export interface UpgradePreviewResponse {
  upgradable_count: number;
  waiting_count: number;
  latest_count: number;
  offline_count: number;
  machines: UpgradePreviewMachine[];
}

/**
 * 升级预览机器
 */
export interface UpgradePreviewMachine {
  id: string;
  ip: string;
  device_type: string;
  version: string;
  status: string;
  upgrade_status: string;
}

/**
 * 升级队列项
 */
export interface UpgradeQueueItem {
  id: string;
  machine_id: string;
  ip: string;
  device_type: string;
  target_version: string;
  status: string;
  created_at?: string;
}

/**
 * 获取升级配置列表
 */
export async function getUpgradeConfigListApi() {
  return requestClient.get<UpgradeConfig[]>('/api/core/env/upgrade/config');
}

/**
 * 更新升级配置
 */
export async function updateUpgradeConfigApi(id: string, data: Partial<UpgradeConfig>) {
  return requestClient.put<UpgradeConfig>(`/api/core/env/upgrade/config/${id}`, data);
}

/**
 * Worker 获取升级信息
 */
export async function getWorkerUpgradeInfoApi(deviceType: string) {
  return requestClient.get<WorkerUpgradeInfo>('/api/core/env/upgrade/worker/info', {
    params: { device_type: deviceType },
  });
}

/**
 * Worker 手动触发升级
 */
export async function workerStartUpgradeApi(machineId: string, version: string) {
  return requestClient.post('/api/core/env/upgrade/worker/start', {
    machine_id: machineId,
    version,
  });
}

/**
 * 批量升级
 */
export async function batchUpgradeApi(data: BatchUpgradeParams) {
  return requestClient.post<BatchUpgradeResponse>('/api/core/env/upgrade/batch', data);
}

/**
 * 升级预览
 */
export async function getUpgradePreviewApi(namespace?: string, deviceType?: string) {
  return requestClient.get<UpgradePreviewResponse>('/api/core/env/upgrade/preview', {
    params: { namespace, device_type: deviceType },
  });
}

/**
 * 升级队列查询
 */
export async function getUpgradeQueueApi(namespace?: string, status?: string) {
  return requestClient.get<{ items: UpgradeQueueItem[]; total: number }>('/api/core/env/upgrade/queue', {
    params: { namespace, status },
  });
}

/**
 * 移除升级队列
 */
export async function removeUpgradeQueueApi(queueId: string) {
  return requestClient.delete(`/api/core/env/upgrade/queue/${queueId}`);
}
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/api/core/env-machine-upgrade.ts
git commit -m "feat(web): add upgrade API definitions"
```

---

## Task 8: 创建升级管理页面组件

**Files:**
- Create: `web/apps/web-ele/src/views/env-machine/upgrade.vue`

- [ ] **Step 1: 创建 upgrade.vue 文件**

创建完整的升级管理页面组件（包含版本配置区、批量升级区、升级队列区）。代码较长，按设计文档实现：

```vue
<script lang="ts" setup>
import type { UpgradeConfig, UpgradePreviewMachine, UpgradeQueueItem, BatchUpgradeParams } from '#/api/core/env-machine-upgrade';

import { onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElCard,
  ElCheckbox,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElPagination,
  ElSelect,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus';

import {
  getUpgradeConfigListApi,
  updateUpgradeConfigApi,
  getUpgradePreviewApi,
  batchUpgradeApi,
  getUpgradeQueueApi,
  removeUpgradeQueueApi,
} from '#/api/core/env-machine-upgrade';

import { DEVICE_TYPE_OPTIONS } from './types';

defineOptions({ name: 'EnvMachineUpgradePage' });

// 版本配置数据
const windowsConfig = ref<UpgradeConfig | null>(null);
const macConfig = ref<UpgradeConfig | null>(null);
const configLoading = ref(false);

// 批量升级筛选
const filterForm = ref({
  namespace: '',
  device_type: '',
});

// Namespace 选项
const NAMESPACE_OPTIONS = [
  { label: '全部', value: '' },
  { label: '集成验证 (meeting_gamma)', value: 'meeting_gamma' },
  { label: 'APP (meeting_app)', value: 'meeting_app' },
  { label: '音视频 (meeting_av)', value: 'meeting_av' },
  { label: '公共设备 (meeting_public)', value: 'meeting_public' },
];

// 设备类型选项（含全部）
const DEVICE_TYPE_FILTER_OPTIONS = [
  { label: '全部', value: '' },
  { label: 'Windows', value: 'windows' },
  { label: 'Mac', value: 'mac' },
];

// 预览数据
const previewData = ref<UpgradePreviewResponse | null>(null);
const previewLoading = ref(false);
const selectedMachineIds = ref<string[]>([]);

// 升级队列数据
const queueData = ref<{ items: UpgradeQueueItem[]; total: number }>({ items: [], total: 0 });
const queueLoading = ref(false);

// 确认弹窗
const confirmDialogVisible = ref(false);
const upgradeLoading = ref(false);

// 加载配置
async function loadConfigs() {
  configLoading.value = true;
  try {
    const configs = await getUpgradeConfigListApi();
    for (const config of configs) {
      if (config.device_type === 'windows') {
        windowsConfig.value = config;
      } else if (config.device_type === 'mac') {
        macConfig.value = config;
      }
    }
  } catch (error) {
    ElMessage.error('加载配置失败');
  } finally {
    configLoading.value = false;
  }
}

// 保存配置
async function saveConfig(config: UpgradeConfig | null, formData: { version: string; download_url: string; note: string }) {
  if (!config) return;
  try {
    await updateUpgradeConfigApi(config.id, {
      version: formData.version,
      download_url: formData.download_url,
      note: formData.note,
    });
    ElMessage.success('保存成功');
    await loadConfigs();
  } catch (error) {
    ElMessage.error('保存失败');
  }
}

// Windows 配置表单
const windowsForm = ref({
  version: '',
  download_url: '',
  note: '',
});

// Mac 配置表单
const macForm = ref({
  version: '',
  download_url: '',
  note: '',
});

// 加载预览
async function loadPreview() {
  previewLoading.value = true;
  try {
    const data = await getUpgradePreviewApi(
      filterForm.value.namespace || undefined,
      filterForm.value.device_type || undefined
    );
    previewData.value = data;
    selectedMachineIds.value = [];
  } catch (error) {
    ElMessage.error('加载预览失败');
  } finally {
    previewLoading.value = false;
  }
}

// 加载队列
async function loadQueue() {
  queueLoading.value = true;
  try {
    const data = await getUpgradeQueueApi();
    queueData.value = data;
  } catch (error) {
    ElMessage.error('加载队列失败');
  } finally {
    queueLoading.value = false;
  }
}

// 全选
function handleSelectAll(val: boolean) {
  if (val && previewData.value) {
    selectedMachineIds.value = previewData.value.machines
      .filter(m => m.upgrade_status === '待升级' || m.upgrade_status === '待队列')
      .map(m => m.id);
  } else {
    selectedMachineIds.value = [];
  }
}

// 打开确认弹窗
function openConfirmDialog() {
  if (selectedMachineIds.value.length === 0) {
    ElMessage.warning('请选择要升级的机器');
    return;
  }
  confirmDialogVisible.value = true;
}

// 执行批量升级
async function executeBatchUpgrade() {
  upgradeLoading.value = true;
  try {
    const params: BatchUpgradeParams = {
      machine_ids: selectedMachineIds.value,
    };
    const result = await batchUpgradeApi(params);
    
    if (result.failed_count > 0) {
      ElMessage.warning(`升级完成，但有 ${result.failed_count} 台失败`);
    } else {
      ElMessage.success(`升级成功：${result.upgraded_count} 台已升级，${result.waiting_count} 台待队列`);
    }
    
    confirmDialogVisible.value = false;
    await loadPreview();
    await loadQueue();
  } catch (error) {
    ElMessage.error('升级失败');
  } finally {
    upgradeLoading.value = false;
  }
}

// 移除队列项
async function handleRemoveQueue(item: UpgradeQueueItem) {
  ElMessageBox.confirm(`确定移除队列项 "${item.ip}" 吗？`, '确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      await removeUpgradeQueueApi(item.id);
      ElMessage.success('移除成功');
      await loadQueue();
    } catch {
      ElMessage.error('移除失败');
    }
  });
}

// 获取状态标签类型
function getStatusTagType(status: string) {
  const typeMap: Record<string, string> = {
    '待升级': 'warning',
    '已最新': 'success',
    '待队列': '',
    '离线': 'danger',
    '升级中': 'info',
  };
  return typeMap[status] || '';
}

// 初始化
onMounted(async () => {
  await loadConfigs();
  // 同步表单数据
  if (windowsConfig.value) {
    windowsForm.value = {
      version: windowsConfig.value.version,
      download_url: windowsConfig.value.download_url,
      note: windowsConfig.value.note || '',
    };
  }
  if (macConfig.value) {
    macForm.value = {
      version: macConfig.value.version,
      download_url: macConfig.value.download_url,
      note: macConfig.value.note || '',
    };
  }
  await loadPreview();
  await loadQueue();
});
</script>

<template>
  <Page auto-content-height>
    <div class="upgrade-page">
      <!-- 版本配置区 -->
      <ElCard class="config-card" shadow="never">
        <template #header>
          <span class="card-title">📦 版本配置</span>
        </template>
        <div class="config-row">
          <!-- Windows 配置 -->
          <div class="config-item">
            <ElTag type="primary" class="config-tag">Windows</ElTag>
            <ElForm label-width="80px" class="config-form">
              <ElFormItem label="目标版本">
                <ElInput v-model="windowsForm.version" placeholder="时间戳格式" />
              </ElFormItem>
              <ElFormItem label="下载地址">
                <ElInput v-model="windowsForm.download_url" placeholder="安装包下载地址" />
              </ElFormItem>
              <ElFormItem label="备注">
                <ElInput v-model="windowsForm.note" placeholder="版本说明" />
              </ElFormItem>
              <ElFormItem>
                <ElButton type="success" @click="saveConfig(windowsConfig, windowsForm)">保存配置</ElButton>
              </ElFormItem>
            </ElForm>
          </div>
          
          <!-- Mac 配置 -->
          <div class="config-item">
            <ElTag class="config-tag" color="#722ed1" style="color: #fff">Mac</ElTag>
            <ElForm label-width="80px" class="config-form">
              <ElFormItem label="目标版本">
                <ElInput v-model="macForm.version" placeholder="时间戳格式" />
              </ElFormItem>
              <ElFormItem label="下载地址">
                <ElInput v-model="macForm.download_url" placeholder="安装包下载地址" />
              </ElFormItem>
              <ElFormItem label="备注">
                <ElInput v-model="macForm.note" placeholder="版本说明" />
              </ElFormItem>
              <ElFormItem>
                <ElButton type="success" @click="saveConfig(macConfig, macForm)">保存配置</ElButton>
              </ElFormItem>
            </ElForm>
          </div>
        </div>
      </ElCard>

      <!-- 批量升级区 -->
      <ElCard class="upgrade-card" shadow="never">
        <template #header>
          <span class="card-title">🚀 批量升级</span>
        </template>
        
        <!-- 筛选条件 -->
        <div class="filter-row">
          <ElForm inline>
            <ElFormItem label="设备类别">
              <ElSelect v-model="filterForm.namespace" placeholder="请选择" style="width: 180px">
                <ElOption v-for="opt in NAMESPACE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
              </ElSelect>
            </ElFormItem>
            <ElFormItem label="设备类型">
              <ElSelect v-model="filterForm.device_type" placeholder="请选择" style="width: 120px">
                <ElOption v-for="opt in DEVICE_TYPE_FILTER_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
              </ElSelect>
            </ElFormItem>
            <ElFormItem>
              <ElButton type="primary" @click="loadPreview">查询预览</ElButton>
              <ElButton @click="filterForm = { namespace: '', device_type: '' }; loadPreview()">重置</ElButton>
            </ElFormItem>
          </ElForm>
        </div>

        <!-- 统计信息 -->
        <div class="stats-row" v-if="previewData">
          <ElTag type="primary">可升级: {{ previewData.upgradable_count }}台</ElTag>
          <ElTag type="warning">使用中(待队列): {{ previewData.waiting_count }}台</ElTag>
          <ElTag type="success">已最新: {{ previewData.latest_count }}台</ElTag>
          <ElTag type="danger">离线: {{ previewData.offline_count }}台</ElTag>
        </div>

        <!-- 机器列表 -->
        <ElTable :data="previewData?.machines || []" v-loading="previewLoading" border class="preview-table">
          <ElTableColumn width="80">
            <template #header>
              <div class="select-header">
                <ElCheckbox 
                  :model-value="selectedMachineIds.length > 0"
                  @change="handleSelectAll"
                />
                <span class="select-label">全选</span>
              </div>
            </template>
            <template #default="{ row }">
              <ElCheckbox 
                v-if="row.upgrade_status === '待升级' || row.upgrade_status === '待队列'"
                :model-value="selectedMachineIds.includes(row.id)"
                @change="(val: boolean) => val ? selectedMachineIds.push(row.id) : selectedMachineIds = selectedMachineIds.filter(id => id !== row.id)"
              />
            </template>
          </ElTableColumn>
          <ElTableColumn prop="ip" label="IP地址" min-width="140">
            <template #default="{ row }">
              <code class="ip-code">{{ row.ip }}</code>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="device_type" label="设备类型" min-width="100">
            <template #default="{ row }">
              {{ row.device_type === 'windows' ? 'Windows' : 'Mac' }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="version" label="当前版本" min-width="120" />
          <ElTableColumn prop="status" label="状态" min-width="80">
            <template #default="{ row }">
              <span :class="`status-${row.status}`">{{ row.status === 'online' ? '在线' : row.status === 'using' ? '使用中' : row.status === 'upgrading' ? '升级中' : '离线' }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="upgrade_status" label="升级状态" min-width="100">
            <template #default="{ row }">
              <ElTag :type="getStatusTagType(row.upgrade_status)" size="small">{{ row.upgrade_status }}</ElTag>
            </template>
          </ElTableColumn>
        </ElTable>

        <!-- 操作按钮 -->
        <div class="action-row">
          <ElButton type="primary" @click="openConfirmDialog">
            批量升级选中的机器 ({{ selectedMachineIds.length }}台)
          </ElButton>
        </div>
      </ElCard>

      <!-- 升级队列区 -->
      <ElCard class="queue-card" shadow="never">
        <template #header>
          <div class="queue-header">
            <span class="card-title">📋 升级队列</span>
            <ElTag type="info">等待: {{ queueData.total }}台</ElTag>
          </div>
        </template>
        
        <ElTable :data="queueData.items" v-loading="queueLoading" border>
          <ElTableColumn prop="ip" label="IP地址" min-width="140">
            <template #default="{ row }">
              <code class="ip-code">{{ row.ip }}</code>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="device_type" label="设备类型" min-width="100">
            <template #default="{ row }">
              {{ row.device_type === 'windows' ? 'Windows' : 'Mac' }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="target_version" label="目标版本" min-width="120" />
          <ElTableColumn prop="created_at" label="入队时间" min-width="160" />
          <ElTableColumn prop="status" label="状态" min-width="80">
            <template #default="{ row }">
              <ElTag size="small">{{ row.status }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" min-width="80">
            <template #default="{ row }">
              <a class="remove-link" @click="handleRemoveQueue(row)">移除队列</a>
            </template>
          </ElTableColumn>
        </ElTable>
      </ElCard>

      <!-- 确认弹窗 -->
      <ElDialog v-model="confirmDialogVisible" title="确认批量升级" width="400px">
        <p>即将升级选中的机器：</p>
        <p class="confirm-info">已选中 {{ selectedMachineIds.length }} 台机器</p>
        <p class="confirm-warning">升级期间机器将不可用，请确认操作。</p>
        <template #footer>
          <ElButton @click="confirmDialogVisible = false">取消</ElButton>
          <ElButton type="primary" :loading="upgradeLoading" @click="executeBatchUpgrade">确认升级</ElButton>
        </template>
      </ElDialog>
    </div>
  </Page>
</template>

<style scoped>
.upgrade-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card-title {
  font-weight: 500;
}

.config-card {
  margin-bottom: 0;
}

.config-row {
  display: flex;
  gap: 24px;
}

.config-item {
  flex: 1;
  background: #fafafa;
  padding: 16px;
  border-radius: 6px;
  border: 1px solid #e8e8e8;
}

.config-tag {
  margin-bottom: 12px;
}

.config-form {
  margin-top: 8px;
}

.filter-row {
  padding: 12px;
  background: #fafafa;
  border-radius: 4px;
  margin-bottom: 12px;
}

.stats-row {
  display: flex;
  gap: 12px;
  padding: 8px 12px;
  background: #e6f7ff;
  border-radius: 4px;
  border: 1px solid #91d5ff;
  margin-bottom: 12px;
}

.preview-table {
  margin-bottom: 12px;
}

.select-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.select-label {
  font-size: 12px;
  color: #1890ff;
}

.ip-code {
  background: #f5f5f5;
  padding: 2px 4px;
  border-radius: 2px;
  font-family: monospace;
}

.status-online {
  color: #52c41a;
}

.status-using {
  color: #e6a23c;
}

.status-upgrading {
  color: #722ed1;
}

.status-offline {
  color: #ff4d4f;
}

.action-row {
  display: flex;
  gap: 12px;
}

.queue-card {
  margin-bottom: 0;
}

.queue-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.remove-link {
  color: #ff4d4f;
  cursor: pointer;
}

.confirm-info {
  font-size: 14px;
  color: #1890ff;
}

.confirm-warning {
  font-size: 13px;
  color: #faad14;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/views/env-machine/upgrade.vue
git commit -m "feat(web): add upgrade management page"
```

---

## Task 9: 创建路由配置

**Files:**
- Create: `web/apps/web-ele/src/router/routes/modules/env-machine-upgrade.ts`
- Modify: 需要在菜单系统中添加入口（如 init_env_machine_menu.py）

- [ ] **Step 1: 创建路由配置文件**

```typescript
import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/env-machine/upgrade',
    name: 'EnvMachineUpgrade',
    component: () => import('#/views/env-machine/upgrade.vue'),
    meta: {
      title: '升级管理',
      icon: 'ant-design:cloud-upload-outlined',
    },
  },
];

export default routes;
```

- [ ] **Step 2: 创建菜单初始化脚本**

创建 `backend-fastapi/scripts/init_upgrade_menu.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
初始化升级管理菜单
"""
import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from core.menu.model import Menu

async def init_upgrade_menu():
    async with AsyncSessionLocal() as db:
        # 查找设备管理父菜单
        result = await db.execute(select(Menu).where(Menu.path == "/env-machine"))
        parent = result.scalar_one_or_none()
        
        if not parent:
            print("未找到设备管理父菜单")
            return
        
        # 创建升级管理子菜单
        menu = Menu(
            parent_id=parent.id,
            name="升级管理",
            path="/env-machine/upgrade",
            component="views/env-machine/upgrade",
            icon="ant-design:cloud-upload-outlined",
            sort=100,
            is_enabled=True,
        )
        db.add(menu)
        await db.commit()
        print("升级管理菜单创建成功")

if __name__ == "__main__":
    asyncio.run(init_upgrade_menu())
```

- [ ] **Step 3: Commit**

```bash
git add web/apps/web-ele/src/router/routes/modules/env-machine-upgrade.ts backend-fastapi/scripts/init_upgrade_menu.py
git commit -m "feat: add upgrade route and menu init script"
```

---

## Task 10: 添加定时任务处理逻辑

**Files:**
- Modify: `backend-fastapi/core/env_machine/scheduler.py` 或定时任务文件

- [ ] **Step 1: 阅读现有定时任务代码**

先阅读 `backend-fastapi/core/env_machine/scheduler.py` 或相关定时任务文件，了解现有定时任务的结构。

- [ ] **Step 2: 添加 upgrading 状态超时处理**

在检测机器超时的定时任务中，添加 upgrading 状态处理：

```python
# upgrading 状态超时也置为 offline
if machine.status == "upgrading":
    timeout_threshold = datetime.now() - timedelta(minutes=30)  # 升级超时时间（可配置）
    if machine.sync_time < timeout_threshold:
        machine.status = "offline"
        logger.warning(f"升级超时，机器置为离线: machine_id={machine.id}, ip={machine.ip}")
```

- [ ] **Step 3: 添加队列清理任务**

在定时任务中添加队列清理逻辑：

```python
from core.env_machine.upgrade_service import WorkerUpgradeQueueService

# 清理 7 天前的 completed 记录
await WorkerUpgradeQueueService.cleanup_completed(db, days=7)

# 标记超时 24 小时的 waiting 为 failed
await WorkerUpgradeQueueService.mark_timeout_waiting(db, hours=24)
```

- [ ] **Step 4: Commit**

```bash
git add backend-fastapi/core/env_machine/scheduler.py
git commit -m "feat(env_machine): add upgrading timeout and queue cleanup tasks"
```

---

## Task 11: 修改设备管理页面新增升级按钮

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/index.vue`
- Modify: `web/apps/web-ele/src/views/env-machine/types.ts`

- [ ] **Step 1: 修改 types.ts 新增 upgrading 状态**

```typescript
export const STATUS_OPTIONS = [
  { label: '在线', value: 'online', type: 'success' },
  { label: '使用中', value: 'using', type: 'warning' },
  { label: '离线', value: 'offline', type: 'info' },
  { label: '升级中', value: 'upgrading', type: 'info' },  // 新增
];
```

- [ ] **Step 2: 在 index.vue 中添加升级版本比对逻辑**

首先需要获取升级配置，在 script 中添加：

```typescript
import { getUpgradeConfigListApi } from '#/api/core/env-machine-upgrade';

// 升级配置（用于版本比对）
const upgradeConfigs = ref<{ windows: string; mac: string }>({ windows: '', mac: '' });

// 加载升级配置
async function loadUpgradeConfigs() {
  try {
    const configs = await getUpgradeConfigListApi();
    for (const config of configs) {
      if (config.device_type === 'windows') {
        upgradeConfigs.value.windows = config.version;
      } else if (config.device_type === 'mac') {
        upgradeConfigs.value.mac = config.version;
      }
    }
  } catch {
    // 配置加载失败时使用默认版本
    upgradeConfigs.value = { windows: '20260410150000', mac: '20260410150000' };
  }
}

// 判断是否需要升级
function needUpgrade(row: EnvMachine): boolean {
  if (!row.version) return true;  // 无版本信息，需要升级
  const targetVersion = upgradeConfigs.value[row.device_type as keyof typeof upgradeConfigs.value];
  return row.version < targetVersion;
}
```

并在 onMounted 中调用：

```typescript
onMounted(() => {
  loadUpgradeConfigs();
  loadData();
});
```

- [ ] **Step 3: 修改 index.vue 操作列**

在标准页面（非手工）模板中，修改操作列：

```vue
<ElTableColumn label="操作" min-width="140">
  <template #default="{ row }">
    <a class="env-link" @click="handleEdit(row)">编辑</a>
    <a class="env-link" @click="handleUpgrade(row)" 
       v-if="row.status === 'online' && needUpgrade(row)">升级</a>
    <a class="env-link env-link-danger" @click="handleDelete(row)">删除</a>
  </template>
</ElTableColumn>
```

添加升级处理逻辑：

```typescript
// 处理单机升级
function handleUpgrade(row: EnvMachine) {
  ElMessageBox.confirm(`确定升级设备 "${row.ip}" 吗？升级期间机器不可用。`, '确认升级', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      await batchUpgradeApi({ machine_ids: [row.id] });
      ElMessage.success('升级指令已下发');
      loadData();
    } catch {
      ElMessage.error('升级失败');
    }
  });
}
```

- [ ] **Step 4: 修改状态样式和显示**

```typescript
// 获取状态样式类
function getStatusClass(status: string) {
  const statusMap: Record<string, string> = {
    online: 'env-status-success',
    using: 'env-status-orange',
    offline: 'env-status-warning',
    upgrading: 'env-status-upgrading',  // 新增
  };
  return statusMap[status] || '';
}
```

```css
.env-status-upgrading {
  color: #722ed1;  /* 紫色 */
}
```

- [ ] **Step 5: Commit**

```bash
git add web/apps/web-ele/src/views/env-machine/index.vue web/apps/web-ele/src/views/env-machine/types.ts
git commit -m "feat(web): add upgrade button and upgrading status to env-machine page"
```

---

## Task 12: 验收测试

- [ ] **Step 1: 启动后端服务**

```bash
cd backend-fastapi && python main.py
```

- [ ] **Step 2: 验证 API 接口**

访问 Swagger UI: http://localhost:8000/docs
检查以下接口：
- GET /api/core/env/upgrade/config
- PUT /api/core/env/upgrade/config/{id}
- GET /api/core/env/upgrade/worker/info
- POST /api/core/env/upgrade/worker/start
- POST /api/core/env/upgrade/batch
- GET /api/core/env/upgrade/preview
- GET /api/core/env/upgrade/queue
- DELETE /api/core/env/upgrade/queue/{id}

- [ ] **Step 3: 启动前端服务**

```bash
cd web && pnpm dev
```

- [ ] **Step 4: 验证前端页面**

访问升级管理页面，检查：
- 版本配置区显示和保存功能
- 批量升级筛选和预览功能
- 升级队列显示
- 设备管理页面升级按钮显示

- [ ] **Step 5: Commit 最终验收**

```bash
git add -A
git commit -m "feat: complete worker upgrade management feature"
```

---

## 执行说明

本计划包含 12 个 Task，每个 Task 包含多个步骤。建议按顺序执行：

1. **Task 1-3**: 数据库相关（模型、迁移）
2. **Task 4-5**: 后端服务层和 API
3. **Task 6**: 核心逻辑改动（pool_manager）
4. **Task 7-9**: 前端开发（API、页面、路由）
5. **Task 10**: 定时任务处理（超时、队列清理）
6. **Task 11**: 设备管理页面升级按钮
7. **Task 12**: 验收测试

每个 Task 结束后都有 Commit，便于追踪进度和回滚。