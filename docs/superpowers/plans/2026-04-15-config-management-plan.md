# 配置管理功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现配置模板管理和配置下发功能，支持批量下发配置到目标执行机。

**Architecture:** 后端新增 config_template 模块，修改 env_machine 模块增加 config_version 字段；前端新增 env-machine/config.vue 页面，遵循现有 upgrade.vue 的设计风格。

**Tech Stack:** FastAPI + SQLAlchemy + PostgreSQL（后端），Vue 3 + Element Plus（前端）

---

## 文件结构

### 后端新建文件
- `backend-fastapi/core/config_template/__init__.py` - 模块入口
- `backend-fastapi/core/config_template/model.py` - 配置模板数据模型
- `backend-fastapi/core/config_template/schema.py` - Pydantic Schema
- `backend-fastapi/core/config_template/service.py` - 业务逻辑层
- `backend-fastapi/core/config_template/api.py` - FastAPI 路由

### 后端修改文件
- `backend-fastapi/core/router.py` - 注册 config_template 路由
- `backend-fastapi/core/env_machine/model.py` - 新增 config_version 字段
- `backend-fastapi/core/env_machine/schema.py` - EnvRegisterRequest 新增 config_version
- `backend-fastapi/core/env_machine/api.py` - 注册接口接收 config_version

### 前端新建文件
- `web/apps/web-ele/src/api/core/env-machine-config.ts` - API 接口定义
- `web/apps/web-ele/src/views/env-machine/config.vue` - 配置管理页面
- `web/apps/web-ele/src/router/routes/modules/env-machine-config.ts` - 路由配置

### 脚本文件
- `backend-fastapi/scripts/init_config_template_menu.py` - 菜单初始化

---

## Task 1: 后端 - 配置模板数据模型

**Files:**
- Create: `backend-fastapi/core/config_template/__init__.py`
- Create: `backend-fastapi/core/config_template/model.py`

- [ ] **Step 1: 创建模块入口文件**

```python
# backend-fastapi/core/config_template/__init__.py
"""
配置模板管理模块
"""
```

- [ ] **Step 2: 创建配置模板数据模型**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2026-04-15
@File: model.py
@Desc: ConfigTemplate Model - 配置模板模型
"""
from sqlalchemy import Column, String, Text, Index

from app.base_model import BaseModel


class ConfigTemplate(BaseModel):
    """
    配置模板表

    字段说明：
    - name: 模板名称（唯一）
    - namespace: 适用命名空间（可选，null表示全部）
    - note: 备注说明
    - config_content: YAML 配置内容
    - version: 版本号（YYYYMMDD-HHMMSS）
    """
    __tablename__ = "config_template"

    # 模板名称（唯一）
    name = Column(String(64), nullable=False, unique=True, comment="模板名称")

    # 适用命名空间（可选）
    namespace = Column(String(64), nullable=True, comment="适用命名空间")

    # 备注说明
    note = Column(Text, nullable=True, comment="备注说明")

    # YAML 配置内容
    config_content = Column(Text, nullable=False, comment="YAML配置内容")

    # 版本号（自动生成）
    version = Column(String(20), nullable=False, comment="版本号YYYYMMDD-HHMMSS")

    # 索引
    __table_args__ = (
        Index("ix_config_template_namespace", "namespace"),
    )
```

- [ ] **Step 3: Commit**

```bash
git add backend-fastapi/core/config_template/__init__.py backend-fastapi/core/config_template/model.py
git commit -m "feat: 新增配置模板数据模型"
```

---

## Task 2: 后端 - 配置模板 Schema

**Files:**
- Create: `backend-fastapi/core/config_template/schema.py`

- [ ] **Step 1: 创建 Schema 定义**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2026-04-15
@File: schema.py
@Desc: ConfigTemplate Schema - 配置模板数据验证模式
"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class ConfigTemplateCreate(BaseModel):
    """创建配置模板请求"""
    name: str = Field(..., description="模板名称", max_length=64)
    namespace: Optional[str] = Field(None, description="适用命名空间", max_length=64)
    note: Optional[str] = Field(None, description="备注说明")
    config_content: str = Field(..., description="YAML配置内容")


class ConfigTemplateUpdate(BaseModel):
    """更新配置模板请求"""
    name: Optional[str] = Field(None, description="模板名称", max_length=64)
    namespace: Optional[str] = Field(None, description="适用命名空间", max_length=64)
    note: Optional[str] = Field(None, description="备注说明")
    config_content: Optional[str] = Field(None, description="YAML配置内容")


class ConfigTemplateResponse(BaseModel):
    """配置模板响应"""
    id: str = Field(..., description="模板ID")
    name: str = Field(..., description="模板名称")
    namespace: Optional[str] = Field(None, description="适用命名空间")
    note: Optional[str] = Field(None, description="备注说明")
    config_content: str = Field(..., description="YAML配置内容")
    version: str = Field(..., description="版本号")
    sys_create_datetime: Optional[datetime] = Field(None, description="创建时间")
    sys_update_datetime: Optional[datetime] = Field(None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class DeployRequest(BaseModel):
    """下发配置请求"""
    template_id: str = Field(..., description="配置模板ID")
    machine_ids: List[str] = Field(..., description="目标机器ID列表")


class DeployDetail(BaseModel):
    """下发详情"""
    machine_id: str = Field(..., description="机器ID")
    ip: str = Field(..., description="IP地址")
    status: str = Field(..., description="状态: success/failed")
    error_message: Optional[str] = Field(None, description="错误信息")


class DeployResponse(BaseModel):
    """下发响应"""
    success_count: int = Field(..., description="成功数量")
    failed_count: int = Field(..., description="失败数量")
    details: List[DeployDetail] = Field(default_factory=list, description="下发详情")


class ConfigPreviewMachine(BaseModel):
    """配置预览机器"""
    id: str = Field(..., description="机器ID")
    ip: str = Field(..., description="IP地址")
    namespace: str = Field(..., description="命名空间")
    device_type: str = Field(..., description="设备类型")
    status: str = Field(..., description="机器状态")
    config_status: str = Field(..., description="配置状态: synced/pending/updating/offline")
    config_version: Optional[str] = Field(None, description="当前配置版本")


class ConfigPreviewResponse(BaseModel):
    """配置预览响应"""
    template_version: str = Field(..., description="模板版本")
    deployable_count: int = Field(..., description="可下发数量")
    updating_count: int = Field(..., description="更新中数量")
    offline_count: int = Field(..., description="离线数量")
    machines: List[ConfigPreviewMachine] = Field(default_factory=list, description="机器列表")
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/config_template/schema.py
git commit -m "feat: 新增配置模板 Schema 定义"
```

---

## Task 3: 后端 - 配置模板 Service

**Files:**
- Create: `backend-fastapi/core/config_template/service.py`

- [ ] **Step 1: 创建 Service 层**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2026-04-15
@File: service.py
@Desc: ConfigTemplate Service - 配置模板服务层
"""
import httpx
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_service import BaseService
from core.config_template.model import ConfigTemplate
from core.config_template.schema import (
    ConfigTemplateCreate,
    ConfigTemplateUpdate,
    ConfigPreviewMachine,
    DeployDetail,
)
from core.env_machine.model import EnvMachine
from core.env_machine.service import EnvMachineService


class ConfigTemplateService(BaseService[ConfigTemplate, ConfigTemplateCreate, ConfigTemplateUpdate]):
    """配置模板服务层"""

    model = ConfigTemplate

    @classmethod
    def _generate_version(cls) -> str:
        """生成版本号 YYYYMMDD-HHMMSS"""
        return datetime.now().strftime("%Y%m%d-%H%M%S")

    @classmethod
    async def create_with_version(
        cls,
        db: AsyncSession,
        data: ConfigTemplateCreate,
        auto_commit: bool = True
    ) -> ConfigTemplate:
        """创建模板并自动生成版本号"""
        version = cls._generate_version()
        template = ConfigTemplate(
            name=data.name,
            namespace=data.namespace,
            note=data.note,
            config_content=data.config_content,
            version=version,
        )
        db.add(template)
        if auto_commit:
            await db.commit()
            await db.refresh(template)
        else:
            await db.flush()
            await db.refresh(template)
        return template

    @classmethod
    async def update_with_version(
        cls,
        db: AsyncSession,
        template_id: str,
        data: ConfigTemplateUpdate,
        auto_commit: bool = True
    ) -> Optional[ConfigTemplate]:
        """更新模板并自动生成新版本号"""
        template = await cls.get_by_id(db, template_id)
        if not template:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(template, key, value)

        # 生成新版本号
        template.version = cls._generate_version()

        if auto_commit:
            await db.commit()
            await db.refresh(template)
        else:
            await db.flush()
            await db.refresh(template)
        return template

    @classmethod
    async def get_all(cls, db: AsyncSession) -> List[ConfigTemplate]:
        """获取所有模板（排除已删除）"""
        result = await db.execute(
            select(ConfigTemplate)
            .where(ConfigTemplate.is_deleted == False)
            .order_by(ConfigTemplate.sys_create_datetime.desc())
        )
        return result.scalars().all()

    @classmethod
    async def check_name_unique(
        cls,
        db: AsyncSession,
        name: str,
        exclude_id: Optional[str] = None
    ) -> bool:
        """检查名称是否唯一"""
        query = select(ConfigTemplate).where(
            ConfigTemplate.name == name,
            ConfigTemplate.is_deleted == False
        )
        if exclude_id:
            query = query.where(ConfigTemplate.id != exclude_id)
        result = await db.execute(query)
        return result.scalar_one_or_none() is None

    @classmethod
    async def get_preview(
        cls,
        db: AsyncSession,
        template_id: str,
        namespace: Optional[str] = None,
        device_type: Optional[str] = None,
        ip: Optional[str] = None
    ) -> Tuple[str, int, int, int, List[ConfigPreviewMachine]]:
        """获取配置下发预览"""
        # 获取模板版本
        template = await cls.get_by_id(db, template_id)
        if not template:
            raise ValueError("模板不存在")
        template_version = template.version

        # 构建查询条件
        VALID_NAMESPACES = ['meeting_gamma', 'meeting_app', 'meeting_av', 'meeting_public']
        filters = [EnvMachine.is_deleted == False]
        
        if namespace:
            filters.append(EnvMachine.namespace == namespace)
        else:
            filters.append(EnvMachine.namespace.in_(VALID_NAMESPACES))

        if device_type:
            filters.append(EnvMachine.device_type == device_type)

        if ip:
            escaped_ip = ip.replace("%", r"\%").replace("_", r"\_")
            filters.append(EnvMachine.ip.ilike(f"%{escaped_ip}%"))

        # 查询机器
        result = await db.execute(
            select(EnvMachine).where(*filters).order_by(EnvMachine.ip)
        )
        machines = result.scalars().all()

        # 计算配置状态
        preview_machines = []
        deployable_count = 0
        updating_count = 0
        offline_count = 0

        for m in machines:
            # 判断配置状态
            if m.status == "offline":
                config_status = "offline"
                offline_count += 1
            elif m.status == "config_updating":
                config_status = "updating"
                updating_count += 1
            elif m.config_version == template_version:
                config_status = "synced"
                deployable_count += 1
            else:
                config_status = "pending"
                deployable_count += 1

            preview_machines.append(ConfigPreviewMachine(
                id=m.id,
                ip=m.ip,
                namespace=m.namespace,
                device_type=m.device_type,
                status=m.status,
                config_status=config_status,
                config_version=m.config_version,
            ))

        return template_version, deployable_count, updating_count, offline_count, preview_machines

    @classmethod
    async def deploy_config(
        cls,
        db: AsyncSession,
        template_id: str,
        machine_ids: List[str]
    ) -> Tuple[int, int, List[DeployDetail]]:
        """下发配置到机器"""
        template = await cls.get_by_id(db, template_id)
        if not template:
            raise ValueError("模板不存在")

        success_count = 0
        failed_count = 0
        details = []

        for machine_id in machine_ids:
            machine = await EnvMachineService.get_by_id(db, machine_id)
            if not machine:
                details.append(DeployDetail(
                    machine_id=machine_id,
                    ip="unknown",
                    status="failed",
                    error_message="机器不存在"
                ))
                failed_count += 1
                continue

            # 检查机器状态
            if machine.status not in ("online", "using"):
                details.append(DeployDetail(
                    machine_id=machine_id,
                    ip=machine.ip,
                    status="failed",
                    error_message="机器离线或更新中"
                ))
                failed_count += 1
                continue

            # 调用 Worker 配置接口
            try:
                url = f"http://{machine.ip}:{machine.port}/worker/config"
                async with httpx.AsyncClient(timeout=30.0, trust_env=True, verify=False) as client:
                    resp = await client.post(url, json={
                        "config_content": template.config_content,
                        "config_version": template.version,
                    })
                    if resp.status_code == 200:
                        # 更新机器状态为配置更新中
                        machine.status = "config_updating"
                        success_count += 1
                        details.append(DeployDetail(
                            machine_id=machine_id,
                            ip=machine.ip,
                            status="success",
                            error_message=None
                        ))
                    else:
                        details.append(DeployDetail(
                            machine_id=machine_id,
                            ip=machine.ip,
                            status="failed",
                            error_message=f"Worker返回错误: {resp.status_code}"
                        ))
                        failed_count += 1
            except httpx.TimeoutException:
                details.append(DeployDetail(
                    machine_id=machine_id,
                    ip=machine.ip,
                    status="failed",
                    error_message="连接超时"
                ))
                failed_count += 1
            except httpx.ConnectError:
                details.append(DeployDetail(
                    machine_id=machine_id,
                    ip=machine.ip,
                    status="failed",
                    error_message="无法连接"
                ))
                failed_count += 1
            except Exception as e:
                details.append(DeployDetail(
                    machine_id=machine_id,
                    ip=machine.ip,
                    status="failed",
                    error_message=str(e)
                ))
                failed_count += 1

        if success_count > 0:
            await db.commit()

        return success_count, failed_count, details
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/config_template/service.py
git commit -m "feat: 新增配置模板 Service 层"
```

---

## Task 4: 后端 - 配置模板 API

**Files:**
- Create: `backend-fastapi/core/config_template/api.py`

- [ ] **Step 1: 创建 API 路由**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2026-04-15
@File: api.py
@Desc: ConfigTemplate API - 配置模板管理接口
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from core.config_template.schema import (
    ConfigTemplateCreate,
    ConfigTemplateUpdate,
    ConfigTemplateResponse,
    DeployRequest,
    DeployResponse,
    ConfigPreviewResponse,
)
from core.config_template.service import ConfigTemplateService

router = APIRouter(prefix="/config-template", tags=["配置模板管理"])


@router.get("", response_model=List[ConfigTemplateResponse], summary="获取模板列表")
async def get_template_list(
    db: AsyncSession = Depends(get_db)
) -> List[ConfigTemplateResponse]:
    """获取所有配置模板列表"""
    templates = await ConfigTemplateService.get_all(db)
    return [ConfigTemplateResponse.model_validate(t) for t in templates]


@router.get("/{template_id}", response_model=ConfigTemplateResponse, summary="获取模板详情")
async def get_template_detail(
    template_id: str,
    db: AsyncSession = Depends(get_db)
) -> ConfigTemplateResponse:
    """获取单个配置模板详情"""
    template = await ConfigTemplateService.get_by_id(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return ConfigTemplateResponse.model_validate(template)


@router.post("", response_model=ConfigTemplateResponse, summary="新建配置模板")
async def create_template(
    data: ConfigTemplateCreate,
    db: AsyncSession = Depends(get_db)
) -> ConfigTemplateResponse:
    """新建配置模板"""
    # 检查名称唯一性
    is_unique = await ConfigTemplateService.check_name_unique(db, data.name)
    if not is_unique:
        raise HTTPException(status_code=400, detail="模板名称已存在")

    template = await ConfigTemplateService.create_with_version(db, data)
    return ConfigTemplateResponse.model_validate(template)


@router.put("/{template_id}", response_model=ConfigTemplateResponse, summary="编辑配置模板")
async def update_template(
    template_id: str,
    data: ConfigTemplateUpdate,
    db: AsyncSession = Depends(get_db)
) -> ConfigTemplateResponse:
    """编辑配置模板"""
    # 检查名称唯一性（如果修改了名称）
    if data.name:
        is_unique = await ConfigTemplateService.check_name_unique(db, data.name, exclude_id=template_id)
        if not is_unique:
            raise HTTPException(status_code=400, detail="模板名称已存在")

    template = await ConfigTemplateService.update_with_version(db, template_id, data)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return ConfigTemplateResponse.model_validate(template)


@router.delete("/{template_id}", summary="删除配置模板")
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除配置模板（软删除）"""
    template = await ConfigTemplateService.get_by_id(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    await ConfigTemplateService.delete(db, template_id)
    await db.commit()
    return {"status": "success", "message": "删除成功"}


@router.get("/preview", response_model=ConfigPreviewResponse, summary="配置下发预览")
async def get_deploy_preview(
    template_id: str = Query(..., description="配置模板ID"),
    namespace: Optional[str] = Query(None, description="命名空间筛选"),
    device_type: Optional[str] = Query(None, description="设备类型筛选"),
    ip: Optional[str] = Query(None, description="IP模糊搜索"),
    db: AsyncSession = Depends(get_db)
) -> ConfigPreviewResponse:
    """获取配置下发预览（机器列表+配置状态）"""
    try:
        template_version, deployable, updating, offline, machines = \
            await ConfigTemplateService.get_preview(
                db, template_id, namespace, device_type, ip
            )
        return ConfigPreviewResponse(
            template_version=template_version,
            deployable_count=deployable,
            updating_count=updating,
            offline_count=offline,
            machines=machines,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/deploy", response_model=DeployResponse, summary="执行配置下发")
async def deploy_config(
    data: DeployRequest,
    db: AsyncSession = Depends(get_db)
) -> DeployResponse:
    """执行配置下发到目标机器"""
    try:
        success, failed, details = await ConfigTemplateService.deploy_config(
            db, data.template_id, data.machine_ids
        )
        return DeployResponse(
            success_count=success,
            failed_count=failed,
            details=details,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/config_template/api.py
git commit -m "feat: 新增配置模板 API 路由"
```

---

## Task 5: 后端 - 注册路由

**Files:**
- Modify: `backend-fastapi/core/router.py`

- [ ] **Step 1: 修改 router.py 注册路由**

在文件中添加导入和注册：

```python
# 在导入区添加
from core.config_template.api import router as config_template_router

# 在注册区添加（env_machine_router 附近）
router.include_router(config_template_router)
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/router.py
git commit -m "feat: 注册配置模板路由"
```

---

## Task 6: 后端 - EnvMachine 模型新增字段

**Files:**
- Modify: `backend-fastapi/core/env_machine/model.py`

- [ ] **Step 1: 添加 config_version 字段**

在 EnvMachine 类中添加字段：

```python
# 配置版本（新增）
config_version = Column(String(20), nullable=True, comment="配置版本")
```

同时修改 STATUS_DISPLAY 增加 config_updating 状态：

```python
STATUS_DISPLAY = {
    "online": "在线",
    "using": "使用中",
    "offline": "离线",
    "upgrading": "升级中",
    "config_updating": "配置更新中",  # 新增
}
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/env_machine/model.py
git commit -m "feat: EnvMachine 新增 config_version 字段"
```

---

## Task 7: 后端 - EnvMachine Schema 新增字段

**Files:**
- Modify: `backend-fastapi/core/env_machine/schema.py`

- [ ] **Step 1: EnvRegisterRequest 新增 config_version**

```python
class EnvRegisterRequest(BaseModel):
    """执行机注册请求 Schema"""
    ip: str = Field(..., description="机器IP")
    port: str = Field(..., description="机器端口")
    namespace: str = Field(..., description="机器分类")
    version: Optional[str] = Field(None, description="机器版本")
    config_version: Optional[str] = Field(None, description="配置版本")  # 新增
    devices: Dict[str, List[str]] = Field(..., description="设备列表")
```

- [ ] **Step 2: EnvMachineResponse 新增 config_version**

```python
class EnvMachineResponse(BaseModel):
    # ... 其他字段
    config_version: Optional[str] = Field(None, description="配置版本")  # 新增
```

- [ ] **Step 3: Commit**

```bash
git add backend-fastapi/core/env_machine/schema.py
git commit -m "feat: EnvMachine Schema 新增 config_version 字段"
```

---

## Task 8: 后端 - EnvMachine 注册接口修改

**Files:**
- Modify: `backend-fastapi/core/env_machine/api.py`

- [ ] **Step 1: 修改注册接口接收 config_version**

在 register_env_machine 函数中，更新 existing_machine 和 new_machine 时添加：

```python
# 存在则更新
if existing_machine:
    existing_machine.sync_time = now
    existing_machine.status = "online"
    existing_machine.port = data.port
    if data.version:
        existing_machine.version = data.version
    if data.config_version:  # 新增
        existing_machine.config_version = data.config_version

# 不存在则插入
new_machine = EnvMachine(
    namespace=data.namespace,
    ip=data.ip,
    port=data.port,
    device_type=device_type,
    device_sn=None,
    status="online",
    available=False,
    sync_time=now,
    version=data.version,
    config_version=data.config_version,  # 新增
)
```

同时在 Android/iOS 分支中也添加相同的处理。

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/env_machine/api.py
git commit -m "feat: 注册接口接收 config_version 字段"
```

---

## Task 9: 后端 - 数据库迁移

**Files:**
- Generate migration file

- [ ] **Step 1: 生成迁移文件**

```bash
cd backend-fastapi && alembic revision --autogenerate -m "add config_template table and config_version field"
```

- [ ] **Step 2: 执行迁移**

```bash
cd backend-fastapi && alembic upgrade head
```

- [ ] **Step 3: Commit**

```bash
git add backend-fastapi/alembic/versions/
git commit -m "feat: 数据库迁移 - 配置模板表和 config_version 字段"
```

---

## Task 10: 后端 - 菜单初始化脚本

**Files:**
- Create: `backend-fastapi/scripts/init_config_template_menu.py`

- [ ] **Step 1: 创建菜单初始化脚本**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
初始化配置管理菜单
执行方式: cd backend-fastapi && python scripts/init_config_template_menu.py
"""
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from core.menu.model import Menu


async def init_config_menu():
    """初始化配置管理菜单"""
    async with AsyncSessionLocal() as session:
        # 查找设备管理父菜单
        result = await session.execute(select(Menu).where(Menu.path == "/env-machine"))
        parent = result.scalar_one_or_none()

        if not parent:
            print("未找到设备管理父菜单")
            return

        # 检查是否已存在
        result = await session.execute(
            select(Menu).where(Menu.path == "/env-machine/config")
        )
        existing = result.scalar_one_or_none()

        if existing:
            print("配置管理菜单已存在，跳过")
            return

        # 创建配置管理子菜单
        menu = Menu(
            id="env-machine-config",
            name="EnvMachineConfig",
            title="配置管理",
            path="/env-machine/config",
            type="menu",
            component="/views/env-machine/config",
            icon="setting",
            parent_id=parent.id,
            order=150,
            sort=150,
        )
        session.add(menu)
        await session.commit()
        print("配置管理菜单创建成功！")


if __name__ == "__main__":
    asyncio.run(init_config_menu())
```

- [ ] **Step 2: 执行脚本**

```bash
cd backend-fastapi && python scripts/init_config_template_menu.py
```

- [ ] **Step 3: Commit**

```bash
git add backend-fastapi/scripts/init_config_template_menu.py
git commit -m "feat: 新增配置管理菜单初始化脚本"
```

---

## Task 11: 前端 - API 接口定义

**Files:**
- Create: `web/apps/web-ele/src/api/core/env-machine-config.ts`

- [ ] **Step 1: 创建 API 定义**

```typescript
import { requestClient } from '#/api/request';

/**
 * 配置模板
 */
export interface ConfigTemplate {
  id: string;
  name: string;
  namespace?: string;
  note?: string;
  config_content: string;
  version: string;
  sys_create_datetime?: string;
  sys_update_datetime?: string;
}

/**
 * 配置预览机器
 */
export interface ConfigPreviewMachine {
  id: string;
  ip: string;
  namespace: string;
  device_type: string;
  status: string;
  config_status: string;
  config_version?: string;
}

/**
 * 配置预览响应
 */
export interface ConfigPreviewResponse {
  template_version: string;
  deployable_count: number;
  updating_count: number;
  offline_count: number;
  machines: ConfigPreviewMachine[];
}

/**
 * 下发请求
 */
export interface DeployRequest {
  template_id: string;
  machine_ids: string[];
}

/**
 * 下发详情
 */
export interface DeployDetail {
  machine_id: string;
  ip: string;
  status: string;
  error_message?: string;
}

/**
 * 下发响应
 */
export interface DeployResponse {
  success_count: number;
  failed_count: number;
  details: DeployDetail[];
}

// API 函数

export async function getConfigTemplateListApi() {
  return requestClient.get<ConfigTemplate[]>('/api/core/config-template');
}

export async function getConfigTemplateDetailApi(id: string) {
  return requestClient.get<ConfigTemplate>(`/api/core/config-template/${id}`);
}

export async function createConfigTemplateApi(data: Partial<ConfigTemplate>) {
  return requestClient.post<ConfigTemplate>('/api/core/config-template', data);
}

export async function updateConfigTemplateApi(id: string, data: Partial<ConfigTemplate>) {
  return requestClient.put<ConfigTemplate>(`/api/core/config-template/${id}`, data);
}

export async function deleteConfigTemplateApi(id: string) {
  return requestClient.delete(`/api/core/config-template/${id}`);
}

export async function getConfigPreviewApi(
  templateId: string,
  namespace?: string,
  deviceType?: string,
  ip?: string
) {
  return requestClient.get<ConfigPreviewResponse>('/api/core/config-template/preview', {
    params: { template_id: templateId, namespace, device_type: deviceType, ip },
  });
}

export async function deployConfigApi(data: DeployRequest) {
  return requestClient.post<DeployResponse>('/api/core/config-template/deploy', data);
}
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/api/core/env-machine-config.ts
git commit -m "feat: 新增配置管理 API 接口定义"
```

---

## Task 12: 前端 - 路由配置

**Files:**
- Create: `web/apps/web-ele/src/router/routes/modules/env-machine-config.ts`

- [ ] **Step 1: 创建路由配置**

```typescript
import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/env-machine/config',
    name: 'EnvMachineConfig',
    component: () => import('#/views/env-machine/config.vue'),
    meta: {
      title: '配置管理',
      hideInMenu: true,
    },
  },
];

export default routes;
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/router/routes/modules/env-machine-config.ts
git commit -m "feat: 新增配置管理路由配置"
```

---

## Task 13: 前端 - 配置管理页面

**Files:**
- Create: `web/apps/web-ele/src/views/env-machine/config.vue`

- [ ] **Step 1: 创建配置管理页面**

页面代码较长，参考 upgrade.vue 的风格，实现：
- 左侧模板列表（新建、编辑、删除）
- 右侧下发区（筛选、预览、下发）

详见实际代码实现。

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/views/env-machine/config.vue
git commit -m "feat: 新增配置管理页面"
```

---

## Task 14: 验证与测试

- [ ] **Step 1: 启动后端服务验证**

```bash
cd backend-fastapi && python main.py
```

访问 http://localhost:8000/docs 验证 API 是否正常。

- [ ] **Step 2: 启动前端服务验证**

```bash
cd web && pnpm dev
```

访问配置管理页面验证功能。

- [ ] **Step 3: 最终 Commit**

```bash
git add -A
git commit -m "feat: 配置管理功能实现完成"
```