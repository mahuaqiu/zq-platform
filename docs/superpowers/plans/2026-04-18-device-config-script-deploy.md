# 设备配置页面支持脚本下发功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在配置管理页面新增脚本下发功能，支持 Windows PowerShell/Batch 和 Mac Shell 脚本下发到远程设备。

**Architecture:** 采用同一张表扩展方式，在 config_template 表新增 type 和 script_name 字段，复用现有下发流程架构。根据脚本扩展名自动识别目标系统并过滤设备。

**Tech Stack:** FastAPI + SQLAlchemy (后端), Vue 3 + Element Plus + Monaco Editor (前端)

---

## 文件结构

### 后端文件
| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `backend-fastapi/core/config_template/model.py` | 修改 | 新增 type、script_name 字段 |
| `backend-fastapi/core/config_template/schema.py` | 修改 | 新增 type、script_name 字段，新增校验 |
| `backend-fastapi/core/config_template/service.py` | 修改 | 新增脚本下发方法，修改预览过滤逻辑 |
| `backend-fastapi/core/config_template/api.py` | 修改 | 新增校验逻辑，修改路由标签 |
| `backend-fastapi/alembic/versions/xxx_add_script_fields.py` | 创建 | 数据库迁移脚本 |
| `backend-fastapi/scripts/update_config_template_menu.py` | 创建 | 更新菜单标题脚本 |

### 前端文件
| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `web/apps/web-ele/src/api/core/env-machine-config.ts` | 修改 | 新增 type、script_name 类型定义 |
| `web/apps/web-ele/src/views/env-machine/config.vue` | 修改 | 页面主体变更：弹窗、编辑器、列表、文案 |
| `web/apps/web-ele/src/router/routes/modules/env-machine-config.ts` | 修改 | 路由 meta title 更新 |
| `web/packages/package.json` | 修改 | 新增 monaco-editor 依赖 |

---

## Task 1: 后端数据库迁移

**Files:**
- Create: `backend-fastapi/alembic/versions/xxx_add_script_fields.py`

- [ ] **Step 1: 创建迁移脚本**

```bash
cd backend-fastapi && alembic revision -m "add_script_fields_to_config_template"
```

Expected: 创建新迁移文件

- [ ] **Step 2: 编辑迁移脚本**

在生成的迁移文件中写入：

```python
"""add script fields to config_template

Revision ID: xxx
Revises: xxx
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa


def upgrade():
    # 新增 type 字段，默认值为 'config'
    op.add_column('config_template',
        sa.Column('type', sa.String(20), nullable=False, server_default='config', comment='模板类型: config/script'))

    # 新增 script_name 字段
    op.add_column('config_template',
        sa.Column('script_name', sa.String(128), nullable=True, comment='脚本名称'))


def downgrade():
    op.drop_column('config_template', 'script_name')
    op.drop_column('config_template', 'type')
```

- [ ] **Step 3: 执行迁移**

```bash
cd backend-fastapi && alembic upgrade head
```

Expected: 数据库表新增两个字段

- [ ] **Step 4: 验证迁移**

```bash
cd backend-fastapi && python -c "from app.database import engine; import asyncio; from sqlalchemy import text; async def check(): async with engine.begin() as conn: result = await conn.execute(text('SELECT column_name FROM information_schema.columns WHERE table_name = \"config_template\"')); print([r[0] for r in result]); asyncio.run(check())"
```

Expected: 输出包含 'type' 和 'script_name'

- [ ] **Step 5: Commit**

```bash
git add backend-fastapi/alembic/versions/*add_script_fields*.py
git commit -m "feat(db): 新增 config_template 表 type 和 script_name 字段"
```

---

## Task 2: 后端 Model 变更

**Files:**
- Modify: `backend-fastapi/core/config_template/model.py`

- [ ] **Step 1: 修改 Model 定义**

```python
# 在 ConfigTemplate 类中新增字段

from sqlalchemy import Column, String, Text, Index

class ConfigTemplate(BaseModel):
    """
    配置模板表

    字段说明：
    - name: 模板名称（唯一）
    - type: 模板类型（config/script）
    - script_name: 脚本名称（仅脚本类型）
    - namespace: 适用命名空间（可选）
    - note: 备注说明
    - config_content: YAML 配置内容或脚本内容
    - version: 版本号（YYYYMMDD-HHMMSS）
    """
    __tablename__ = "config_template"

    # 模板名称（唯一）
    name = Column(String(64), nullable=False, unique=True, comment="模板名称")

    # 模板类型（config/script）
    type = Column(String(20), nullable=False, default="config", comment="模板类型")

    # 脚本名称（仅脚本类型使用）
    script_name = Column(String(128), nullable=True, comment="脚本名称")

    # 适用命名空间（可选）
    namespace = Column(String(64), nullable=True, comment="适用命名空间")

    # 备注说明
    note = Column(Text, nullable=True, comment="备注说明")

    # YAML 配置内容或脚本内容
    config_content = Column(Text, nullable=False, comment="配置内容")

    # 版本号（自动生成）
    version = Column(String(20), nullable=False, comment="版本号YYYYMMDD-HHMMSS")

    # 索引
    __table_args__ = (
        Index("ix_config_template_namespace", "namespace"),
        Index("ix_config_template_type", "type"),
    )
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/config_template/model.py
git commit -m "feat(model): ConfigTemplate 新增 type 和 script_name 字段"
```

---

## Task 3: 后端 Schema 变更

**Files:**
- Modify: `backend-fastapi/core/config_template/schema.py`

- [ ] **Step 1: 修改 ConfigTemplateCreate**

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator
import re

class ConfigTemplateCreate(BaseModel):
    """创建配置模板请求 Schema"""
    name: str = Field(..., max_length=64, description="模板名称")
    type: str = Field(default="config", description="模板类型: config/script")
    script_name: Optional[str] = Field(None, max_length=128, description="脚本名称")
    namespace: Optional[str] = Field(None, max_length=64, description="命名空间")
    note: Optional[str] = Field(None, description="备注")
    config_content: str = Field(..., description="配置内容")

    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ('config', 'script'):
            raise ValueError('模板类型必须是 config 或 script')
        return v

    @field_validator('script_name')
    @classmethod
    def validate_script_name(cls, v: Optional[str], info) -> Optional[str]:
        # 脚本类型时 script_name 必填
        if info.data.get('type') == 'script' and not v:
            raise ValueError('脚本类型必须填写脚本名称')

        # 校验扩展名
        if v:
            ext = v.lower().split('.')[-1] if '.' in v else ''
            if ext not in ('ps1', 'bat', 'sh'):
                raise ValueError('脚本扩展名必须是 .ps1, .bat 或 .sh')

        return v
```

- [ ] **Step 2: 修改 ConfigTemplateUpdate**

```python
class ConfigTemplateUpdate(BaseModel):
    """更新配置模板请求 Schema"""
    name: Optional[str] = Field(None, max_length=64, description="模板名称")
    type: Optional[str] = Field(None, description="模板类型")
    script_name: Optional[str] = Field(None, max_length=128, description="脚本名称")
    namespace: Optional[str] = Field(None, max_length=64, description="命名空间")
    note: Optional[str] = Field(None, description="备注")
    config_content: Optional[str] = Field(None, description="配置内容")

    @field_validator('type')
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ('config', 'script'):
            raise ValueError('模板类型必须是 config 或 script')
        return v
```

- [ ] **Step 3: 修改 ConfigTemplateResponse**

```python
class ConfigTemplateResponse(BaseModel):
    """配置模板响应 Schema"""
    id: str = Field(..., description="模板ID")
    name: str = Field(..., description="模板名称")
    type: str = Field(..., description="模板类型")
    script_name: Optional[str] = Field(None, description="脚本名称")
    namespace: Optional[str] = Field(None, description="命名空间")
    note: Optional[str] = Field(None, description="备注")
    config_content: str = Field(..., description="配置内容")
    version: str = Field(..., description="版本号")
    sys_create_datetime: Optional[datetime] = Field(None, description="创建时间")
    sys_update_datetime: Optional[datetime] = Field(None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 4: Commit**

```bash
git add backend-fastapi/core/config_template/schema.py
git commit -m "feat(schema): ConfigTemplate Schema 新增 type、script_name 字段和校验"
```

---

## Task 4: 后端 Service 变更 - 新增辅助方法

**Files:**
- Modify: `backend-fastapi/core/config_template/service.py`

- [ ] **Step 1: 新增目标系统识别方法**

在 ConfigTemplateService 类中新增：

```python
@staticmethod
def _get_target_os_from_extension(script_name: str) -> str:
    """
    根据脚本扩展名返回目标操作系统

    :param script_name: 脚本名称
    :return: 'windows' 或 'mac' 或 ''
    """
    if not script_name:
        return ''
    ext = script_name.lower().split('.')[-1] if '.' in script_name else ''
    if ext in ('ps1', 'bat'):
        return 'windows'
    elif ext == 'sh':
        return 'mac'
    return ''
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/config_template/service.py
git commit -m "feat(service): 新增 _get_target_os_from_extension 方法"
```

---

## Task 5: 后端 Service 变更 - 新增脚本下发方法

**Files:**
- Modify: `backend-fastapi/core/config_template/service.py`

- [ ] **Step 1: 新增脚本下发方法**

```python
@staticmethod
async def _send_script_to_worker(
    machine: EnvMachine,
    template: ConfigTemplate
) -> Tuple[bool, Optional[str], str]:
    """
    调用 Worker scripts 接口下发脚本

    :param machine: 机器对象
    :param template: 配置模板（脚本类型）
    :return: (是否成功, 错误信息, machine_id)
    """
    url = f"http://{machine.ip}:{machine.port}/worker/scripts"
    payload = {
        "name": template.script_name,
        "content": template.config_content,
        "version": template.version,
        "overwrite": True
    }

    try:
        async with httpx.AsyncClient(
            timeout=WORKER_CONFIG_TIMEOUT,
            trust_env=True,
            verify=False
        ) as client:
            response = await client.post(url, json=payload)

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return True, None, machine.id
                else:
                    return False, f"Worker 返回异常状态: {data.get('status')}", machine.id
            elif response.status_code == 409:
                return False, "脚本更新进行中或已存在", machine.id
            elif response.status_code == 503:
                return False, "Worker 未初始化", machine.id
            else:
                return False, f"Worker 返回错误状态码: {response.status_code}", machine.id

    except httpx.TimeoutException:
        return False, "Worker 响应超时", machine.id
    except httpx.ConnectError:
        return False, "无法连接到 Worker", machine.id
    except Exception as e:
        logger.error(f"调用 Worker scripts 接口失败: {e}")
        return False, f"网络错误: {str(e)}", machine.id
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/config_template/service.py
git commit -m "feat(service): 新增 _send_script_to_worker 方法"
```

---

## Task 6: 后端 Service 变更 - 修改 deploy_config 方法

**Files:**
- Modify: `backend-fastapi/core/config_template/service.py`

- [ ] **Step 1: 修改 deploy_config 方法**

找到 `deploy_config` 方法，修改下发调用部分：

```python
@classmethod
async def deploy_config(
    cls,
    db: AsyncSession,
    template_id: str,
    machine_ids: List[str],
) -> DeployResponse:
    """
    下发配置/脚本到机器

    :param db: 数据库会话
    :param template_id: 模板 ID
    :param machine_ids: 机器 ID 列表
    :return: 下发响应
    """
    # 获取模板
    template = await cls.get_by_id(db, template_id)
    if not template:
        raise ValueError(f"模板不存在: {template_id}")

    # 查询机器
    result = await db.execute(
        select(EnvMachine).where(
            and_(
                EnvMachine.id.in_(machine_ids),
                EnvMachine.is_deleted == False,  # noqa: E712
            )
        )
    )
    machines = result.scalars().all()

    response = DeployResponse(success_count=0, failed_count=0, details=[])

    # 收集并发任务
    deploy_tasks = []
    deploy_machine_map = {}

    for machine in machines:
        # 跳过离线机器
        if machine.status == "offline":
            response.failed_count += 1
            response.details.append(DeployDetail(
                machine_id=machine.id,
                ip=machine.ip,
                status="failed",
                error_message="机器离线"
            ))
            continue

        # 跳过正在更新配置的机器
        if hasattr(machine, 'config_status') and machine.config_status == "updating":
            response.failed_count += 1
            response.details.append(DeployDetail(
                machine_id=machine.id,
                ip=machine.ip,
                status="failed",
                error_message="配置正在更新中"
            ))
            continue

        # 脚本类型：校验设备类型匹配
        if template.type == 'script':
            target_os = cls._get_target_os_from_extension(template.script_name)
            if target_os == 'windows' and machine.device_type != 'windows':
                response.failed_count += 1
                response.details.append(DeployDetail(
                    machine_id=machine.id,
                    ip=machine.ip,
                    status="failed",
                    error_message="脚本仅支持 Windows 设备"
                ))
                continue
            elif target_os == 'mac' and machine.device_type != 'mac':
                response.failed_count += 1
                response.details.append(DeployDetail(
                    machine_id=machine.id,
                    ip=machine.ip,
                    status="failed",
                    error_message="脚本仅支持 Mac 设备"
                ))
                continue

        # 收集并发任务 - 根据 type 选择不同的下发方法
        if template.type == 'script':
            deploy_tasks.append(cls._send_script_to_worker(machine, template))
        else:
            deploy_tasks.append(cls._send_config_to_worker(machine, template))
        deploy_machine_map[machine.id] = machine

    # 并发下发
    if deploy_tasks:
        logger.info(f"并发下发到 {len(deploy_tasks)} 台机器，类型: {template.type}")
        results = await asyncio.gather(*deploy_tasks, return_exceptions=True)

        # 处理结果
        for task_result in results:
            if isinstance(task_result, Exception):
                logger.error(f"并发任务异常: {task_result}")
                response.failed_count += 1
                continue

            success, error_message, machine_id = task_result
            machine = deploy_machine_map[machine_id]

            if success:
                # 更新机器状态
                if hasattr(machine, 'config_status'):
                    machine.config_status = "updating"
                if hasattr(machine, 'config_version'):
                    machine.config_version = template.version

                response.success_count += 1
                response.details.append(DeployDetail(
                    machine_id=machine.id,
                    ip=machine.ip,
                    status="success",
                    error_message=None
                ))
            else:
                response.failed_count += 1
                response.details.append(DeployDetail(
                    machine_id=machine.id,
                    ip=machine.ip,
                    status="failed",
                    error_message=error_message
                ))

    await db.commit()
    return response
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/config_template/service.py
git commit -m "feat(service): deploy_config 支持脚本类型下发"
```

---

## Task 7: 后端 Service 变更 - 修改 get_preview 方法

**Files:**
- Modify: `backend-fastapi/core/config_template/service.py`

- [ ] **Step 1: 修改 get_preview 方法**

在查询条件构建部分添加脚本类型过滤：

```python
@classmethod
async def get_preview(
    cls,
    db: AsyncSession,
    template_id: str,
    namespace: Optional[str] = None,
    device_type: Optional[str] = None,
    machine_ids: Optional[List[str]] = None
) -> ConfigPreviewResponse:
    """
    获取配置下发预览

    :param db: 数据库会话
    :param template_id: 模板 ID
    :param namespace: 可选，按命名空间筛选
    :param device_type: 可选，按设备类型筛选
    :param machine_ids: 可选，指定机器 ID 列表
    :return: 配置预览响应
    """
    # 获取模板
    template = await cls.get_by_id(db, template_id)
    if not template:
        raise ValueError(f"模板不存在: {template_id}")

    template_version = template.version

    # 构建查询条件
    conditions = [
        EnvMachine.is_deleted == False,  # noqa: E712
    ]

    # 命名空间筛选
    if namespace:
        conditions.append(EnvMachine.namespace == namespace)
    else:
        conditions.append(EnvMachine.namespace.in_(VALID_NAMESPACE_LIST))

    # 设备类型筛选
    # 脚本类型：根据扩展名自动过滤设备类型，忽略前端传入的 device_type
    if template.type == 'script':
        target_os = cls._get_target_os_from_extension(template.script_name)
        if target_os:
            conditions.append(EnvMachine.device_type == target_os)
    elif device_type:
        # 配置类型：使用前端传入的筛选条件
        conditions.append(EnvMachine.device_type == device_type)

    # 指定机器 ID
    if machine_ids:
        conditions.append(EnvMachine.id.in_(machine_ids))

    # 查询机器
    result = await db.execute(select(EnvMachine).where(and_(*conditions)))
    machines = result.scalars().all()

    # ... 后续统计逻辑保持不变
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/config_template/service.py
git commit -m "feat(service): get_preview 支持脚本类型自动过滤设备"
```

---

## Task 8: 后端 API 变更

**Files:**
- Modify: `backend-fastapi/core/config_template/api.py`

- [ ] **Step 1: 修改路由标签**

```python
router = APIRouter(prefix="/config-template", tags=["设备配置管理"])
```

- [ ] **Step 2: 新建模板增加校验**

在 create_config_template 函数中增加扩展名校验：

```python
@router.post("", response_model=ConfigTemplateResponse, summary="新建配置模板")
async def create_config_template(
    data: ConfigTemplateCreate,
    db: AsyncSession = Depends(get_db)
) -> ConfigTemplateResponse:
    """
    新建配置模板

    自动生成版本号（YYYYMMDD-HHMMSS）。

    注意：模板名称必须唯一。
    """
    # 检查名称唯一性
    is_unique = await ConfigTemplateService.check_name_unique(db, data.name)
    if not is_unique:
        raise HTTPException(status_code=400, detail="模板名称已存在")

    # 脚本类型校验（Schema 已处理，这里可以添加额外检查）
    if data.type == 'script' and data.script_name:
        ext = data.script_name.lower().split('.')[-1] if '.' in data.script_name else ''
        if ext not in ('ps1', 'bat', 'sh'):
            raise HTTPException(status_code=400, detail="脚本扩展名必须是 .ps1, .bat 或 .sh")

    try:
        template = await ConfigTemplateService.create_with_version(db, data)
        logger.info(f"创建配置模板成功: id={template.id}, name={template.name}, type={template.type}")
        return ConfigTemplateResponse.model_validate(template)
    except Exception as e:
        await db.rollback()
        logger.error(f"创建配置模板失败: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")
```

- [ ] **Step 3: 更新模板增加校验**

```python
@router.put("/{template_id}", response_model=ConfigTemplateResponse, summary="编辑配置模板")
async def update_config_template(
    template_id: str,
    data: ConfigTemplateUpdate,
    db: AsyncSession = Depends(get_db)
) -> ConfigTemplateResponse:
    """
    编辑配置模板

    更新模板信息并自动生成新版本号。
    """
    template = await ConfigTemplateService.get_by_id(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 如果修改了名称，检查唯一性
    if data.name and data.name != template.name:
        is_unique = await ConfigTemplateService.check_name_unique(
            db, data.name, exclude_id=template_id
        )
        if not is_unique:
            raise HTTPException(status_code=400, detail="模板名称已存在")

    # 脚本类型校验
    if data.type == 'script' and data.script_name:
        ext = data.script_name.lower().split('.')[-1] if '.' in data.script_name else ''
        if ext not in ('ps1', 'bat', 'sh'):
            raise HTTPException(status_code=400, detail="脚本扩展名必须是 .ps1, .bat 或 .sh")

    try:
        updated_template = await ConfigTemplateService.update_with_version(
            db, template_id, data
        )
        logger.info(f"更新配置模板成功: id={template_id}")
        return ConfigTemplateResponse.model_validate(updated_template)
    except Exception as e:
        await db.rollback()
        logger.error(f"更新配置模板失败: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")
```

- [ ] **Step 4: Commit**

```bash
git add backend-fastapi/core/config_template/api.py
git commit -m "feat(api): 设备配置管理 API 新增脚本类型校验"
```

---

## Task 9: 更新菜单标题

**Files:**
- Create: `backend-fastapi/scripts/update_config_template_menu.py`

- [ ] **Step 1: 创建菜单更新脚本**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新配置管理菜单标题为"设备配置"
执行方式: cd backend-fastapi && python scripts/update_config_template_menu.py
"""
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from core.menu.model import Menu


async def update_menu_title():
    async with AsyncSessionLocal() as session:
        # 查找配置管理菜单
        result = await session.execute(
            select(Menu).where(Menu.id == "env-machine-config")
        )
        menu = result.scalar_one_or_none()

        if not menu:
            print("[错误] 未找到配置管理菜单 (env-machine-config)")
            return

        # 更新标题
        menu.title = "设备配置"
        await session.commit()
        print("[OK] 菜单标题已更新为 '设备配置'")


if __name__ == "__main__":
    asyncio.run(update_menu_title())
```

- [ ] **Step 2: 执行脚本**

```bash
cd backend-fastapi && python scripts/update_config_template_menu.py
```

Expected: 输出 "[OK] 菜单标题已更新为 '设备配置'"

- [ ] **Step 3: Commit**

```bash
git add backend-fastapi/scripts/update_config_template_menu.py
git commit -m "feat(scripts): 新增菜单标题更新脚本"
```

---

## Task 10: 前端 TypeScript 类型定义变更

**Files:**
- Modify: `web/apps/web-ele/src/api/core/env-machine-config.ts`

- [ ] **Step 1: 修改 ConfigTemplate 类型定义**

```typescript
/**
 * 配置模板
 */
export interface ConfigTemplate {
  id: string;
  name: string;
  type: 'config' | 'script';  // 新增：模板类型
  script_name?: string;       // 新增：脚本名称
  namespace?: string;
  note?: string;
  config_content: string;
  version: string;
  sys_create_datetime?: string;
  sys_update_datetime?: string;
}
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/api/core/env-machine-config.ts
git commit -m "feat(api): ConfigTemplate 类型新增 type 和 script_name"
```

---

## Task 11: 前端路由 meta title 更新

**Files:**
- Modify: `web/apps/web-ele/src/router/routes/modules/env-machine-config.ts`

- [ ] **Step 1: 修改路由 meta**

```typescript
import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/env-machine/config',
    name: 'EnvMachineConfig',
    component: () => import('#/views/env-machine/config.vue'),
    meta: {
      title: '设备配置',  // 从 '配置管理' 改为 '设备配置'
      hideInMenu: true,
    },
  },
];

export default routes;
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/router/routes/modules/env-machine-config.ts
git commit -m "feat(router): 路由标题更新为 '设备配置'"
```

---

## Task 12: 前端页面变更 - 文案调整和模板类型选择

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/config.vue`

- [ ] **Step 1: 修改左侧面板标题**

找到 `panel-title` 部分，修改文案：

```vue
<!-- 左侧：模板列表 -->
<div class="template-panel">
  <div class="panel-header">
    <span class="panel-title">📝 下发列表</span>  <!-- 从 "配置模板" 改为 "下发列表" -->
    <ElButton type="primary" size="small" @click="handleCreateTemplate">新建</ElButton>
  </div>
```

- [ ] **Step 2: 修改弹窗标题**

找到 `templateDialogTitle` 的赋值部分：

```typescript
// 新建模板
function handleCreateTemplate() {
  templateDialogTitle.value = '新建模板';  // 从 "新建配置模板" 改为 "新建模板"
  templateForm.value = {
    name: '',
    type: 'config',  // 新增：默认类型为 config
    script_name: '',  // 新增：脚本名称
    namespace: '',
    config_content: '',
    note: '',
  };
  templateDialogVisible.value = true;
}

// 编辑模板
function handleEditTemplate(template: ConfigTemplate) {
  templateDialogTitle.value = '编辑模板';  // 从 "编辑配置模板" 改为 "编辑模板"
  templateForm.value = {
    name: template.name,
    type: template.type || 'config',  // 新增
    script_name: template.script_name || '',  // 新增
    namespace: template.namespace || '',
    config_content: template.config_content,
    note: template.note || '',
  };
  selectedTemplate.value = template;
  templateDialogVisible.value = true;
}
```

- [ ] **Step 3: 修改 templateForm 类型定义**

```typescript
const templateForm = ref({
  name: '',
  type: 'config' as 'config' | 'script',  // 新增
  script_name: '',  // 新增
  namespace: '',
  config_content: '',
  note: '',
});
```

- [ ] **Step 4: 修改保存模板逻辑**

```typescript
async function handleSaveTemplate() {
  if (!templateForm.value.name.trim()) {
    ElMessage.warning('请输入模板名称');
    return;
  }

  // 脚本类型校验
  if (templateForm.value.type === 'script') {
    if (!templateForm.value.script_name.trim()) {
      ElMessage.warning('请输入脚本名称');
      return;
    }
    const ext = templateForm.value.script_name.toLowerCase().split('.').pop();
    if (ext && !['ps1', 'bat', 'sh'].includes(ext)) {
      ElMessage.warning('脚本扩展名必须是 .ps1, .bat 或 .sh');
      return;
    }
  }

  if (!templateForm.value.config_content.trim()) {
    ElMessage.warning('请输入配置内容');
    return;
  }

  templateFormLoading.value = true;
  try {
    if (templateDialogTitle.value === '新建模板') {
      await createConfigTemplateApi({
        name: templateForm.value.name,
        type: templateForm.value.type,
        script_name: templateForm.value.type === 'script' ? templateForm.value.script_name : undefined,
        namespace: templateForm.value.namespace || undefined,
        config_content: templateForm.value.config_content,
        note: templateForm.value.note,
      });
      ElMessage.success('创建成功');
    } else {
      if (selectedTemplate.value) {
        await updateConfigTemplateApi(selectedTemplate.value.id, {
          name: templateForm.value.name,
          type: templateForm.value.type,
          script_name: templateForm.value.type === 'script' ? templateForm.value.script_name : undefined,
          namespace: templateForm.value.namespace || undefined,
          config_content: templateForm.value.config_content,
          note: templateForm.value.note,
        });
        ElMessage.success('更新成功');
      }
    }
    templateDialogVisible.value = false;
    await loadTemplates();
  } catch (error) {
    ElMessage.error(templateDialogTitle.value === '新建模板' ? '创建失败' : '更新失败');
  } finally {
    templateFormLoading.value = false;
  }
}
```

- [ ] **Step 5: Commit**

```bash
git add web/apps/web-ele/src/views/env-machine/config.vue
git commit -m "feat(ui): 页面文案调整和模板类型字段新增"
```

---

## Task 13: 前端页面变更 - 弹窗新增模板类型和脚本名称输入

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/config.vue`

- [ ] **Step 1: 弹窗新增模板类型选择和脚本名称输入**

在 `template-dialog-body` 的基本信息部分新增：

```vue
<!-- 弹窗内容 -->
<div class="template-dialog-body">
  <!-- 基本信息 -->
  <div class="form-section">
    <div class="section-title">基本信息</div>
    <div class="section-content">
      <div class="form-row">
        <div class="form-col">
          <label class="form-label">模板名称 <span class="required">*</span></label>
          <ElInput v-model="templateForm.name" placeholder="如：默认配置模板" />
        </div>
        <div class="form-col">
          <label class="form-label">模板类型 <span class="required">*</span></label>
          <ElSelect v-model="templateForm.type" style="width: 100%">
            <ElOption label="配置" value="config" />
            <ElOption label="脚本内容" value="script" />
          </ElSelect>
        </div>
      </div>

      <!-- 脚本名称：仅脚本类型显示 -->
      <div v-if="templateForm.type === 'script'" class="form-row">
        <div class="form-col-full">
          <label class="form-label">脚本名称 <span class="required">*</span></label>
          <ElInput
            v-model="templateForm.script_name"
            placeholder="如 play_ppt.ps1，扩展名仅支持 .ps1/.bat/.sh"
          />
        </div>
      </div>

      <div class="form-row">
        <div class="form-col">
          <label class="form-label">适用命名空间</label>
          <ElSelect v-model="templateForm.namespace" placeholder="全部命名空间" clearable style="width: 100%">
            <ElOption v-for="opt in NAMESPACE_OPTIONS_DIALOG" :key="opt.value" :label="opt.label" :value="opt.value" />
          </ElSelect>
        </div>
        <div class="form-col">
          <label class="form-label">备注说明</label>
          <ElInput v-model="templateForm.note" placeholder="模板用途说明" />
        </div>
      </div>
    </div>
  </div>

  <!-- 配置内容/脚本内容 -->
  <div class="form-section">
    <div class="section-title">
      {{ templateForm.type === 'config' ? '配置内容 (YAML)' : '脚本内容' }}
    </div>
    <div class="section-content">
      <!-- 编辑器部分（后续 Task 替换为 Monaco Editor） -->
      <textarea
        v-model="templateForm.config_content"
        class="yaml-textarea"
        :placeholder="templateForm.type === 'config' ? '在此编辑 YAML 配置文件...' : '在此编辑脚本内容...'"
        rows="18"
      ></textarea>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/views/env-machine/config.vue
git commit -m "feat(ui): 弹窗新增模板类型选择和脚本名称输入"
```

---

## Task 14: 前端页面变更 - 左侧列表显示脚本信息

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/config.vue`

- [ ] **Step 1: 新增目标系统识别函数**

```typescript
// 根据脚本扩展名获取目标系统显示
function getTargetOsDisplay(scriptName: string): string {
  if (!scriptName) return '';
  const ext = scriptName.toLowerCase().split('.').pop();
  if (ext === 'ps1' || ext === 'bat') return 'Windows';
  if (ext === 'sh') return 'Mac';
  return '';
}
```

- [ ] **Step 2: 修改模板列表项显示**

```vue
<div v-else class="template-list">
  <div
    v-for="item in templateList"
    :key="item.id"
    :class="['template-item', { active: selectedTemplate?.id === item.id }]"
    @click="handleSelectTemplate(item)"
  >
    <div class="template-info">
      <div class="template-name">{{ item.name }}</div>
      <div class="template-meta">适用：{{ getTemplateNamespaceDisplay(item.namespace) }}</div>

      <!-- 脚本类型：显示脚本名称和目标系统 -->
      <div v-if="item.type === 'script'" class="template-script-info">
        <span class="script-name">{{ item.script_name }}</span>
        <span class="script-os">{{ getTargetOsDisplay(item.script_name || '') }}</span>
      </div>

      <div class="template-version">版本：{{ item.version }}</div>
    </div>
    <div class="template-actions">
      <a class="action-link" @click.stop="handleEditTemplate(item)">编辑</a>
      <a class="action-link danger" @click.stop="handleDeleteTemplate(item)">删除</a>
    </div>
  </div>
</div>
```

- [ ] **Step 3: 新增样式**

```css
.template-script-info {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 12px;
}

.script-name {
  color: #1890ff;
}

.script-os {
  color: #666;
}
```

- [ ] **Step 4: Commit**

```bash
git add web/apps/web-ele/src/views/env-machine/config.vue
git commit -m "feat(ui): 左侧列表显示脚本名称和目标系统"
```

---

## Task 15: 前端页面变更 - 右侧列表文案调整

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/config.vue`

- [ ] **Step 1: 修改统计信息文案**

```vue
<!-- 统计信息 -->
<div v-if="previewData" class="stats-row">
  <span class="stats-item stats-deployable"><strong>可下发:</strong> {{ previewData.deployable_count }}台</span>
  <span class="stats-item stats-updating"><strong>下发更新中:</strong> {{ previewData.updating_count }}台</span>  <!-- 从 "配置更新中" 改为 "下发更新中" -->
  <span class="stats-item stats-offline"><strong>离线:</strong> {{ previewData.offline_count }}台</span>
</div>
```

- [ ] **Step 2: 修改表格列标题**

```vue
<ElTableColumn prop="config_status" label="下发状态" min-width="100">  <!-- 从 "配置状态" 改为 "下发状态" -->
  <template #default="{ row }">
    <span
      class="status-tag"
      :style="{
        background: getConfigStatusStyle(row.config_status).bg,
        color: getConfigStatusStyle(row.config_status).color
      }"
    >
      {{ getConfigStatusText(row.config_status) }}
    </span>
  </template>
</ElTableColumn>
```

- [ ] **Step 3: Commit**

```bash
git add web/apps/web-ele/src/views/env-machine/config.vue
git commit -m "feat(ui): 右侧列表文案调整为 '下发更新中' 和 '下发状态'"
```

---

## Task 16: 前端页面变更 - 设备类型筛选联动

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/config.vue`

- [ ] **Step 1: 新增计算属性判断是否禁用设备类型筛选**

```typescript
// 脚本类型模板：禁用设备类型筛选（已自动过滤）
const isDeviceTypeFilterDisabled = computed(() => {
  return selectedTemplate.value?.type === 'script';
});

// 脚本类型模板：显示当前筛选的目标系统
const deviceTypeFilterHint = computed(() => {
  if (selectedTemplate.value?.type === 'script' && selectedTemplate.value?.script_name) {
    const targetOs = getTargetOsDisplay(selectedTemplate.value.script_name);
    return `已自动筛选 ${targetOs} 设备`;
  }
  return '';
});
```

- [ ] **Step 2: 修改设备类型筛选下拉框**

```vue
<div class="filter-item">
  <label class="filter-label">设备类型:</label>
  <ElSelect
    v-model="filterForm.device_type"
    style="width: 100px"
    :disabled="isDeviceTypeFilterDisabled"
  >
    <ElOption v-for="opt in DEVICE_TYPE_FILTER_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
  </ElSelect>
  <span v-if="deviceTypeFilterHint" class="filter-hint">{{ deviceTypeFilterHint }}</span>
</div>
```

- [ ] **Step 3: 新增样式**

```css
.filter-hint {
  font-size: 12px;
  color: #faad14;
  margin-left: 8px;
}
```

- [ ] **Step 4: Commit**

```bash
git add web/apps/web-ele/src/views/env-machine/config.vue
git commit -m "feat(ui): 脚本类型自动禁用设备类型筛选"
```

---

## Task 17: Monaco Editor 集成 - 安装依赖

**Files:**
- Modify: `web/packages/package.json`

- [ ] **Step 1: 安装 Monaco Editor**

```bash
cd web && pnpm add monaco-editor
```

Expected: 安装成功

- [ ] **Step 2: Commit**

```bash
git add web/packages/package.json web/packages/pnpm-lock.yaml
git commit -m "feat(deps): 新增 monaco-editor 依赖"
```

---

## Task 18: Monaco Editor 集成 - 编辑器组件

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/config.vue`

- [ ] **Step 1: 导入 Monaco Editor**

```typescript
import * as monaco from 'monaco-editor';
import { onMounted, ref, watch, nextTick } from 'vue';
```

- [ ] **Step 2: 新增编辑器相关状态**

```typescript
// Monaco Editor 实例
const editorInstance = ref<monaco.editor.IStandaloneCodeEditor | null>(null);
const editorContainerRef = ref<HTMLElement | null>(null);

// 根据模板类型和脚本名称获取编辑器语言
function getEditorLanguage(): string {
  if (templateForm.value.type === 'config') {
    return 'yaml';
  }
  // 脚本类型：根据扩展名选择语言
  const scriptName = templateForm.value.script_name || '';
  const ext = scriptName.toLowerCase().split('.').pop();
  if (ext === 'ps1') return 'powershell';
  if (ext === 'bat') return 'bat';  // Monaco 不直接支持 bat，用 basic 替代
  if (ext === 'sh') return 'shell';
  return 'plaintext';
}
```

- [ ] **Step 3: 新增编辑器初始化和销毁逻辑**

```typescript
// 初始化 Monaco Editor
function initEditor() {
  if (!editorContainerRef.value) return;

  // 销毁旧实例
  if (editorInstance.value) {
    editorInstance.value.dispose();
    editorInstance.value = null;
  }

  // 创建新实例
  editorInstance.value = monaco.editor.create(editorContainerRef.value, {
    value: templateForm.value.config_content,
    language: getEditorLanguage(),
    theme: 'vs-dark',
    fontSize: 13,
    lineHeight: 22,
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    automaticLayout: true,
    tabSize: 2,
  });

  // 监听内容变化
  editorInstance.value.onDidChangeModelContent(() => {
    templateForm.value.config_content = editorInstance.value?.getValue() || '';
  });
}

// 监听模板类型和脚本名称变化，切换语言
watch(
  () => [templateForm.value.type, templateForm.value.script_name],
  () => {
    if (editorInstance.value) {
      const model = editorInstance.value.getModel();
      if (model) {
        monaco.editor.setModelLanguage(model, getEditorLanguage());
      }
    }
  }
);

// 弹窗打开时初始化编辑器
watch(templateDialogVisible, (visible) => {
  if (visible) {
    nextTick(() => {
      initEditor();
    });
  } else {
    // 弹窗关闭时销毁编辑器
    if (editorInstance.value) {
      editorInstance.value.dispose();
      editorInstance.value = null;
    }
  }
});
```

- [ ] **Step 4: 替换 textarea 为编辑器容器**

```vue
<!-- 配置内容/脚本内容 -->
<div class="form-section">
  <div class="section-title">
    {{ templateForm.type === 'config' ? '配置内容 (YAML)' : '脚本内容' }}
  </div>
  <div class="section-content">
    <div ref="editorContainerRef" class="monaco-editor-container"></div>
  </div>
</div>
```

- [ ] **Step 5: 新增编辑器容器样式**

```css
.monaco-editor-container {
  width: 100%;
  min-height: 320px;
  background: #1e1e1e;
  border-radius: 4px;
  overflow: hidden;
}
```

- [ ] **Step 6: Commit**

```bash
git add web/apps/web-ele/src/views/env-machine/config.vue
git commit -m "feat(ui): Monaco Editor 替换 textarea，支持动态语言高亮"
```

---

## Task 19: 下发按钮文案调整

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/config.vue`

- [ ] **Step 1: 修改下发按钮文案**

根据模板类型动态显示下发按钮文案：

```typescript
// 下发按钮文案
const deployButtonText = computed(() => {
  if (selectedTemplate.value?.type === 'script') {
    return '下发脚本';
  }
  return '下发配置';
});
```

```vue
<!-- 操作按钮 -->
<div class="action-row">
  <div class="selected-count">已选择 <strong class="count-num">{{ selectedMachineIds.length }}</strong> 台机器</div>
  <ElButton type="primary" @click="openDeployDialog">{{ deployButtonText }}</ElButton>
</div>
```

- [ ] **Step 2: 修改下发确认弹窗标题和文案**

```vue
<!-- 下发确认弹窗 -->
<ElDialog v-model="deployDialogVisible" ...>
  <div class="dialog-box">
    <div class="dialog-header">
      <div class="dialog-icon">...</div>
      <div class="dialog-title">
        {{ selectedTemplate?.type === 'script' ? '确认下发脚本' : '确认下发配置' }}
      </div>
    </div>

    <div class="dialog-body">
      <p class="dialog-desc">
        {{ selectedTemplate?.type === 'script'
          ? '即将把脚本下发到选中的设备，下发后设备将保存脚本文件。'
          : '即将把配置下发到选中的设备，下发后设备将应用新配置。'
        }}
      </p>
      ...
    </div>
  </div>
</ElDialog>
```

- [ ] **Step 3: Commit**

```bash
git add web/apps/web-ele/src/views/env-machine/config.vue
git commit -m "feat(ui): 下发按钮和弹窗文案根据模板类型动态调整"
```

---

## Task 20: 最终验证和提交

- [ ] **Step 1: 启动后端服务**

```bash
cd backend-fastapi && python main.py
```

Expected: 服务启动成功，无报错

- [ ] **Step 2: 启动前端服务**

```bash
cd web && pnpm dev
```

Expected: 前端启动成功

- [ ] **Step 3: 手动测试配置下发**

1. 登录系统
2. 进入"设备管理" -> "设备配置"菜单
3. 点击"新建" -> 选择"配置"类型 -> 填写模板信息 -> 保存
4. 选择模板 -> 选择设备 -> 点击"下发配置"
5. 验证下发成功

- [ ] **Step 4: 手动测试脚本下发**

1. 点击"新建" -> 选择"脚本内容"类型 -> 填写脚本名称（如 `test.ps1`）-> 填写脚本内容 -> 保存
2. 验证左侧列表显示脚本名称和目标系统（Windows）
3. 选择脚本模板 -> 验证设备类型筛选已禁用 -> 验证只显示 Windows 设备
4. 点击"下发脚本"
5. 验证下发成功

- [ ] **Step 5: 最终 Commit（如有遗漏修改）**

```bash
git add -A
git commit -m "feat: 设备配置页面支持脚本下发功能完成"
```

---

## 执行顺序汇总

1. Task 1-9: 后端变更（数据库、Model、Schema、Service、API、菜单）
2. Task 10-11: 前端类型定义和路由
3. Task 12-16: 前端页面主体变更
4. Task 17-18: Monaco Editor 集成
5. Task 19: 下发按钮文案调整
6. Task 20: 最终验证