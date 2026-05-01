# 性能监控模块实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现完整的 Worker 性能监控模块，包括后端数据模型/API、前端主页面（曲线图+次要指标+TOP10）、版本对比页面。

**Architecture:** 后端采用 FastAPI + SQLAlchemy 异步 ORM，前端采用 Vue 3 + Element Plus + ECharts 图表。数据通过 HTTP API 同步，Worker 定时上报性能数据，前端轮询获取实时数据。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vue 3, Element Plus, ECharts, TypeScript

---

## 文件结构

### 后端文件

| 文件 | 负责内容 |
|------|----------|
| `backend-fastapi/core/performance_monitor/__init__.py` | 模块初始化 |
| `backend-fastapi/core/performance_monitor/model.py` | 数据模型（PerformanceCollect, PerformanceData, PerformanceTag, PerformanceVersion） |
| `backend-fastapi/core/performance_monitor/schema.py` | Pydantic Schema（请求/响应定义） |
| `backend-fastapi/core/performance_monitor/service.py` | 业务逻辑（采集管理、数据查询、标签管理、版本对比） |
| `backend-fastapi/core/performance_monitor/api.py` | API 路由（采集、标签、版本对比） |
| `backend-fastapi/core/router.py` | 注册 performance_monitor 路由 |

### 前端文件

| 文件 | 负责内容 |
|------|----------|
| `web/apps/web-ele/src/api/core/performance-monitor.ts` | API 接口定义（TypeScript interface + fetch 函数） |
| `web/apps/web-ele/src/views/performance-monitor/index.vue` | 主页面（曲线图+次要指标+TOP10+时间轴+采集控制） |
| `web/apps/web-ele/src/views/performance-monitor/compare.vue` | 版本对比页面（多版本曲线+标签系统+数据摘要表） |
| `web/apps/web-ele/src/views/performance-monitor/components/ChartPanel.vue` | 曲线图组件（ECharts封装） |
| `web/apps/web-ele/src/views/performance-monitor/components/MetricCard.vue` | 次要指标卡片组件 |
| `web/apps/web-ele/src/views/performance-monitor/components/Top10List.vue` | TOP10 概览组件 |
| `web/apps/web-ele/src/views/performance-monitor/components/CollectDialog.vue` | 开始采集弹窗组件 |
| `web/apps/web-ele/src/views/performance-monitor/components/TagDialog.vue` | 标签配置弹窗组件 |
| `web/apps/web-ele/src/views/performance-monitor/types.ts` | TypeScript 类型定义 |
| `web/apps/web-ele/src/router/routes/modules/performance-monitor.ts` | 主页面路由 |
| `web/apps/web-ele/src/router/routes/modules/performance-monitor-compare.ts` | 对比页面路由 |

---

## Task 1: 后端数据模型

**Files:**
- Create: `backend-fastapi/core/performance_monitor/__init__.py`
- Create: `backend-fastapi/core/performance_monitor/model.py`

- [ ] **Step 1: 创建模块目录和初始化文件**

```bash
mkdir -p backend-fastapi/core/performance_monitor
```

创建 `__init__.py`:
```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控模块
"""
```

- [ ] **Step 2: 编写数据模型**

创建 `model.py`:
```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控数据模型
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, JSON, ForeignKey

from app.base_model import BaseModel


class PerformanceCollect(BaseModel):
    """采集记录表"""
    __tablename__ = "performance_collect"

    device_id = Column(String(21), nullable=False, comment="设备ID")
    name = Column(String(100), nullable=True, comment="采集名称")
    start_time = Column(DateTime, nullable=False, comment="开始时间")
    end_time = Column(DateTime, nullable=True, comment="结束时间")
    interval = Column(Integer, nullable=False, default=5, comment="采集频率（秒）")
    target_processes = Column(JSON, nullable=True, comment="目标进程配置")
    status = Column(String(20), nullable=False, default="running", comment="状态：running/stopped/error")
    is_protected = Column(Boolean, nullable=False, default=False, comment="保护标记")


class PerformanceData(BaseModel):
    """性能数据表"""
    __tablename__ = "performance_data"

    collect_id = Column(String(21), ForeignKey("performance_collect.id"), nullable=False, comment="采集记录ID")
    timestamp = Column(DateTime, nullable=False, comment="实际时间")
    relative_time = Column(Integer, nullable=False, comment="相对时间（秒）")

    # 系统指标
    cpu_usage = Column(Float, nullable=True, comment="CPU使用率 %")
    gpu_usage = Column(Float, nullable=True, comment="GPU使用率 %")
    commit_memory = Column(Float, nullable=True, comment="提交内存 GB")
    memory_usage = Column(Float, nullable=True, comment="内存使用 GB")
    power = Column(Float, nullable=True, comment="功耗 W")
    cpu_speed = Column(Float, nullable=True, comment="CPU速度 GHz")
    cpu_temp = Column(Float, nullable=True, comment="CPU温度 °C")
    process_handles = Column(Integer, nullable=True, comment="进程句柄数")
    upload_speed = Column(Float, nullable=True, comment="上传速度 MB/s")
    download_speed = Column(Float, nullable=True, comment="下载速度 MB/s")

    # 进程数据
    target_processes = Column(JSON, nullable=True, comment="目标进程数据")
    top10_cpu = Column(JSON, nullable=True, comment="CPU TOP10")
    top10_gpu = Column(JSON, nullable=True, comment="GPU TOP10")


class PerformanceTag(BaseModel):
    """标签表"""
    __tablename__ = "performance_tag"

    collect_id = Column(String(21), ForeignKey("performance_collect.id"), nullable=False, comment="采集记录ID")
    name = Column(String(50), nullable=False, comment="标签名称")
    start_relative_time = Column(Integer, nullable=False, comment="起始相对时间（秒）")
    duration = Column(Integer, nullable=False, comment="时间长度（秒）")
    type = Column(String(20), nullable=False, default="peak", comment="类型：peak/mean")


class PerformanceVersion(BaseModel):
    """版本对比表"""
    __tablename__ = "performance_version"

    device_id = Column(String(21), nullable=False, comment="设备ID")
    name = Column(String(100), nullable=False, comment="版本名称")
    collect_ids = Column(JSON, nullable=False, comment="包含的采集记录ID列表")
    is_protected = Column(Boolean, nullable=False, default=False, comment="保护标记")
```

- [ ] **Step 3: 执行数据库迁移**

```bash
cd backend-fastapi
alembic revision --autogenerate -m "add performance_monitor tables"
alembic upgrade head
```

- [ ] **Step 4: 提交**

```bash
git add backend-fastapi/core/performance_monitor/
git commit -m "feat(performance-monitor): 添加数据模型 PerformanceCollect/Data/Tag/Version"
```

---

## Task 2: 后端 Schema 定义

**Files:**
- Create: `backend-fastapi/core/performance_monitor/schema.py`

- [ ] **Step 1: 编写请求 Schema**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控 Schema 定义
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ===== 采集管理 =====

class CollectStartRequest(BaseModel):
    """开始采集请求"""
    device_id: str = Field(..., description="设备ID")
    interval: int = Field(default=5, ge=1, le=60, description="采集频率（秒）")
    target_processes: List[Dict[str, Any]] = Field(default=[], description="目标进程列表")


class CollectStopRequest(BaseModel):
    """停止采集请求"""
    collect_id: Optional[str] = Field(None, description="采集记录ID，不传则停止所有")
    device_id: str = Field(..., description="设备ID")


class CollectListRequest(BaseModel):
    """采集列表查询请求"""
    device_id: Optional[str] = Field(None, description="设备ID")
    status: Optional[str] = Field(None, description="状态筛选")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class CollectDataRequest(BaseModel):
    """采集数据查询请求"""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=100, ge=1, le=500)


# ===== 数据上报 =====

class ProcessInstance(BaseModel):
    """进程实例"""
    pid: int
    cpu: float
    memory: float
    gpu: float


class TargetProcess(BaseModel):
    """目标进程数据"""
    name: str
    total_cpu: float
    total_memory: float
    total_gpu: float
    instances: List[ProcessInstance]


class SystemMetrics(BaseModel):
    """系统指标"""
    cpu_usage: float
    gpu_usage: float
    commit_memory: float
    memory_usage: float
    power: float
    cpu_speed: float
    cpu_temp: float
    process_handles: int
    upload_speed: float
    download_speed: float


class Top10Process(BaseModel):
    """TOP10进程"""
    name: str
    cpu: Optional[float] = None
    memory: Optional[float] = None
    gpu: Optional[float] = None


class PerformanceReportRequest(BaseModel):
    """Worker 上报数据请求"""
    collect_id: str
    device_id: str
    timestamp: datetime
    relative_time: int
    system: SystemMetrics
    target_processes: List[TargetProcess] = []
    top10_cpu: List[Top10Process] = []
    top10_gpu: List[Top10Process] = []


# ===== 标签管理 =====

class TagCreateRequest(BaseModel):
    """创建标签请求"""
    collect_id: str
    name: str = Field(..., max_length=50)
    start_relative_time: int = Field(..., ge=0)
    duration: int = Field(..., ge=1)
    type: str = Field(default="peak", pattern="^(peak|mean)$")


class TagUpdateRequest(BaseModel):
    """更新标签请求"""
    tag_id: str
    name: Optional[str] = Field(None, max_length=50)
    start_relative_time: Optional[int] = Field(None, ge=0)
    duration: Optional[int] = Field(None, ge=1)
    type: Optional[str] = Field(None, pattern="^(peak|mean)$")


# ===== 版本对比 =====

class VersionCreateRequest(BaseModel):
    """创建版本请求"""
    name: str = Field(..., max_length=100)
    collect_ids: List[str] = Field(..., min_length=1, max_length=6)


class VersionCompareRequest(BaseModel):
    """版本对比请求"""
    version_ids: List[str] = Field(..., min_length=1, max_length=6)


# ===== 响应 Schema =====

class CollectResponse(BaseModel):
    """采集记录响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    device_id: str
    name: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    interval: int
    target_processes: Optional[Dict[str, Any]]
    status: str
    is_protected: bool


class DataResponse(BaseModel):
    """性能数据响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    timestamp: datetime
    relative_time: int
    cpu_usage: Optional[float]
    gpu_usage: Optional[float]
    commit_memory: Optional[float]
    memory_usage: Optional[float]
    power: Optional[float]
    cpu_speed: Optional[float]
    cpu_temp: Optional[float]
    process_handles: Optional[int]
    upload_speed: Optional[float]
    download_speed: Optional[float]
    target_processes: Optional[Dict[str, Any]]
    top10_cpu: Optional[Dict[str, Any]]
    top10_gpu: Optional[Dict[str, Any]]


class TagResponse(BaseModel):
    """标签响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    collect_id: str
    name: str
    start_relative_time: int
    duration: int
    type: str


class VersionResponse(BaseModel):
    """版本响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    device_id: str
    name: str
    collect_ids: List[str]
    is_protected: bool


class PaginatedResponse(BaseModel):
    """分页响应"""
    total: int
    items: List[Any]
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/performance_monitor/schema.py
git commit -m "feat(performance-monitor): 添加 Schema 定义"
```

---

## Task 3: 后端 Service 层

**Files:**
- Create: `backend-fastapi/core/performance_monitor/service.py`

- [ ] **Step 1: 编写 Service 类**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控业务逻辑
"""
from datetime import datetime
from typing import List, Optional, Dict, Any, Type

from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_service import BaseService
from app.base_model import generate_nanoid
from core.performance_monitor.model import PerformanceCollect, PerformanceData, PerformanceTag, PerformanceVersion
from core.performance_monitor.schema import (
    CollectStartRequest, CollectStopRequest, PerformanceReportRequest,
    TagCreateRequest, TagUpdateRequest, VersionCreateRequest
)
from app.utils.nanoid import generate_nanoid


class PerformanceCollectService(BaseService[PerformanceCollect]):
    """采集记录服务"""
    model = PerformanceCollect

    @classmethod
    async def start_collect(cls, db: AsyncSession, request: CollectStartRequest) -> str:
        """开始采集"""
        collect = PerformanceCollect(
            device_id=request.device_id,
            start_time=datetime.utcnow(),
            interval=request.interval,
            target_processes=request.target_processes,
            status="running"
        )
        db.add(collect)
        await db.commit()
        await db.refresh(collect)
        return collect.id

    @classmethod
    async def stop_collect(cls, db: AsyncSession, collect_id: Optional[str], device_id: str) -> bool:
        """停止采集"""
        if collect_id:
            collect = await db.get(PerformanceCollect, collect_id)
            if collect:
                collect.status = "stopped"
                collect.end_time = datetime.utcnow()
                await db.commit()
                return True
        else:
            # 停止该设备所有正在运行的采集
            stmt = select(PerformanceCollect).where(
                and_(PerformanceCollect.device_id == device_id, PerformanceCollect.status == "running")
            )
            result = await db.execute(stmt)
            collects = result.scalars().all()
            for c in collects:
                c.status = "stopped"
                c.end_time = datetime.utcnow()
            await db.commit()
            return len(collects) > 0
        return False

    @classmethod
    async def get_collect_status(cls, db: AsyncSession, device_id: str) -> Optional[Dict[str, Any]]:
        """获取采集状态"""
        stmt = select(PerformanceCollect).where(
            and_(PerformanceCollect.device_id == device_id, PerformanceCollect.status == "running")
        ).order_by(desc(PerformanceCollect.start_time)).limit(1)
        result = await db.execute(stmt)
        collect = result.scalar_one_or_none()
        if collect:
            return {
                "is_collecting": True,
                "collect_id": collect.id,
                "interval": collect.interval,
                "target_processes": collect.target_processes,
                "start_time": collect.start_time,
                "elapsed_seconds": int((datetime.utcnow() - collect.start_time).total_seconds())
            }
        return {"is_collecting": False}

    @classmethod
    async def get_collect_list(cls, db: AsyncSession, device_id: Optional[str], page: int, page_size: int) -> Dict[str, Any]:
        """获取采集列表"""
        conditions = [PerformanceCollect.is_deleted == False]
        if device_id:
            conditions.append(PerformanceCollect.device_id == device_id)
        
        stmt = select(PerformanceCollect).where(and_(*conditions)).order_by(desc(PerformanceCollect.start_time))
        # 计算总数
        count_stmt = select(func.count()).select_from(PerformanceCollect).where(and_(*conditions))
        count_result = await db.execute(count_stmt)
        total = count_result.scalar()
        
        # 分页查询
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(stmt)
        items = result.scalars().all()
        
        return {"total": total, "items": items}


class PerformanceDataService(BaseService[PerformanceData]):
    """性能数据服务"""
    model = PerformanceData

    @classmethod
    async def report_data(cls, db: AsyncSession, request: PerformanceReportRequest) -> bool:
        """接收 Worker 上报数据"""
        data = PerformanceData(
            collect_id=request.collect_id,
            timestamp=request.timestamp,
            relative_time=request.relative_time,
            cpu_usage=request.system.cpu_usage,
            gpu_usage=request.system.gpu_usage,
            commit_memory=request.system.commit_memory,
            memory_usage=request.system.memory_usage,
            power=request.system.power,
            cpu_speed=request.system.cpu_speed,
            cpu_temp=request.system.cpu_temp,
            process_handles=request.system.process_handles,
            upload_speed=request.system.upload_speed,
            download_speed=request.system.download_speed,
            target_processes=[p.model_dump() for p in request.target_processes],
            top10_cpu=[p.model_dump() for p in request.top10_cpu],
            top10_gpu=[p.model_dump() for p in request.top10_gpu]
        )
        db.add(data)
        await db.commit()
        return True

    @classmethod
    async def get_collect_data(cls, db: AsyncSession, collect_id: str, page: int, page_size: int) -> Dict[str, Any]:
        """获取采集数据"""
        stmt = select(PerformanceData).where(
            PerformanceData.collect_id == collect_id
        ).order_by(PerformanceData.relative_time)
        
        # 计算总数
        count_stmt = select(func.count()).select_from(PerformanceData).where(PerformanceData.collect_id == collect_id)
        count_result = await db.execute(count_stmt)
        total = count_result.scalar()
        
        # 分页查询
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(stmt)
        items = result.scalars().all()
        
        return {"total": total, "items": items}

    @classmethod
    async def get_latest_data(cls, db: AsyncSession, collect_id: str, limit: int = 10) -> List[PerformanceData]:
        """获取最新数据"""
        stmt = select(PerformanceData).where(
            PerformanceData.collect_id == collect_id
        ).order_by(desc(PerformanceData.relative_time)).limit(limit)
        result = await db.execute(stmt)
        items = result.scalars().all()
        return list(reversed(items))


class PerformanceTagService(BaseService[PerformanceTag]):
    """标签服务"""
    model = PerformanceTag

    @classmethod
    async def create_tag(cls, db: AsyncSession, request: TagCreateRequest) -> str:
        """创建标签"""
        tag = PerformanceTag(
            collect_id=request.collect_id,
            name=request.name,
            start_relative_time=request.start_relative_time,
            duration=request.duration,
            type=request.type
        )
        db.add(tag)
        await db.commit()
        await db.refresh(tag)
        return tag.id

    @classmethod
    async def get_tags(cls, db: AsyncSession, collect_id: str) -> List[PerformanceTag]:
        """获取标签列表"""
        stmt = select(PerformanceTag).where(PerformanceTag.collect_id == collect_id)
        result = await db.execute(stmt)
        return result.scalars().all()

    @classmethod
    async def update_tag(cls, db: AsyncSession, tag_id: str, **kwargs) -> bool:
        """更新标签"""
        tag = await db.get(PerformanceTag, tag_id)
        if tag:
            for key, value in kwargs.items():
                if value is not None and hasattr(tag, key):
                    setattr(tag, key, value)
            await db.commit()
            return True
        return False

    @classmethod
    async def delete_tag(cls, db: AsyncSession, tag_id: str) -> bool:
        """删除标签"""
        tag = await db.get(PerformanceTag, tag_id)
        if tag:
            await db.delete(tag)
            await db.commit()
            return True
        return False


class PerformanceVersionService(BaseService[PerformanceVersion]):
    """版本对比服务"""
    model = PerformanceVersion

    @classmethod
    async def create_version(cls, db: AsyncSession, request: VersionCreateRequest) -> str:
        """创建版本"""
        # 从第一个 collect_id 获取 device_id
        first_collect = await db.get(PerformanceCollect, request.collect_ids[0])
        if not first_collect:
            raise ValueError("采集记录不存在")
        
        version = PerformanceVersion(
            device_id=first_collect.device_id,
            name=request.name,
            collect_ids=request.collect_ids,  # 直接使用字符串列表
            is_protected=False
        )
        db.add(version)
        await db.commit()
        await db.refresh(version)
        return version.id

    @classmethod
    async def get_versions(cls, db: AsyncSession, device_id: str) -> List[PerformanceVersion]:
        """获取版本列表"""
        stmt = select(PerformanceVersion).where(PerformanceVersion.device_id == device_id)
        result = await db.execute(stmt)
        return result.scalars().all()

    @classmethod
    async def get_compare_data(cls, db: AsyncSession, version_ids: List[str]) -> Dict[str, Any]:
        """获取对比数据"""
        versions_data = []
        for vid in version_ids:
            version = await db.get(PerformanceVersion, vid)
            if version:
                collect_ids = version.collect_ids  # 已经是字符串列表
                collects = []
                for cid in collect_ids:
                    collect = await db.get(PerformanceCollect, cid)
                    if collect:
                        # 获取该采集的所有数据
                        stmt = select(PerformanceData).where(PerformanceData.collect_id == cid).order_by(PerformanceData.relative_time)
                        result = await db.execute(stmt)
                        data = result.scalars().all()
                        # 获取标签
                        tags = await PerformanceTagService.get_tags(db, cid)
                        collects.append({
                            "collect": collect,
                            "data": data,
                            "tags": tags
                        })
                versions_data.append({
                    "version": version,
                    "collects": collects
                })
        
        return {"versions": versions_data}
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/performance_monitor/service.py
git commit -m "feat(performance-monitor): 添加 Service 业务逻辑层"
```

---

## Task 4: 后端 API 路由

**Files:**
- Create: `backend-fastapi/core/performance_monitor/api.py`
- Modify: `backend-fastapi/core/router.py` (添加路由注册)

- [ ] **Step 1: 编写 API 路由**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控 API 路由
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from core.performance_monitor.model import PerformanceCollect
from core.performance_monitor.schema import (
    CollectStartRequest, CollectStopRequest,
    PerformanceReportRequest, TagCreateRequest, TagUpdateRequest,
    VersionCreateRequest
)
from core.performance_monitor.service import (
    PerformanceCollectService, PerformanceDataService,
    PerformanceTagService, PerformanceVersionService
)

router = APIRouter(prefix="/performance-monitor", tags=["性能监控"])


# ===== 采集管理 =====

@router.post("/collect/start")
async def start_collect(request: CollectStartRequest, db: AsyncSession = Depends(get_db)):
    """开始采集"""
    collect_id = await PerformanceCollectService.start_collect(db, request)
    return {"collect_id": collect_id, "status": "started"}


@router.post("/collect/stop")
async def stop_collect(request: CollectStopRequest, db: AsyncSession = Depends(get_db)):
    """停止采集"""
    success = await PerformanceCollectService.stop_collect(db, request.collect_id, request.device_id)
    return {"status": "stopped" if success else "not_found"}


@router.get("/collect/status")
async def get_collect_status(device_id: str, db: AsyncSession = Depends(get_db)):
    """获取采集状态"""
    status = await PerformanceCollectService.get_collect_status(db, device_id)
    return status


@router.get("/collect/list")
async def get_collect_list(
    device_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """获取采集列表"""
    result = await PerformanceCollectService.get_collect_list(db, device_id, page, page_size)
    return result


@router.get("/collect/{collect_id}")
async def get_collect_detail(collect_id: str, db: AsyncSession = Depends(get_db)):
    """获取采集详情"""
    collect = await db.get(PerformanceCollect, collect_id)
    return collect


@router.get("/collect/{collect_id}/data")
async def get_collect_data(
    collect_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    """获取采集数据"""
    result = await PerformanceDataService.get_collect_data(db, collect_id, page, page_size)
    return result


@router.get("/collect/{collect_id}/latest")
async def get_latest_data(collect_id: str, limit: int = Query(10, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    """获取最新数据"""
    items = await PerformanceDataService.get_latest_data(db, collect_id, limit)
    return {"items": items}


# ===== 数据上报 =====

@router.post("/report")
async def report_data(request: PerformanceReportRequest, db: AsyncSession = Depends(get_db)):
    """Worker 上报数据"""
    success = await PerformanceDataService.report_data(db, request)
    return {"status": "success" if success else "failed"}


# ===== 标签管理 =====

@router.post("/tag/create")
async def create_tag(request: TagCreateRequest, db: AsyncSession = Depends(get_db)):
    """创建标签"""
    tag_id = await PerformanceTagService.create_tag(db, request)
    return {"tag_id": tag_id, "status": "created"}


@router.get("/tag/list")
async def get_tags(collect_id: str, db: AsyncSession = Depends(get_db)):
    """获取标签列表"""
    tags = await PerformanceTagService.get_tags(db, collect_id)
    return {"items": tags}


@router.put("/tag/update")
async def update_tag(request: TagUpdateRequest, db: AsyncSession = Depends(get_db)):
    """更新标签"""
    success = await PerformanceTagService.update_tag(db, request.tag_id, name=request.name, 
                                       start_relative_time=request.start_relative_time,
                                       duration=request.duration, type=request.type)
    return {"status": "updated" if success else "not_found"}


@router.delete("/tag/delete")
async def delete_tag(tag_id: str, db: AsyncSession = Depends(get_db)):
    """删除标签"""
    success = await PerformanceTagService.delete_tag(db, tag_id)
    return {"status": "deleted" if success else "not_found"}


# ===== 版本对比 =====

@router.post("/version/create")
async def create_version(request: VersionCreateRequest, db: AsyncSession = Depends(get_db)):
    """创建版本"""
    version_id = await PerformanceVersionService.create_version(db, request)
    return {"version_id": version_id, "status": "created"}


@router.get("/version/list")
async def get_versions(device_id: str, db: AsyncSession = Depends(get_db)):
    """获取版本列表"""
    versions = await PerformanceVersionService.get_versions(db, device_id)
    return {"items": versions}


@router.get("/version/compare")
async def get_compare_data(version_ids: str, db: AsyncSession = Depends(get_db)):
    """获取版本对比数据"""
    ids = version_ids.split(",")
    result = await PerformanceVersionService.get_compare_data(db, ids)
    return result
```

- [ ] **Step 2: 注册路由**

修改 `backend-fastapi/core/router.py`，添加：
```python
from core.performance_monitor.api import router as performance_monitor_router

# 在 router.include_router 列表中添加
router.include_router(performance_monitor_router)
```

- [ ] **Step 3: 提交**

```bash
git add backend-fastapi/core/performance_monitor/api.py backend-fastapi/core/router.py
git commit -m "feat(performance-monitor): 添加 API 路由并注册"
```

---

## Task 5: 前端 API 定义

**Files:**
- Create: `web/apps/web-ele/src/api/core/performance-monitor.ts`

- [ ] **Step 1: 编写 TypeScript 类型定义和 API 函数**

```typescript
import { requestClient } from '#/api/request';

// ===== 类型定义 =====

export interface PerformanceCollect {
  id: string;
  device_id: string;
  name?: string;
  start_time: string;
  end_time?: string;
  interval: number;
  target_processes?: TargetProcessConfig[];
  status: string;
  is_protected: boolean;
}

export interface TargetProcessConfig {
  name: string;
  pids?: number[];
}

export interface PerformanceData {
  id: string;
  timestamp: string;
  relative_time: number;
  cpu_usage?: number;
  gpu_usage?: number;
  commit_memory?: number;
  memory_usage?: number;
  power?: number;
  cpu_speed?: number;
  cpu_temp?: number;
  process_handles?: number;
  upload_speed?: number;
  download_speed?: number;
  target_processes?: ProcessData[];
  top10_cpu?: Top10Process[];
  top10_gpu?: Top10Process[];
}

export interface ProcessData {
  name: string;
  total_cpu: number;
  total_memory: number;
  total_gpu: number;
  instances: ProcessInstance[];
}

export interface ProcessInstance {
  pid: number;
  cpu: number;
  memory: number;
  gpu: number;
}

export interface Top10Process {
  name: string;
  cpu?: number;
  memory?: number;
  gpu?: number;
}

export interface PerformanceTag {
  id: string;
  collect_id: string;
  name: string;
  start_relative_time: number;
  duration: number;
  type: 'peak' | 'mean';
}

export interface PerformanceVersion {
  id: string;
  device_id: string;
  name: string;
  collect_ids: string[];
  is_protected: boolean;
}

export interface CollectStatus {
  is_collecting: boolean;
  collect_id?: string;
  interval?: number;
  target_processes?: TargetProcessConfig[];
  start_time?: string;
  elapsed_seconds?: number;
}

// ===== API 函数 =====

// 采集管理
export async function startCollect(params: {
  device_id: string;
  interval: number;
  target_processes: TargetProcessConfig[];
}) {
  return requestClient.post<{ collect_id: string; status: string }>('/api/core/performance-monitor/collect/start', params);
}

export async function stopCollect(params: { collect_id?: string; device_id: string }) {
  return requestClient.post<{ status: string }>('/api/core/performance-monitor/collect/stop', params);
}

export async function getCollectStatus(deviceId: string) {
  return requestClient.get<CollectStatus>(`/api/core/performance-monitor/collect/status?device_id=${deviceId}`);
}

export async function getCollectList(params: {
  device_id?: string;
  page: number;
  page_size: number;
}) {
  return requestClient.get<{ total: number; items: PerformanceCollect[] }>('/api/core/performance-monitor/collect/list', { params });
}

export async function getCollectData(collectId: string, params: { page: number; page_size: number }) {
  return requestClient.get<{ total: number; items: PerformanceData[] }>(`/api/core/performance-monitor/collect/${collectId}/data`, { params });
}

export async function getLatestData(collectId: string, limit: number = 10) {
  return requestClient.get<{ items: PerformanceData[] }>(`/api/core/performance-monitor/collect/${collectId}/latest?limit=${limit}`);
}

// 标签管理
export async function createTag(params: {
  collect_id: string;
  name: string;
  start_relative_time: number;
  duration: number;
  type: 'peak' | 'mean';
}) {
  return requestClient.post<{ tag_id: string; status: string }>('/api/core/performance-monitor/tag/create', params);
}

export async function getTags(collectId: string) {
  return requestClient.get<{ items: PerformanceTag[] }>(`/api/core/performance-monitor/tag/list?collect_id=${collectId}`);
}

export async function updateTag(params: {
  tag_id: string;
  name?: string;
  start_relative_time?: number;
  duration?: number;
  type?: 'peak' | 'mean';
}) {
  return requestClient.put<{ status: string }>('/api/core/performance-monitor/tag/update', params);
}

export async function deleteTag(tagId: string) {
  return requestClient.delete<{ status: string }>(`/api/core/performance-monitor/tag/delete?tag_id=${tagId}`);
}

// 版本对比
export async function createVersion(params: { name: string; collect_ids: string[] }) {
  return requestClient.post<{ version_id: string; status: string }>('/api/core/performance-monitor/version/create', params);
}

export async function getVersions(deviceId: string) {
  return requestClient.get<{ items: PerformanceVersion[] }>(`/api/core/performance-monitor/version/list?device_id=${deviceId}`);
}

export async function getCompareData(versionIds: string[]) {
  return requestClient.get(`/api/core/performance-monitor/version/compare?version_ids=${versionIds.join(',')}`);
}
```

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/api/core/performance-monitor.ts
git commit -m "feat(performance-monitor): 添加前端 API 定义"
```

---

## Task 6: 前端类型定义和路由

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/types.ts`
- Create: `web/apps/web-ele/src/router/routes/modules/performance-monitor.ts`
- Create: `web/apps/web-ele/src/router/routes/modules/performance-monitor-compare.ts`

- [ ] **Step 1: 创建类型定义**

```typescript
// 曲线图数据点
export interface ChartDataPoint {
  time: number;  // relative_time
  value: number;
}

// 图表系列
export interface ChartSeries {
  name: string;
  data: ChartDataPoint[];
  color: string;
}

// 次要指标卡片数据
export interface MetricCardData {
  name: string;
  value: number;
  unit: string;
  color?: string;
  historyData: number[];  // 迷你趋势线数据
}

// TOP10 数据
export interface Top10Item {
  name: string;
  value: number;
  trendData: number[];  // 迷你趋势线
  color: string;
}

// 版本颜色映射
export const VERSION_COLORS = [
  '#67c23a', // 绿
  '#f56c6c', // 红
  '#e6a23c', // 橙
  '#409eff', // 蓝
  '#909399', // 灰
  '#9c27b0', // 紫
];

// 采集状态枚举
export enum CollectStatusEnum {
  IDLE = 'idle',
  RUNNING = 'running',
  STOPPING = 'stopping',
}

// 标签类型
export type TagType = 'peak' | 'mean';

// 区间合并结果
export interface MergedInterval {
  start: number;
  end: number;
  type: TagType;
}

// 数据摘要
export interface SummaryRow {
  version_name: string;
  color: string;
  peak_cpu?: number;
  peak_process_cpu?: number;
  peak_gpu?: number;
  peak_commit_memory?: number;
  peak_memory_usage?: number;
  mean_cpu?: number;
  mean_process_cpu?: number;
  mean_gpu?: number;
  mean_commit_memory?: number;
  mean_memory_usage?: number;
}
```

- [ ] **Step 2: 创建路由配置**

主页面路由 `performance-monitor.ts`:
```typescript
import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/performance-monitor',
    name: 'PerformanceMonitor',
    component: () => import('#/views/performance-monitor/index.vue'),
    meta: {
      title: '性能监控',
      hideInMenu: true,
    },
  },
];

export default routes;
```

对比页面路由 `performance-monitor-compare.ts`:
```typescript
import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/performance-monitor/compare',
    name: 'PerformanceMonitorCompare',
    component: () => import('#/views/performance-monitor/compare.vue'),
    meta: {
      title: '版本对比',
      hideInMenu: true,
    },
  },
];

export default routes;
```

- [ ] **Step 3: 提交**

```bash
git add web/apps/web-ele/src/views/performance-monitor/types.ts web/apps/web-ele/src/router/routes/modules/performance-monitor*.ts
git commit -m "feat(performance-monitor): 添加类型定义和路由配置"
```

---

## Task 7: 前端组件 - 曲线图面板

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/ChartPanel.vue`

- [ ] **Step 1: 创建曲线图组件**

```vue
<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue';
import * as echarts from 'echarts';
import type { ChartSeries } from '../types';

const props = defineProps<{
  title: string;
  series: ChartSeries[];
  showTop10?: boolean;
  height?: number;
  timeRange?: [number, number];
  tags?: Array<{ name: string; start: number; duration: number; type: string; color: string }>;
}>();

const chartRef = ref<HTMLDivElement>();
let chartInstance: echarts.ECharts | null = null;

const chartHeight = computed(() => props.height || 200);

function initChart() {
  if (!chartRef.value) return;
  chartInstance = echarts.init(chartRef.value);
  updateChart();
}

function updateChart() {
  if (!chartInstance) return;

  const xAxisData = props.series[0]?.data.map(d => d.time) || [];
  
  const seriesConfig = props.series.map(s => ({
    name: s.name,
    type: 'line',
    data: s.data.map(d => d.value),
    lineStyle: { color: s.color, width: 2 },
    itemStyle: { color: s.color },
    smooth: true,
    symbol: 'none',
  }));

  // 标签区间标记
  const markAreas: any[] = [];
  if (props.tags) {
    props.tags.forEach(tag => {
      markAreas.push([
        { xAxis: tag.start, itemStyle: { color: tag.type === 'peak' ? 'rgba(103,194,126,0.15)' : 'rgba(245,108,108,0.15)' } },
        { xAxis: tag.start + tag.duration }
      ]);
    });
  }

  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const time = params[0].axisValue;
        let html = `<div>相对时间: ${time}秒</div>`;
        params.forEach((p: any) => {
          html += `<div>${p.seriesName}: ${p.value?.toFixed(1)}%</div>`;
        });
        return html;
      }
    },
    legend: {
      show: props.series.length > 1,
      top: 0,
      right: 10,
      data: props.series.map(s => s.name),
    },
    grid: {
      left: 50,
      right: 20,
      top: 30,
      bottom: 30,
    },
    xAxis: {
      type: 'category',
      data: xAxisData,
      axisLabel: { formatter: (v: number) => `${v}s` },
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: '{value}%' },
    },
    series: seriesConfig,
  };

  chartInstance.setOption(option);
}

watch(() => props.series, updateChart, { deep: true });
watch(() => props.timeRange, updateChart);

onMounted(() => {
  initChart();
});
</script>

<template>
  <div class="chart-panel">
    <div class="chart-title">{{ title }}</div>
    <div ref="chartRef" class="chart-container" :style="{ height: chartHeight + 'px' }"></div>
  </div>
</template>

<style scoped>
.chart-panel {
  background: #fff;
  border-radius: 8px;
  padding: 12px;
}
.chart-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}
.chart-container {
  width: 100%;
}
</style>
```

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/ChartPanel.vue
git commit -m "feat(performance-monitor): 添加曲线图组件 ChartPanel"
```

---

## Task 8: 前端组件 - 次要指标卡片

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/MetricCard.vue`

- [ ] **Step 1: 创建次要指标卡片组件**

```vue
<script setup lang="ts">
import { computed } from 'vue';
import type { MetricCardData } from '../types';
import * as echarts from 'echarts';
import { ref, onMounted } from 'vue';

const props = defineProps<{
  data: MetricCardData;
}>();

const miniChartRef = ref<HTMLDivElement>();
let miniChart: echarts.ECharts | null = null;

function initMiniChart() {
  if (!miniChartRef.value) return;
  miniChart = echarts.init(miniChartRef.value);
  miniChart.setOption({
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: { type: 'category', show: false, data: props.data.historyData.map((_, i) => i) },
    yAxis: { type: 'value', show: false },
    series: [{
      type: 'line',
      data: props.data.historyData,
      lineStyle: { color: props.data.color || '#409eff', width: 1.5 },
      smooth: true,
      symbol: 'none',
    }],
  });
}

onMounted(() => {
  initMiniChart();
});
</script>

<template>
  <div class="metric-card">
    <div class="metric-name">{{ data.name }}</div>
    <div class="metric-value" :style="{ color: data.color || '#409eff' }">
      {{ data.value.toFixed(1) }} {{ data.unit }}
    </div>
    <div ref="miniChartRef" class="mini-chart"></div>
  </div>
</template>

<style scoped>
.metric-card {
  background: #f8f9fa;
  border-radius: 4px;
  padding: 8px;
}
.metric-name {
  font-size: 10px;
  color: #999;
}
.metric-value {
  font-size: 14px;
  font-weight: 600;
  margin: 4px 0;
}
.mini-chart {
  height: 20px;
  width: 100%;
}
</style>
```

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/MetricCard.vue
git commit -m "feat(performance-monitor): 添加次要指标卡片组件 MetricCard"
```

---

## Task 9: 前端组件 - TOP10 概览

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/Top10List.vue`

- [ ] **Step 1: 创建 TOP10 概览组件**

```vue
<script setup lang="ts">
import { computed } from 'vue';
import type { Top10Item } from '../types';
import * as echarts from 'echarts';
import { ref, onMounted, watch } from 'vue';

const props = defineProps<{
  title: string;
  items: Top10Item[];
}>();

// TOP3 显示迷你趋势线
const top3 = computed(() => props.items.slice(0, 3));
// 其他显示列表
const others = computed(() => props.items.slice(3, 10));

function getMiniChartOption(trendData: number[], color: string) {
  return {
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: { type: 'category', show: false, data: trendData.map((_, i) => i) },
    yAxis: { type: 'value', show: false },
    series: [{
      type: 'line',
      data: trendData,
      lineStyle: { color, width: 1.5 },
      smooth: true,
      symbol: 'none',
    }],
  };
}
</script>

<template>
  <div class="top10-list">
    <div class="top10-title">{{ title }}</div>
    <div class="top10-content">
      <!-- TOP3 迷你趋势线 -->
      <div v-for="(item, index) in top3" :key="index" class="top10-item top-item" :style="{ background: index === 0 ? '#f0f9eb' : index === 1 ? '#fef0f0' : '#fdf6ec' }">
        <div class="mini-trend" ref="chartRefs">
          <!-- 迷你趋势线将通过 echarts 渲染 -->
          <svg class="mini-svg">
            <polyline :points="item.trendData.map((v, i) => `${i},${10 - v/10}`).join(' ')" :stroke="item.color" stroke-width="1.5" fill="none"/>
          </svg>
        </div>
        <span class="process-name">{{ item.name }}</span>
        <span class="process-value" :style="{ color: item.color }">{{ item.value.toFixed(1) }}%</span>
      </div>
      
      <!-- TOP4-10 列表 -->
      <div v-for="(item, index) in others" :key="index + 3" class="top10-item other-item">
        <span class="process-name">{{ item.name }}</span>
        <span class="process-value">{{ item.value.toFixed(1) }}%</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.top10-list {
  background: #fff;
  border-radius: 6px;
  padding: 12px;
}
.top10-title {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 8px;
}
.top10-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.top10-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px;
  border-radius: 4px;
}
.top-item {
  background: #f8f9fa;
}
.mini-trend {
  width: 40px;
  height: 16px;
}
.mini-svg {
  width: 100%;
  height: 100%;
}
.process-name {
  font-size: 11px;
  flex: 1;
}
.process-value {
  font-size: 12px;
  font-weight: 600;
}
.other-item {
  justify-content: space-between;
  font-size: 10px;
  color: #666;
  padding: 4px 0;
  border-top: 1px dashed #eee;
}
</style>
```

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/Top10List.vue
git commit -m "feat(performance-monitor): 添加 TOP10 概览组件 Top10List"
```

---

## Task 10: 前端组件 - 开始采集弹窗

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/CollectDialog.vue`

- [ ] **Step 1: 创建采集配置弹窗组件**

```vue
<script setup lang="ts">
import { ref, computed } from 'vue';
import { ElMessage } from 'element-plus';
import { startCollect } from '#/api/core/performance-monitor';
import type { TargetProcessConfig } from '#/api/core/performance-monitor';

const props = defineProps<{
  visible: boolean;
  deviceId: string;
  deviceName: string;
  deviceIp: string;
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'started', collectId: string): void;
}>();

const interval = ref(5);
const searchQuery = ref('');
const processes = ref<Array<{ name: string; pid: number; cpu: number; memory: number; gpu: number }>>([]);
const selectedProcesses = ref<Array<{ name: string; pids: number[] }>>([]);
const presetProcesses = ['chrome.exe', 'node.exe', 'python.exe', 'vscode.exe'];

// 模拟进程列表（实际需要从 Worker API 获取）
const filteredProcesses = computed(() => {
  if (!searchQuery.value) return processes.value;
  return processes.value.filter(p => p.name.toLowerCase().includes(searchQuery.value.toLowerCase()));
});

async function handleStart() {
  if (selectedProcesses.value.length === 0) {
    ElMessage.warning('请选择目标进程');
    return;
  }
  
  try {
    const result = await startCollect({
      device_id: props.deviceId,
      interval: interval.value,
      target_processes: selectedProcesses.value,
    });
    ElMessage.success('开始采集');
    emit('started', result.collect_id);
    emit('update:visible', false);
  } catch (error) {
    ElMessage.error('启动采集失败');
  }
}

function handleCancel() {
  emit('update:visible', false);
}

function toggleProcess(name: string, pid: number) {
  const existing = selectedProcesses.value.find(s => s.name === name);
  if (existing) {
    if (existing.pids.includes(pid)) {
      existing.pids = existing.pids.filter(p => p !== pid);
      if (existing.pids.length === 0) {
        selectedProcesses.value = selectedProcesses.value.filter(s => s.name !== name);
      }
    } else {
      existing.pids.push(pid);
    }
  } else {
    selectedProcesses.value.push({ name, pids: [pid] });
  }
}

function isSelected(name: string, pid: number): boolean {
  const existing = selectedProcesses.value.find(s => s.name === name);
  return existing?.pids.includes(pid) ?? false;
}
</script>

<template>
  <el-dialog :model-value="visible" @update:model-value="emit('update:visible', $event)" title="采集配置" width="500px">
    <div class="collect-dialog">
      <div class="device-info">
        目标设备: {{ deviceName }} ({{ deviceIp })
      </div>
      
      <div class="interval-section">
        <span>采集频率:</span>
        <el-input-number v-model="interval" :min="1" :max="60" size="small" />
        <span>秒</span>
        <el-button-group>
          <el-button size="small" @click="interval = 1">1秒</el-button>
          <el-button size="small" type="primary" @click="interval = 5">5秒</el-button>
          <el-button size="small" @click="interval = 10">10秒</el-button>
          <el-button size="small" @click="interval = 30">30秒</el-button>
        </el-button-group>
      </div>
      
      <div class="process-section">
        <div class="process-header">
          <span>目标进程:</span>
          <el-input v-model="searchQuery" placeholder="搜索进程名" size="small" style="width: 150px" />
        </div>
        <div class="preset-processes">
          <span>预设常用:</span>
          <el-tag v-for="name in presetProcesses" :key="name" size="small" style="margin-right: 4px">{{ name }}</el-tag>
        </div>
        <div class="process-list">
          <div v-for="p in filteredProcesses" :key="p.pid" class="process-item">
            <el-checkbox :model-value="isSelected(p.name, p.pid)" @change="toggleProcess(p.name, p.pid)" />
            <span class="process-name">{{ p.name }}</span>
            <span class="process-pid">PID:{{ p.pid }}</span>
            <span class="process-cpu">CPU:{{ p.cpu.toFixed(1) }}%</span>
          </div>
        </div>
        <div class="selected-summary">
          已选择: 
          <el-tag v-for="s in selectedProcesses" :key="s.name" size="small">
            {{ s.name }}({{ s.pids.length }})
          </el-tag>
          <el-button size="small" text @click="selectedProcesses = []">清空</el-button>
        </div>
      </div>
    </div>
    
    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" @click="handleStart">开始采集</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.collect-dialog {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.device-info {
  font-size: 12px;
  color: #666;
}
.interval-section {
  display: flex;
  align-items: center;
  gap: 8px;
}
.process-section {
  border: 1px solid #eee;
  border-radius: 6px;
  padding: 12px;
}
.process-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}
.preset-processes {
  font-size: 11px;
  color: #999;
  margin-bottom: 8px;
}
.process-list {
  max-height: 200px;
  overflow-y: auto;
}
.process-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px;
  border-bottom: 1px solid #eee;
}
.process-name {
  flex: 1;
  font-size: 12px;
}
.process-pid, .process-cpu {
  font-size: 10px;
  color: #999;
}
.selected-summary {
  font-size: 11px;
  margin-top: 8px;
}
</style>
```

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/CollectDialog.vue
git commit -m "feat(performance-monitor): 添加开始采集弹窗组件 CollectDialog"
```

---

## Task 11: 前端主页面

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/index.vue`

- [ ] **Step 1: 创建主页面**

这是一个较大的组件，包含：
- 顶部控制栏（设备选择、开始/停止采集、采集状态）
- 时间轴选择器
- 左侧 4 个曲线图（CPU、GPU、提交内存、内存使用）
- 右侧次要指标卡片（6个）
- TOP10 概览区

详细代码见附录 A。

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/performance-monitor/index.vue
git commit -m "feat(performance-monitor): 添加主页面 index.vue"
```

---

## Task 12: 前端版本对比页面

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/compare.vue`
- Create: `web/apps/web-ele/src/views/performance-monitor/components/TagDialog.vue`

- [ ] **Step 1: 创建标签配置弹窗组件**

```vue
<script setup lang="ts">
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { createTag } from '#/api/core/performance-monitor';

const props = defineProps<{
  visible: boolean;
  collectId: string;
  clickedTime: number;  // 点击的相对时间
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'created'): void;
}>();

const name = ref('');
const duration = ref(60);
const type = ref<'peak' | 'mean'>('peak');

async function handleCreate() {
  if (!name.value) {
    ElMessage.warning('请输入标签名称');
    return;
  }
  
  try {
    await createTag({
      collect_id: props.collectId,
      name: name.value,
      start_relative_time: props.clickedTime,
      duration: duration.value,
      type: type.value,
    });
    ElMessage.success('标签创建成功');
    emit('created');
    emit('update:visible', false);
  } catch (error) {
    ElMessage.error('创建标签失败');
  }
}
</script>

<template>
  <el-dialog :model-value="visible" @update:model-value="emit('update:visible', $event)" title="添加区间标签" width="400px">
    <div class="tag-dialog">
      <div class="field">
        <span>起始时间:</span>
        <span>{{ clickedTime }}秒</span>
      </div>
      <div class="field">
        <span>标签名称:</span>
        <el-input v-model="name" placeholder="如：发起共享、场景加载" />
      </div>
      <div class="field">
        <span>时间长度:</span>
        <el-input-number v-model="duration" :min="10" :max="300" />
        <span>秒</span>
        <el-button-group>
          <el-button size="small" @click="duration = 30">30秒</el-button>
          <el-button size="small" type="primary" @click="duration = 60">60秒</el-button>
          <el-button size="small" @click="duration = 120">120秒</el-button>
        </el-button-group>
      </div>
      <div class="field">
        <span>区间类型:</span>
        <el-radio-group v-model="type">
          <el-radio value="peak">峰值区间</el-radio>
          <el-radio value="mean">均值区间</el-radio>
        </el-radio-group>
      </div>
    </div>
    
    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" @click="handleCreate">确认添加</el-button>
    </template>
  </el-dialog>
</template>
```

- [ ] **Step 2: 创建版本对比页面**

详细代码见附录 B。

- [ ] **Step 3: 提交**

```bash
git add web/apps/web-ele/src/views/performance-monitor/compare.vue web/apps/web-ele/src/views/performance-monitor/components/TagDialog.vue
git commit -m "feat(performance-monitor): 添加版本对比页面和标签弹窗组件"
```

---

## Task 13: 菜单初始化

**Files:**
- Modify: `backend-fastapi/scripts/init_all_menus.py`（添加性能监控菜单）

- [ ] **Step 1: 在菜单初始化脚本中添加性能监控菜单**

在 init_all_menus.py 的 ALL_MENUS 列表中添加：
```python
# ==================== 性能监控（一级菜单）====================
{
    "id": "performance-monitor-root",
    "name": "PerformanceMonitor",
    "title": "性能监控",
    "path": "/performance-monitor",
    "type": "catalog",
    "icon": "ep:monitor",
    "order": 15,
    "parent_id": None,
},
# 性能监控子菜单
{
    "id": "performance-monitor-main",
    "name": "PerformanceMonitorMain",
    "title": "性能监控",
    "path": "/performance-monitor",
    "type": "menu",
    "component": "/views/performance-monitor/index",
    "parent_id": "performance-monitor-root",
    "order": 1,
},
{
    "id": "performance-monitor-compare",
    "name": "PerformanceMonitorCompare",
    "title": "版本对比",
    "path": "/performance-monitor/compare",
    "type": "menu",
    "component": "/views/performance-monitor/compare",
    "parent_id": "performance-monitor-root",
    "order": 2,
},
```

- [ ] **Step 2: 运行菜单初始化脚本**

```bash
cd backend-fastapi
python scripts/init_all_menus.py
```

- [ ] **Step 3: 提交**

```bash
git add backend-fastapi/scripts/init_all_menus.py
git commit -m "feat(performance-monitor): 添加性能监控菜单配置"
```

---

## 附录 A: 主页面完整代码

见设计文档 `docs/superpowers/specs/2026-05-01-performance-monitor-design.md` 的主页面设计部分。

---

## 附录 B: 版本对比页面完整代码

见设计文档 `docs/superpowers/specs/2026-05-01-performance-monitor-design.md` 的版本对比页面设计部分。

---

## 测试清单

- [ ] 后端 API 测试：采集开始/停止/状态查询
- [ ] 后端 API 测试：数据上报和查询
- [ ] 后端 API 测试：标签 CRUD
- [ ] 后端 API 测试：版本对比
- [ ] 前端测试：页面渲染和交互
- [ ] 前端测试：曲线图数据更新
- [ ] 前端测试：采集状态轮询
- [ ] 前端测试：标签创建和编辑

---

## 验收标准

1. 主页面正确显示 4 个曲线图 + 6 个次要指标 + TOP10 概览
2. 开始采集弹窗支持进程选择和频率配置
3. 采集过程中实时更新曲线图（轮询）
4. 时间轴支持快速选择和版本标记跳转
5. 版本对比页面支持最多 6 个版本同时对比
6. 标签系统支持点击曲线创建、编辑、删除
7. 数据摘要表正确标记最优/最差值
8. 导出 HTML 报告和 Excel 数据功能可用