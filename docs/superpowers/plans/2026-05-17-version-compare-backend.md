# 版本对比页面后端实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修改后端 API 支持无设备限制的版本列表，新增对比标签存储模型和 API

**Architecture:** 新建对比标签模型，修改版本列表 API 移除 device_id 必须参数，新增标签管理 API

**Tech Stack:** FastAPI + SQLAlchemy + PostgreSQL

---

## 文件结构

### 新建文件
- `backend-fastapi/core/performance_monitor/compare_model.py` - 对比标签模型
- `backend-fastapi/core/performance_monitor/compare_schema.py` - 对比标签 Schema

### 修改文件
- `backend-fastapi/core/performance_monitor/api.py` - 新增对比标签 API，修改版本列表 API
- `backend-fastapi/core/performance_monitor/service.py` - 新增对比标签 Service
- `backend-fastapi/core/performance_monitor/model.py` - 导入对比标签模型

---

## Task 1: 创建对比标签数据模型

**Files:**
- Create: `backend-fastapi/core/performance_monitor/compare_model.py`

- [ ] **Step 1: 创建 compare_model.py 文件**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
版本对比标签模型
"""
from sqlalchemy import Column, String, Integer, DateTime
from app.base_model import BaseModel


class CompareTag(BaseModel):
    """对比标签表"""
    __tablename__ = "performance_compare_tag"

    name = Column(String(100), nullable=False, comment="标签名称")
    type = Column(String(20), nullable=False, default="peak", comment="类型: peak(冲高) / stable(稳态)")
    start_time = Column(DateTime, nullable=False, comment="开始时间（绝对时间）")
    end_time = Column(DateTime, nullable=False, comment="结束时间（绝对时间）")
    note = Column(String(500), nullable=True, comment="备注")
    
    # 创建人和修改人继承自 BaseModel
    # 使用 sys_create_datetime, sys_update_datetime 继承自 BaseModel
```

- [ ] **Step 2: 在 model.py 中导入对比标签模型**

修改 `backend-fastapi/core/performance_monitor/model.py`，在文件末尾添加：

```python
from core.performance_monitor.compare_model import CompareTag
```

- [ ] **Step 3: 提交模型文件**

```bash
git add backend-fastapi/core/performance_monitor/compare_model.py
git add backend-fastapi/core/performance_monitor/model.py
git commit -m "feat(model): 创建 CompareTag 对比标签模型"
```

---

## Task 2: 创建对比标签 Schema

**Files:**
- Create: `backend-fastapi/core/performance_monitor/compare_schema.py`

- [ ] **Step 1: 创建 compare_schema.py 文件**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
版本对比标签 Schema
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CompareTagCreate(BaseModel):
    """创建对比标签请求"""
    name: str = Field(..., max_length=100, description="标签名称")
    type: str = Field(default="peak", description="类型: peak(冲高) / stable(稳态)")
    start_time: datetime = Field(..., description="开始时间")
    end_time: datetime = Field(..., description="结束时间")
    note: Optional[str] = Field(None, max_length=500, description="备注")


class CompareTagUpdate(BaseModel):
    """更新对比标签请求"""
    name: Optional[str] = Field(None, max_length=100)
    type: Optional[str] = Field(None)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    note: Optional[str] = Field(None, max_length=500)


class CompareTagResponse(BaseModel):
    """对比标签响应"""
    id: str
    name: str
    type: str
    type_display: str  # 冲高 / 稳态
    start_time: datetime
    end_time: datetime
    note: Optional[str]
    sys_create_datetime: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 2: 提交 Schema 文件**

```bash
git add backend-fastapi/core/performance_monitor/compare_schema.py
git commit -m "feat(schema): 创建 CompareTag Schema"
```

---

## Task 3: 创建对比标签 Service

**Files:**
- Modify: `backend-fastapi/core/performance_monitor/service.py`

- [ ] **Step 1: 在 service.py 中添加 CompareTagService 类**

在文件末尾添加：

```python
from sqlalchemy import select
from core.performance_monitor.compare_model import CompareTag
from core.performance_monitor.compare_schema import CompareTagCreate, CompareTagUpdate


class CompareTagService:
    """对比标签服务"""

    @staticmethod
    async def create_tag(db: AsyncSession, request: CompareTagCreate) -> str:
        """创建对比标签"""
        tag = CompareTag(
            name=request.name,
            type=request.type,
            start_time=request.start_time,
            end_time=request.end_time,
            note=request.note,
        )
        db.add(tag)
        await db.commit()
        await db.refresh(tag)
        return str(tag.id)

    @staticmethod
    async def get_tags(db: AsyncSession) -> list[CompareTag]:
        """获取所有对比标签"""
        stmt = select(CompareTag).where(CompareTag.is_deleted == False).order_by(CompareTag.sys_create_datetime.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_tag(db: AsyncSession, tag_id: str, request: CompareTagUpdate) -> bool:
        """更新对比标签"""
        tag = await db.get(CompareTag, tag_id)
        if not tag or tag.is_deleted:
            return False
        if request.name:
            tag.name = request.name
        if request.type:
            tag.type = request.type
        if request.start_time:
            tag.start_time = request.start_time
        if request.end_time:
            tag.end_time = request.end_time
        if request.note:
            tag.note = request.note
        await db.commit()
        return True

    @staticmethod
    async def delete_tag(db: AsyncSession, tag_id: str) -> bool:
        """删除对比标签（软删除）"""
        tag = await db.get(CompareTag, tag_id)
        if not tag or tag.is_deleted:
            return False
        tag.is_deleted = True
        await db.commit()
        return True
```

- [ ] **Step 2: 提交 Service 文件修改**

```bash
git add backend-fastapi/core/performance_monitor/service.py
git commit -m "feat(service): 创建 CompareTagService 对比标签服务"
```

---

## Task 4: 修改版本列表 API（移除 device_id 必须参数）

**Files:**
- Modify: `backend-fastapi/core/performance_monitor/api.py`
- Modify: `backend-fastapi/core/performance_monitor/service.py`

- [ ] **Step 1: 修改版本列表 API**

在 `api.py` 中修改 `get_versions` 函数（约 276-280 行）：

```python
@router.get("/version/list")
async def get_versions(
    device_id: Optional[str] = Query(None, description="设备ID（可选，不传则返回所有）"),
    db: AsyncSession = Depends(get_db)
):
    """获取版本列表"""
    versions = await PerformanceVersionService.get_versions(db, device_id)
    return {"items": versions}
```

- [ ] **Step 2: 修改版本列表 Service**

在 `service.py` 中修改 `PerformanceVersionService.get_versions` 方法：

```python
@staticmethod
async def get_versions(db: AsyncSession, device_id: Optional[str] = None) -> list[PerformanceVersion]:
    """获取版本列表"""
    stmt = select(PerformanceVersion).where(PerformanceVersion.is_deleted == False)
    if device_id:
        stmt = stmt.where(PerformanceVersion.device_id == device_id)
    stmt = stmt.order_by(PerformanceVersion.sys_create_datetime.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())
```

- [ ] **Step 3: 提交版本列表 API 修改**

```bash
git add backend-fastapi/core/performance_monitor/api.py
git add backend-fastapi/core/performance_monitor/service.py
git commit -m "feat(api): 版本列表 API 支持 device_id 可选参数"
```

---

## Task 5: 新增对比标签 API

**Files:**
- Modify: `backend-fastapi/core/performance_monitor/api.py`

- [ ] **Step 1: 在 api.py 中添加对比标签 API 路由**

在文件末尾添加：

```python
from core.performance_monitor.compare_schema import CompareTagCreate, CompareTagUpdate, CompareTagResponse
from core.performance_monitor.service import CompareTagService


# ===== 对比标签管理 =====

@router.post("/compare/tag")
async def create_compare_tag(
    request: CompareTagCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建对比标签"""
    tag_id = await CompareTagService.create_tag(db, request)
    return {"id": tag_id, "status": "created"}


@router.get("/compare/tags")
async def get_compare_tags(db: AsyncSession = Depends(get_db)):
    """获取对比标签列表"""
    tags = await CompareTagService.get_tags(db)
    items = [CompareTagResponse.model_validate(t, from_attributes=True) for t in tags]
    # 添加 type_display
    for item in items:
        item.type_display = "冲高" if item.type == "peak" else "稳态"
    return {"items": items}


@router.put("/compare/tag/{tag_id}")
async def update_compare_tag(
    tag_id: str,
    request: CompareTagUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新对比标签"""
    success = await CompareTagService.update_tag(db, tag_id, request)
    return {"status": "updated" if success else "not_found"}


@router.delete("/compare/tag/{tag_id}")
async def delete_compare_tag(
    tag_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除对比标签"""
    success = await CompareTagService.delete_tag(db, tag_id)
    return {"status": "deleted" if success else "not_found"}
```

- [ ] **Step 2: 提交对比标签 API**

```bash
git add backend-fastapi/core/performance_monitor/api.py
git commit -m "feat(api): 新增对比标签管理 API"
```

---

## Task 6: 数据库迁移

- [ ] **Step 1: 创建数据库迁移脚本**

```bash
cd backend-fastapi
alembic revision --autogenerate -m "add compare_tag table"
```

- [ ] **Step 2: 执行数据库迁移**

```bash
alembic upgrade head
```

- [ ] **Step 3: 提交迁移文件**

```bash
git add backend-fastapi/alembic/versions/
git commit -m "db: 新增 compare_tag 表迁移"
```

---

## Task 7: 验证 API 功能

- [ ] **Step 1: 启动后端服务器**

```bash
cd backend-fastapi
python main.py
```

- [ ] **Step 2: 测试 API**

访问 Swagger UI: http://localhost:8000/docs

测试：
- GET /api/core/performance-monitor/version/list（无 device_id）
- POST /api/core/performance-monitor/compare/tag
- GET /api/core/performance-monitor/compare/tags
- DELETE /api/core/performance-monitor/compare/tag/{tag_id}

- [ ] **Step 3: 最终提交**

```bash
git add -A
git commit -m "feat(compare): 后端对比标签功能完成"
```

---

## 成功标准

- 版本列表 API 可不传 device_id 返回所有版本
- 对比标签 CRUD API 正常工作
- 数据库迁移成功执行