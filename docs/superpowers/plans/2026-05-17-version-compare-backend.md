# 版本对比页面后端实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修改后端 API 支持无设备限制的版本列表，新增对比标签存储模型和 API

**Architecture:** 新建对比标签模型，修改版本列表 API 移除 device_id 必须参数，新增标签管理 API。遵循现有代码库模式：Service 继承 BaseService，Schema 使用 Pydantic v2 ConfigDict。

**Tech Stack:** FastAPI + SQLAlchemy + PostgreSQL + Pydantic v2

---

## 文件结构

### 新建文件
- `backend-fastapi/core/performance_monitor/compare_model.py` - 对比标签模型
- `backend-fastapi/core/performance_monitor/compare_schema.py` - 对比标签 Schema

### 修改文件
- `backend-fastapi/core/performance_monitor/model.py` - 导入对比标签模型（顶部）
- `backend-fastapi/core/performance_monitor/service.py` - 新增 CompareTagService（顶部导入，末尾类定义）
- `backend-fastapi/core/performance_monitor/api.py` - 新增对比标签 API（顶部导入，末尾路由）

---

## Task 1: 创建对比标签数据模型

**Files:**
- Create: `backend-fastapi/core/performance_monitor/compare_model.py`

- [ ] **Step 1: 创建 compare_model.py 文件**

遵循现有模型模式（参考 PerformanceTag 模型）：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
版本对比标签模型
"""
from sqlalchemy import Column, String, DateTime, Text
from app.base_model import BaseModel


class CompareTag(BaseModel):
    """对比标签表（跨版本共享标签）"""
    __tablename__ = "performance_compare_tag"

    name = Column(String(100), nullable=False, comment="标签名称")
    type = Column(String(20), nullable=False, default="peak", comment="类型: peak(冲高) / stable(稳态)")
    start_time = Column(DateTime, nullable=False, comment="开始时间（绝对时间，UTC）")
    end_time = Column(DateTime, nullable=False, comment="结束时间（绝对时间，UTC）")
    note = Column(Text, nullable=True, comment="备注")
```

- [ ] **Step 2: 在 model.py 顶部导入对比标签模型**

修改 `backend-fastapi/core/performance_monitor/model.py`，在导入区域添加：

找到现有导入位置（约第 14-17 行），添加 CompareTag 导入：

```python
# 现有导入：
from core.performance_monitor.compare_model import (
    CompareTag
)
```

完整导入列表应该是：
```python
from core.performance_monitor.models import (
    PerformanceCollect, PerformanceData, PerformanceTag, PerformanceVersion,
    PerformanceMetricMapping, PerformanceMarker, CompareTag
)
```

**注意**：根据现有文件结构，可能需要检查 model.py 的实际导入方式。

- [ ] **Step 3: 提交模型文件**

```bash
git add backend-fastapi/core/performance_monitor/compare_model.py
git add backend-fastapi/core/performance_monitor/model.py
git commit -m "feat(model): 创建 CompareTag 对比标签模型"
```

- [ ] **Step 4: 验证提交成功**

```bash
git status
```

Expected: `nothing to commit, working tree clean`

---

## Task 2: 创建对比标签 Schema（Pydantic v2）

**Files:**
- Create: `backend-fastapi/core/performance_monitor/compare_schema.py`

- [ ] **Step 1: 创建 compare_schema.py 文件**

遵循现有 Schema 模式（使用 Pydantic v2 ConfigDict，添加 datetime 序列化）：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
版本对比标签 Schema
"""
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class CompareTagCreate(BaseModel):
    """创建对比标签请求"""
    name: str = Field(..., max_length=100, description="标签名称")
    type: str = Field(default="peak", description="类型: peak(冲高) / stable(稳态)")
    start_time: datetime = Field(..., description="开始时间（UTC）")
    end_time: datetime = Field(..., description="结束时间（UTC）")
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
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    type: str
    type_display: str = ""  # 冲高 / 稳态（在 API 中设置）
    start_time: datetime
    end_time: datetime
    note: Optional[str]
    sys_create_datetime: datetime

    @field_serializer('start_time', 'end_time', 'sys_create_datetime')
    def serialize_datetime_as_utc(self, value: Optional[datetime]) -> Optional[str]:
        """将 datetime 序列化为带 Z 后缀的 UTC 格式"""
        if value is None:
            return None
        if value.tzinfo is None:
            return value.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
        return value.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
```

- [ ] **Step 2: 提交 Schema 文件**

```bash
git add backend-fastapi/core/performance_monitor/compare_schema.py
git commit -m "feat(schema): 创建 CompareTag Schema（Pydantic v2）"
```

- [ ] **Step 3: 验证提交成功**

```bash
git status
```

---

## Task 3: 创建对比标签 Service（继承 BaseService）

**Files:**
- Modify: `backend-fastapi/core/performance_monitor/service.py`

- [ ] **Step 1: 在 service.py 顶部添加导入**

在导入区域（约第 14-17 行）添加：

```python
from core.performance_monitor.compare_model import CompareTag
from core.performance_monitor.compare_schema import CompareTagCreate, CompareTagUpdate
```

- [ ] **Step 2: 在 service.py 文件末尾添加 CompareTagService 类**

遵循现有 Service 模式（继承 BaseService，使用 @classmethod）：

```python
class CompareTagService(BaseService):
    """对比标签服务"""
    model = CompareTag

    @classmethod
    async def create_tag(cls, db: AsyncSession, request: CompareTagCreate) -> str:
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

    @classmethod
    async def get_tags(cls, db: AsyncSession) -> List[CompareTag]:
        """获取所有对比标签"""
        stmt = select(CompareTag).where(CompareTag.is_deleted == False).order_by(CompareTag.sys_create_datetime.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def update_tag(cls, db: AsyncSession, tag_id: str, request: CompareTagUpdate) -> bool:
        """更新对比标签"""
        tag = await db.get(CompareTag, tag_id)
        if not tag or tag.is_deleted:
            return False
        if request.name is not None:
            tag.name = request.name
        if request.type is not None:
            tag.type = request.type
        if request.start_time is not None:
            tag.start_time = request.start_time
        if request.end_time is not None:
            tag.end_time = request.end_time
        if request.note is not None:
            tag.note = request.note
        await db.commit()
        return True

    @classmethod
    async def delete_tag(cls, db: AsyncSession, tag_id: str) -> bool:
        """删除对比标签（软删除）"""
        tag = await db.get(CompareTag, tag_id)
        if not tag or tag.is_deleted:
            return False
        tag.is_deleted = True
        await db.commit()
        return True
```

- [ ] **Step 3: 提交 Service 文件修改**

```bash
git add backend-fastapi/core/performance_monitor/service.py
git commit -m "feat(service): 创建 CompareTagService 对比标签服务"
```

- [ ] **Step 4: 验证提交成功**

```bash
git status
```

---

## Task 4: 修改版本列表 API（移除 device_id 必须参数）

**Files:**
- Modify: `backend-fastapi/core/performance_monitor/api.py`
- Modify: `backend-fastapi/core/performance_monitor/service.py`

- [ ] **Step 1: 修改版本列表 API**

在 `api.py` 中修改 `get_versions` 函数（约第 276-280 行）：

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

**注意**：需要导入 `Optional`（已在顶部导入，检查确认）。

- [ ] **Step 2: 修改版本列表 Service**

在 `service.py` 中找到 `PerformanceVersionService.get_versions` 方法，修改为支持 device_id 可选：

```python
@classmethod
async def get_versions(cls, db: AsyncSession, device_id: Optional[str] = None) -> List[PerformanceVersion]:
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

- [ ] **Step 4: 验证提交成功**

```bash
git status
```

---

## Task 5: 新增对比标签 API

**Files:**
- Modify: `backend-fastapi/core/performance_monitor/api.py`

- [ ] **Step 1: 在 api.py 顶部添加导入**

在导入区域添加：

```python
from core.performance_monitor.compare_schema import CompareTagCreate, CompareTagUpdate, CompareTagResponse
from core.performance_monitor.service import CompareTagService
```

- [ ] **Step 2: 在 api.py 文件末尾添加对比标签 API 路由**

```python
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
    items = []
    for t in tags:
        item = CompareTagResponse.model_validate(t)
        # 设置 type_display
        item.type_display = "冲高" if t.type == "peak" else "稳态"
        items.append(item)
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

- [ ] **Step 3: 提交对比标签 API**

```bash
git add backend-fastapi/core/performance_monitor/api.py
git commit -m "feat(api): 新增对比标签管理 API"
```

- [ ] **Step 4: 验证提交成功**

```bash
git status
```

---

## Task 6: 数据库迁移

- [ ] **Step 1: 创建数据库迁移脚本**

```bash
cd backend-fastapi
alembic revision --autogenerate -m "add compare_tag table"
```

- [ ] **Step 2: 检查迁移脚本**

打开生成的迁移文件（`alembic/versions/xxx_add_compare_tag_table.py`），确认：
- 包含 `performance_compare_tag` 表创建
- 包含所有字段：id, name, type, start_time, end_time, note, is_deleted 等

- [ ] **Step 3: 执行数据库迁移**

```bash
alembic upgrade head
```

Expected: 迁移成功，无错误

- [ ] **Step 4: 提交迁移文件**

```bash
git add backend-fastapi/alembic/versions/
git commit -m "db: 新增 compare_tag 表迁移"
```

- [ ] **Step 5: 验证提交成功**

```bash
git status
```

---

## Task 7: 验证 API 功能

- [ ] **Step 1: 启动后端服务器**

```bash
cd backend-fastapi
python main.py
```

Expected: 服务器启动成功

- [ ] **Step 2: 访问 Swagger UI 测试 API**

访问: http://localhost:8000/docs

测试以下 API：
1. `GET /api/core/performance-monitor/version/list`（不传 device_id）
2. `POST /api/core/performance-monitor/compare/tag`
3. `GET /api/core/performance-monitor/compare/tags`
4. `DELETE /api/core/performance-monitor/compare/tag/{tag_id}`

- [ ] **Step 3: 最终提交（如有遗漏修复）**

```bash
git add -A
git commit -m "feat(compare): 后端对比标签功能完成"
```

- [ ] **Step 4: 验证提交成功**

```bash
git status
```

---

## 成功标准

- 版本列表 API 可不传 device_id 返回所有版本
- 对比标签 CRUD API 正常工作
- 数据库迁移成功执行
- 所有 Service 继承 BaseService 并使用 @classmethod
- 所有 Schema 使用 Pydantic v2 ConfigDict
- datetime 字段正确序列化为 UTC 格式