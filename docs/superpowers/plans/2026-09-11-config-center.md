# 配置中心实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** zq-platform 新增通用「配置中心」（键值对管理页面 + 免鉴权外部查询接口），ocr_service 启动拉取 `ocr_config` 并在 reg_ 匹配前替换识别文本、每天 12:00 定时刷新。

**Architecture:** 平台侧新增 `core/config_center` 模块（PostgreSQL 表 `config_center_item`，value 存 JSON 对象字符串）+ `/api/public/config-center/query` 免鉴权查询；ocr_service 侧新增 `text_replacer.py`（全局替换字典 + httpx 拉取），在 `OCREngine.recognize()` 解析出 TextBlock 后立即应用替换，lifespan 内启动拉取 + asyncio 每日 12:00 刷新。

**Tech Stack:** FastAPI + SQLAlchemy async + Alembic + Vue3/Element Plus/zq-table（平台）；FastAPI + httpx + pytest（ocr_service）。

**Spec:** `docs/superpowers/specs/2026-09-11-config-center-design.md`

## Global Constraints

- 后端路由：静态路由在动态路由前（`/check/key`、`/batch/delete` 必须在 `/{item_id}` 之前）；业务表不带 `core_` 前缀。
- 模型继承 `app.base_model.BaseModel`，服务继承 `app.base_service.BaseService`；响应用 `app.base_schema.PaginatedResponse`。
- 免鉴权接口挂 `/api/public/*` 前缀（现有白名单正则 `^/api/public/.*` 自动放行，不改 auth_middleware）。
- 前端错误提示约定：请求失败只由请求层全局拦截器弹一次错，页面 catch 只做状态恢复，不弹第二条。
- value 校验：合法 JSON 且为 `{str: str}` 对象（前后端双重校验）；key 校验 `^[A-Za-z0-9_-]{1,64}$` 且活动记录内唯一。
- ocr_service：Python 3.8+ 语法；只用已有依赖 httpx，不引入 APScheduler；日志要写入 ocr.log 必须带 `[CONFIG]` 标签（修改过滤器）。
- 提交信息风格：`feat:` / `docs:` / `fix:`。

---

### Task 1: zq-platform 后端 config_center 模块

**Files:**
- Create: `backend-fastapi/core/config_center/__init__.py`（空文件）
- Create: `backend-fastapi/core/config_center/model.py`
- Create: `backend-fastapi/core/config_center/schema.py`
- Create: `backend-fastapi/core/config_center/service.py`
- Create: `backend-fastapi/core/config_center/api.py`
- Create: `backend-fastapi/core/config_center/public_api.py`
- Modify: `backend-fastapi/core/router.py`
- Modify: `backend-fastapi/main.py`

**Interfaces:**
- Produces: `ConfigCenterService(BaseService)`（继承 `get_by_field(db,"key",k)`、`check_unique(db,"key",k,exclude_id)`、`create/update/delete/batch_delete/get_list`）；免鉴权 `GET /api/public/config-center/query?key=` 返回字典本身；管理端 6 个接口（见 api.py）。

- [ ] **Step 1: 写入 6 个模块文件**

`model.py`：
```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File: model.py
@Desc: ConfigCenterItem Model - 配置中心键值对模型
"""
from sqlalchemy import Column, String, Text, Index, text

from app.base_model import BaseModel


class ConfigCenterItem(BaseModel):
    """
    配置中心键值对表

    字段说明：
    - key: 配置键（活动记录内唯一，软删除后可重建同名）
    - value: 配置值，JSON 对象字符串，如 {"充许":"允许","聊关":"聊天"}，键值均为字符串
    - remark: 备注
    """
    __tablename__ = "config_center_item"

    key = Column(String(64), nullable=False, comment="配置键")
    value = Column(Text, nullable=False, comment="配置值(JSON对象字符串)")
    remark = Column(Text, nullable=True, comment="备注")

    __table_args__ = (
        Index(
            "uq_config_center_item_active_key",
            "key",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        Index("ix_config_center_item_key", "key"),
    )
```

`schema.py`：
```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File: schema.py
@Desc: ConfigCenter Schema - 配置中心数据验证模式
"""
import json
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

KEY_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


def _validate_pairs_json(value: str) -> str:
    """校验 value 是合法 JSON 且为 {str: str} 对象"""
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"配置值必须是合法的 JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("配置值必须是 JSON 对象（键值对）")
    for k, v in parsed.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise ValueError("配置值的键和值都必须是字符串")
    return value


class ConfigCenterItemCreate(BaseModel):
    """创建配置项请求"""
    key: str = Field(..., pattern=KEY_PATTERN, description="配置键（字母/数字/下划线/中划线，≤64字符）")
    value: str = Field(..., description='配置值 JSON 对象字符串，如 {"充许":"允许"}')
    remark: Optional[str] = Field(None, description="备注")

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: str) -> str:
        return _validate_pairs_json(v)


class ConfigCenterItemUpdate(BaseModel):
    """更新配置项请求（key 不可修改）"""
    value: Optional[str] = Field(None, description="配置值 JSON 对象字符串")
    remark: Optional[str] = Field(None, description="备注")

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return _validate_pairs_json(v)


class ConfigCenterItemResponse(BaseModel):
    """配置项响应"""
    id: str = Field(..., description="配置项ID")
    key: str = Field(..., description="配置键")
    value: str = Field(..., description="配置值 JSON 字符串")
    remark: Optional[str] = Field(None, description="备注")
    sys_create_datetime: Optional[datetime] = Field(None, description="创建时间")
    sys_update_datetime: Optional[datetime] = Field(None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class ConfigCenterBatchDeleteRequest(BaseModel):
    """批量删除请求"""
    ids: List[str] = Field(..., min_length=1, description="配置项ID列表")
```

`service.py`：
```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File: service.py
@Desc: ConfigCenter Service - 配置中心服务（CRUD 继承 BaseService）
"""
from app.base_service import BaseService
from core.config_center.model import ConfigCenterItem
from core.config_center.schema import ConfigCenterItemCreate, ConfigCenterItemUpdate


class ConfigCenterService(BaseService[ConfigCenterItem, ConfigCenterItemCreate, ConfigCenterItemUpdate]):
    """配置中心服务。

    按键查询：get_by_field(db, "key", key)；按键唯一性校验：check_unique(db, "key", key, exclude_id)。
    """

    model = ConfigCenterItem
```

`api.py`：
```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File: api.py
@Desc: 配置中心管理接口（需登录）
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_schema import PaginatedResponse
from app.database import get_db
from core.config_center.model import ConfigCenterItem
from core.config_center.schema import (
    ConfigCenterBatchDeleteRequest,
    ConfigCenterItemCreate,
    ConfigCenterItemResponse,
    ConfigCenterItemUpdate,
)
from core.config_center.service import ConfigCenterService

router = APIRouter(prefix="/config-center", tags=["配置中心"])


def _escape_like(keyword: str) -> str:
    return keyword.strip().replace("%", r"\%").replace("_", r"\_")


@router.get("/check/key", summary="校验配置键是否已存在")
async def check_key(
    key: str = Query(..., max_length=64, description="配置键"),
    exclude_id: Optional[str] = Query(None, description="排除的配置项ID（编辑时传自身）"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    exists = not await ConfigCenterService.check_unique(db, "key", key, exclude_id)
    return {"exists": exists}


@router.get("", response_model=PaginatedResponse[ConfigCenterItemResponse], summary="获取配置项列表")
async def list_config_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    key: Optional[str] = Query(None, max_length=64, description="配置键关键字"),
    remark: Optional[str] = Query(None, max_length=100, description="备注关键字"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ConfigCenterItemResponse]:
    filters = []
    if key and key.strip():
        filters.append(ConfigCenterItem.key.ilike(f"%{_escape_like(key)}%"))
    if remark and remark.strip():
        filters.append(ConfigCenterItem.remark.ilike(f"%{_escape_like(remark)}%"))
    items, total = await ConfigCenterService.get_list(db, page=page, page_size=page_size, filters=filters)
    return PaginatedResponse(
        items=[ConfigCenterItemResponse.model_validate(item) for item in items],
        total=total,
    )


@router.post("", response_model=ConfigCenterItemResponse, summary="创建配置项")
async def create_config_item(
    data: ConfigCenterItemCreate,
    db: AsyncSession = Depends(get_db),
) -> ConfigCenterItemResponse:
    if not await ConfigCenterService.check_unique(db, "key", data.key):
        raise HTTPException(status_code=400, detail=f"配置键已存在: {data.key}")
    item = await ConfigCenterService.create(db, data)
    return ConfigCenterItemResponse.model_validate(item)


@router.post("/batch/delete", summary="批量删除配置项")
async def batch_delete_config_items(
    data: ConfigCenterBatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    success_count, fail_count = await ConfigCenterService.batch_delete(db, data.ids)
    return {"status": "success", "success_count": success_count, "fail_count": fail_count}


@router.get("/{item_id}", response_model=ConfigCenterItemResponse, summary="获取配置项详情")
async def get_config_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
) -> ConfigCenterItemResponse:
    item = await ConfigCenterService.get_by_id(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="配置项不存在")
    return ConfigCenterItemResponse.model_validate(item)


@router.put("/{item_id}", response_model=ConfigCenterItemResponse, summary="更新配置项（key 不可修改）")
async def update_config_item(
    item_id: str,
    data: ConfigCenterItemUpdate,
    db: AsyncSession = Depends(get_db),
) -> ConfigCenterItemResponse:
    updated = await ConfigCenterService.update(db, item_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="配置项不存在")
    return ConfigCenterItemResponse.model_validate(updated)


@router.delete("/{item_id}", summary="删除配置项（软删除）")
async def delete_config_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    deleted = await ConfigCenterService.delete(db, item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="配置项不存在")
    return {"status": "success", "message": "删除成功"}
```

`public_api.py`：
```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""配置中心免鉴权外部查询接口。

供 ocr_service 等外部系统按配置键查询配置值；路径在 /api/public 下，
由 auth_middleware 现有白名单 ^/api/public/.* 放行。
"""
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from core.config_center.service import ConfigCenterService

router = APIRouter(prefix="/api/public/config-center", tags=["配置中心外部查询"])


@router.get("/query", summary="按配置键查询配置值（免鉴权，返回字典本身）")
async def query_config_value(
    key: str = Query(..., max_length=64, description="配置键"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    item = await ConfigCenterService.get_by_field(db, "key", key)
    if not item:
        raise HTTPException(status_code=404, detail=f"配置项不存在: {key}")
    try:
        value = json.loads(item.value)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="配置项 value 不是合法的 JSON")
    if not isinstance(value, dict):
        raise HTTPException(status_code=500, detail="配置项 value 不是 JSON 对象")
    return value
```

- [ ] **Step 2: 注册路由**

`core/router.py`：在 `from core.config_template.api import TASK_ROUTER` 之后加：
```python
from core.config_center.api import router as config_center_router
```
在 `router.include_router(config_template_router)` 之后加：
```python
router.include_router(config_center_router)
```

`main.py`：在 `from core.config_template.public_api import router as public_config_template_router` 之后加：
```python
from core.config_center.public_api import router as public_config_center_router
```
在 `app.include_router(public_config_template_router)` 之后加：
```python
# 配置中心免鉴权外部查询接口（/api/public 前缀，白名单放行）
app.include_router(public_config_center_router)
```

- [ ] **Step 3: 语法/导入自检**

Run: `cd backend-fastapi && python -c "from core.config_center.api import router; from core.config_center.public_api import router as pr; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend-fastapi/core/config_center backend-fastapi/core/router.py backend-fastapi/main.py
git commit -m "feat: 配置中心模块（键值对管理CRUD + /api/public 免鉴权查询接口）"
```

---

### Task 2: alembic 迁移

**Files:**
- Create: `backend-fastapi/alembic/versions/e7a3c9d1f5b2_add_config_center_item.py`

**Interfaces:** 消费 Task 1 的表定义；产出 `config_center_item` 表（head 链：`b1c2d3e4f5a6` → `e7a3c9d1f5b2`）。

- [ ] **Step 1: 写迁移文件**

```python
"""add config_center_item table

Revision ID: e7a3c9d1f5b2
Revises: b1c2d3e4f5a6
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7a3c9d1f5b2'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('config_center_item',
    sa.Column('key', sa.String(length=64), nullable=False, comment='配置键'),
    sa.Column('value', sa.Text(), nullable=False, comment='配置值(JSON对象字符串)'),
    sa.Column('remark', sa.Text(), nullable=True, comment='备注'),
    sa.Column('id', sa.String(length=21), nullable=False, comment='主键ID(NanoId)'),
    sa.Column('sort', sa.Integer(), nullable=True, comment='排序'),
    sa.Column('is_deleted', sa.Boolean(), nullable=True, comment='是否删除'),
    sa.Column('sys_create_datetime', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='创建时间'),
    sa.Column('sys_update_datetime', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='更新时间'),
    sa.Column('sys_creator_id', sa.String(length=21), nullable=True, comment='创建人ID（逻辑外键关联core_user）'),
    sa.Column('sys_modifier_id', sa.String(length=21), nullable=True, comment='修改人ID（逻辑外键关联core_user）'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_config_center_item_is_deleted'), 'config_center_item', ['is_deleted'], unique=False)
    op.create_index('ix_config_center_item_key', 'config_center_item', ['key'], unique=False)
    op.create_index('uq_config_center_item_active_key', 'config_center_item', ['key'], unique=True,
                    postgresql_where=sa.text('is_deleted = false'))


def downgrade() -> None:
    op.drop_index('uq_config_center_item_active_key', table_name='config_center_item')
    op.drop_index(op.f('ix_config_center_item_is_deleted'), table_name='config_center_item')
    op.drop_index('ix_config_center_item_key', table_name='config_center_item')
    op.drop_table('config_center_item')
```

- [ ] **Step 2: 校验迁移链并尝试升级**

Run: `cd backend-fastapi && alembic history | head -3 && alembic upgrade head`
Expected: head 为 `e7a3c9d1f5b2`；DB 可达则升级成功，不可达则记录给用户部署时执行。

- [ ] **Step 3: Commit**

```bash
git add backend-fastapi/alembic/versions/e7a3c9d1f5b2_add_config_center_item.py
git commit -m "feat: config_center_item 表迁移"
```

---

### Task 3: 前端 API 封装与路由映射

**Files:**
- Create: `web/apps/web-ele/src/api/core/config-center.ts`
- Create: `web/apps/web-ele/src/router/routes/modules/config-center.ts`

**Interfaces:**
- Produces: `ConfigCenterItem`、`getConfigItemListApi(params)`、`createConfigItemApi(data)`、`updateConfigItemApi(id, data)`、`deleteConfigItemApi(id)`、`batchDeleteConfigItemApi({ids})`、`checkConfigKeyApi(key, excludeId?)`、`parseConfigValue(value) → {key,value}[]`、`buildConfigValue(pairs) → string`。

- [ ] **Step 1: 写 API 封装**

```typescript
import { requestClient } from '#/api/request';

/**
 * 配置中心相关类型定义
 */
export interface ConfigCenterItem {
  id: string;
  key: string;
  /** JSON 对象字符串，如 {"充许":"允许"} */
  value: string;
  remark?: string;
  sys_create_datetime?: string;
  sys_update_datetime?: string;
}

export interface ConfigCenterItemCreateInput {
  key: string;
  value: string;
  remark?: string;
}

export interface ConfigCenterItemUpdateInput {
  value: string;
  remark?: string;
}

export interface ConfigCenterItemListParams {
  page?: number;
  pageSize?: number;
  key?: string;
  remark?: string;
}

export interface ConfigCenterBatchDeleteInput {
  ids: string[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

export interface KeyValuePair {
  key: string;
  value: string;
}

/**
 * 获取配置项列表（分页）
 */
export async function getConfigItemListApi(params?: ConfigCenterItemListParams) {
  return requestClient.get<PaginatedResponse<ConfigCenterItem>>(
    '/api/core/config-center',
    { params },
  );
}

/**
 * 创建配置项
 */
export async function createConfigItemApi(data: ConfigCenterItemCreateInput) {
  return requestClient.post<ConfigCenterItem>('/api/core/config-center', data);
}

/**
 * 更新配置项（key 不可修改）
 */
export async function updateConfigItemApi(
  itemId: string,
  data: ConfigCenterItemUpdateInput,
) {
  return requestClient.put<ConfigCenterItem>(
    `/api/core/config-center/${itemId}`,
    data,
  );
}

/**
 * 删除配置项（软删除）
 */
export async function deleteConfigItemApi(itemId: string) {
  return requestClient.delete<{ status: string; message: string }>(
    `/api/core/config-center/${itemId}`,
  );
}

/**
 * 批量删除配置项
 */
export async function batchDeleteConfigItemApi(data: ConfigCenterBatchDeleteInput) {
  return requestClient.post<{ status: string; success_count: number; fail_count: number }>(
    '/api/core/config-center/batch/delete',
    data,
  );
}

/**
 * 校验配置键是否已存在
 */
export async function checkConfigKeyApi(key: string, excludeId?: string) {
  return requestClient.get<{ exists: boolean }>(
    '/api/core/config-center/check/key',
    { params: excludeId ? { key, exclude_id: excludeId } : { key } },
  );
}

/**
 * 把 value JSON 字符串解析为键值对数组；解析失败返回空数组
 */
export function parseConfigValue(value: string): KeyValuePair[] {
  try {
    const parsed = JSON.parse(value) as Record<string, unknown>;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return [];
    }
    return Object.entries(parsed).map(([k, v]) => ({
      key: k,
      value: typeof v === 'string' ? v : String(v),
    }));
  } catch {
    return [];
  }
}

/**
 * 把键值对数组序列化为 value JSON 字符串（保持编辑顺序）
 */
export function buildConfigValue(pairs: KeyValuePair[]): string {
  const obj: Record<string, string> = {};
  for (const pair of pairs) {
    obj[pair.key] = pair.value;
  }
  return JSON.stringify(obj, null, 2);
}
```

- [ ] **Step 2: 写路由映射**

```typescript
import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/system/config-center',
    name: 'SystemConfigCenter',
    component: () => import('#/views/config-center/index.vue'),
    meta: {
      title: '配置中心',
      hideInMenu: true, // 菜单从后端获取，前端只定义组件映射
    },
  },
];

export default routes;
```

- [ ] **Step 3: Commit**

```bash
git add web/apps/web-ele/src/api/core/config-center.ts web/apps/web-ele/src/router/routes/modules/config-center.ts
git commit -m "feat: 配置中心前端 API 封装与路由映射"
```

---

### Task 4: 配置中心页面（列表 / 键值对编辑 / 批量粘贴 / 查看）

**Files:**
- Create: `web/apps/web-ele/src/views/config-center/data.ts`
- Create: `web/apps/web-ele/src/views/config-center/modules/form.vue`
- Create: `web/apps/web-ele/src/views/config-center/index.vue`

**Interfaces:**
- Consumes: Task 3 的全部 API 与工具函数；`useZqTable`（`#/components/zq-table`）、`ZqDrawer`（`#/components/zq-drawer`）。
- Produces: 页面组件 name `SystemConfigCenter`（与菜单 name 一致，keepAlive 依赖）。

- [ ] **Step 1: 写 data.ts（搜索表单 + 表格列）**

```typescript
import type { Column } from 'element-plus';

import type { VbenFormSchema } from '#/adapter/form';

/**
 * 搜索表单字段配置
 */
export function useSearchFormSchema(): VbenFormSchema[] {
  return [
    {
      component: 'Input',
      fieldName: 'key',
      label: '配置键',
      componentProps: { placeholder: '请输入配置键', clearable: true },
    },
    {
      component: 'Input',
      fieldName: 'remark',
      label: '备注',
      componentProps: { placeholder: '请输入备注关键字', clearable: true },
    },
  ];
}

/**
 * 表格列配置
 */
export function useZqTableColumns(): Column[] {
  return [
    {
      key: 'key',
      dataKey: 'key',
      title: '配置键',
      width: 150,
      slots: { default: 'cell-key' },
    },
    {
      key: 'value',
      title: '配置值（键值对）',
      minWidth: 320,
      slots: { default: 'cell-value' },
    },
    {
      key: 'remark',
      dataKey: 'remark',
      title: '备注',
      minWidth: 180,
    },
    {
      key: 'sys_update_datetime',
      dataKey: 'sys_update_datetime',
      title: '更新时间',
      width: 170,
    },
    {
      key: 'actions',
      title: '操作',
      width: 200,
      fixed: true,
      align: 'center' as const,
      slots: { default: 'cell-actions' },
    },
  ];
}
```

- [ ] **Step 2: 写 form.vue（键值对编辑抽屉 + 批量粘贴导入）**

```vue
<script lang="ts" setup>
import type { ConfigCenterItem, KeyValuePair } from '#/api/core/config-center';

import { computed, ref } from 'vue';

import { ZqDrawer } from '#/components/zq-drawer';

import {
  ElAlert,
  ElButton,
  ElDialog,
  ElFormItem,
  ElInput,
  ElMessage,
  ElTable,
  ElTableColumn,
} from 'element-plus';

import {
  buildConfigValue,
  createConfigItemApi,
  updateConfigItemApi,
} from '#/api/core/config-center';

const emit = defineEmits<{
  success: [];
}>();

const visible = ref(false);
const confirmLoading = ref(false);
const formData = ref<{ id?: string; key: string; remark: string }>({
  key: '',
  remark: '',
});
const pairs = ref<KeyValuePair[]>([{ key: '', value: '' }]);
const keyError = ref('');

// 批量粘贴导入
const pasteVisible = ref(false);
const pasteText = ref('');

const isEdit = computed(() => !!formData.value.id);
const drawerTitle = computed(() => (isEdit.value ? '编辑配置' : '新增配置'));

function emptyPair(): KeyValuePair {
  return { key: '', value: '' };
}

function open(data?: ConfigCenterItem) {
  visible.value = true;
  keyError.value = '';
  if (data) {
    formData.value = { id: data.id, key: data.key, remark: data.remark ?? '' };
    try {
      const parsed = JSON.parse(data.value) as Record<string, string>;
      const list = Object.entries(parsed).map(([k, v]) => ({
        key: k,
        value: String(v),
      }));
      pairs.value = list.length > 0 ? list : [emptyPair()];
    } catch {
      pairs.value = [emptyPair()];
    }
  } else {
    formData.value = { key: '', remark: '' };
    pairs.value = [emptyPair()];
  }
}

defineExpose({ open });

function addPair() {
  pairs.value.push(emptyPair());
}

function removePair(index: number) {
  if (pairs.value.length === 1) {
    pairs.value = [emptyPair()];
    return;
  }
  pairs.value.splice(index, 1);
}

function openPasteDialog() {
  pasteText.value = '';
  pasteVisible.value = true;
}

/**
 * 解析批量粘贴文本：每行一条，分隔符支持 = , ， Tab → ->
 */
export function parsePasteLines(text: string): KeyValuePair[] {
  const result: KeyValuePair[] = [];
  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim();
    if (!line) continue;
    const matched = line.match(/^(.+?)(?:=|,|，|\t|→|->)(.+)$/);
    if (!matched) continue;
    const k = matched[1]?.trim() ?? '';
    const v = matched[2]?.trim() ?? '';
    if (k && v) result.push({ key: k, value: v });
  }
  return result;
}

function confirmPaste() {
  const parsed = parsePasteLines(pasteText.value);
  if (parsed.length === 0) {
    ElMessage.warning('未解析到有效的键值对，每行格式：键=值');
    return;
  }
  // 清掉整行为空的占位行
  pairs.value = pairs.value.filter((p) => p.key.trim() || p.value.trim());
  const existing = new Set(pairs.value.map((p) => p.key.trim()));
  let added = 0;
  for (const pair of parsed) {
    if (existing.has(pair.key)) continue; // 跳过与现有重复的键
    pairs.value.push(pair);
    existing.add(pair.key);
    added += 1;
  }
  if (pairs.value.length === 0) pairs.value = [emptyPair()];
  pasteVisible.value = false;
  ElMessage.success(`已导入 ${added} 对（重复键已跳过）`);
}

/**
 * 表单校验，返回错误信息；空串表示通过
 */
function validateForm(): string {
  const key = formData.value.key.trim();
  if (!key) {
    keyError.value = '请输入配置键';
    return keyError.value;
  }
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(key)) {
    keyError.value = '配置键只能是字母、数字、下划线、中划线，且不超过 64 字符';
    return keyError.value;
  }
  keyError.value = '';
  const filled = pairs.value.filter((p) => p.key.trim() || p.value.trim());
  if (filled.length === 0) return '请至少添加一对键值';
  const seen = new Set<string>();
  for (const pair of filled) {
    if (!pair.key.trim()) return '键不能为空';
    if (!pair.value.trim()) return `键「${pair.key.trim()}」的值不能为空`;
    if (seen.has(pair.key.trim())) return `键「${pair.key.trim()}」重复`;
    seen.add(pair.key.trim());
  }
  return '';
}

async function onSubmit() {
  const error = validateForm();
  if (error) {
    ElMessage.warning(error);
    return;
  }
  confirmLoading.value = true;
  const filled = pairs.value.filter((p) => p.key.trim() || p.value.trim());
  const payload = {
    value: buildConfigValue(
      filled.map((p) => ({ key: p.key.trim(), value: p.value.trim() })),
    ),
    remark: formData.value.remark || undefined,
  };
  try {
    if (isEdit.value && formData.value.id) {
      await updateConfigItemApi(formData.value.id, payload);
    } else {
      await createConfigItemApi({ key: formData.value.key.trim(), ...payload });
    }
    visible.value = false;
    emit('success');
  } catch {
    // 请求失败由请求层全局拦截器统一弹错
  } finally {
    confirmLoading.value = false;
  }
}
</script>

<template>
  <ZqDrawer
    v-model="visible"
    :title="drawerTitle"
    :confirm-loading="confirmLoading"
    size="700px"
    @confirm="onSubmit"
  >
    <div class="mx-4 flex flex-col gap-4">
      <div class="flex gap-4">
        <ElFormItem label="配置键" required class="flex-1">
          <ElInput
            v-model="formData.key"
            :disabled="isEdit"
            placeholder="字母/数字/下划线/中划线，≤64字符"
            maxlength="64"
          />
          <div v-if="keyError" class="text-xs text-[#f56c6c]">{{ keyError }}</div>
        </ElFormItem>
        <ElFormItem label="备注" class="flex-1">
          <ElInput v-model="formData.remark" placeholder="配置用途说明" maxlength="200" />
        </ElFormItem>
      </div>

      <div>
        <div class="mb-2 flex items-center justify-between">
          <div class="text-sm">
            配置值（键值对）
            <span class="text-xs text-[#909399]">至少 1 对；键不能为空、不能重复</span>
          </div>
          <div class="flex gap-2">
            <ElButton size="small" plain type="primary" @click="openPasteDialog">
              批量粘贴导入
            </ElButton>
            <ElButton size="small" plain type="primary" @click="addPair">＋添加</ElButton>
          </div>
        </div>

        <ElTable :data="pairs" border size="small" max-height="480">
          <ElTableColumn label="键" min-width="40%">
            <template #default="{ $index }">
              <ElInput v-model="pairs[$index]!.key" placeholder="键" maxlength="200" />
            </template>
          </ElTableColumn>
          <ElTableColumn width="40" align="center">
            <template #default>→</template>
          </ElTableColumn>
          <ElTableColumn label="值" min-width="45%">
            <template #default="{ $index }">
              <ElInput v-model="pairs[$index]!.value" placeholder="值" maxlength="500" />
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="70" align="center">
            <template #default="{ $index }">
              <ElButton link type="danger" size="small" @click="removePair($index)">
                删除
              </ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
      </div>
    </div>

    <!-- 批量粘贴导入 -->
    <ElDialog v-model="pasteVisible" title="批量粘贴导入" width="560px" append-to-body>
      <ElAlert type="info" :closable="false" class="mb-2">
        每行一条「键=值」，分隔符支持 = , ， Tab → ->；与现有键重复的行会被跳过。
      </ElAlert>
      <ElInput
        v-model="pasteText"
        type="textarea"
        :rows="10"
        placeholder="充许=允许&#10;聊关=聊天&#10;己经=已经"
      />
      <template #footer>
        <ElButton @click="pasteVisible = false">取消</ElButton>
        <ElButton type="primary" @click="confirmPaste">导入</ElButton>
      </template>
    </ElDialog>
  </ZqDrawer>
</template>
```

- [ ] **Step 3: 写 index.vue（列表页 + 值列标签 + 查看弹窗）**

```vue
<script lang="ts" setup>
import type { ConfigCenterItem } from '#/api/core/config-center';

import { ref } from 'vue';

import { Page } from '@vben/common-ui';
import { Edit, Eye, Plus, Trash2 } from '@vben/icons';

import {
  ElButton,
  ElDialog,
  ElMessage,
  ElMessageBox,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus';

import {
  batchDeleteConfigItemApi,
  deleteConfigItemApi,
  getConfigItemListApi,
  parseConfigValue,
} from '#/api/core/config-center';
import { useZqTable } from '#/components/zq-table';

import { useSearchFormSchema, useZqTableColumns } from './data';
import Form from './modules/form.vue';

defineOptions({ name: 'SystemConfigCenter' });

const formRef = ref<InstanceType<typeof Form>>();
const selectedRows = ref<ConfigCenterItem[]>([]);

// 查看弹窗状态
const viewVisible = ref(false);
const viewKey = ref('');
const viewRemark = ref('');
const viewPairs = ref<Array<{ key: string; value: string }>>([]);

function onView(row: ConfigCenterItem) {
  viewKey.value = row.key;
  viewRemark.value = row.remark ?? '';
  viewPairs.value = parseConfigValue(row.value);
  viewVisible.value = true;
}

function onEdit(row: ConfigCenterItem) {
  formRef.value?.open(row);
}

function onCreate() {
  formRef.value?.open();
}

function onDelete(row: ConfigCenterItem) {
  ElMessageBox.confirm(`确定删除配置「${row.key}」吗？`, '删除确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(async () => {
      await deleteConfigItemApi(row.id);
      ElMessage.success('删除成功');
      refreshGrid();
    })
    .catch(() => {
      // 用户取消或请求失败（请求层已统一弹错）
    });
}

function onBatchDelete() {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先勾选要删除的配置');
    return;
  }
  const keys = selectedRows.value.map((row) => row.key).join('、');
  ElMessageBox.confirm(
    `确定删除选中的 ${selectedRows.value.length} 个配置（${keys}）吗？`,
    '批量删除确认',
    { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' },
  )
    .then(async () => {
      const ids = selectedRows.value.map((row) => row.id);
      await batchDeleteConfigItemApi({ ids });
      ElMessage.success('批量删除成功');
      selectedRows.value = [];
      refreshGrid();
    })
    .catch(() => {
      // 用户取消或请求失败（请求层已统一弹错）
    });
}

function handleSelectionChange(items: Record<string, any>[]) {
  selectedRows.value = items as ConfigCenterItem[];
}

const fetchItemList = async (params: any) => {
  const res = await getConfigItemListApi({
    page: params.page.currentPage,
    pageSize: params.page.pageSize,
    key: params.form?.key,
    remark: params.form?.remark,
  });
  return { items: res.items, total: res.total };
};

const [Grid, gridApi] = useZqTable({
  gridOptions: {
    columns: useZqTableColumns(),
    border: true,
    stripe: true,
    showSelection: true,
    showIndex: true,
    proxyConfig: {
      autoLoad: true,
      ajax: {
        query: fetchItemList,
      },
    },
    pagerConfig: {
      enabled: true,
      pageSize: 20,
    },
    toolbarConfig: {
      search: true,
      refresh: true,
      zoom: true,
      custom: true,
    },
  },
  formOptions: {
    schema: useSearchFormSchema(),
    showCollapseButton: false,
    submitOnChange: false,
  },
});

function refreshGrid() {
  gridApi.reload();
}
</script>

<template>
  <Page auto-content-height>
    <Form ref="formRef" @success="refreshGrid" />

    <Grid @selection-change="handleSelectionChange">
      <template #toolbar-actions>
        <ElButton type="primary" :icon="Plus" @click="onCreate">新增配置</ElButton>
        <ElButton type="danger" plain :icon="Trash2" @click="onBatchDelete">
          批量删除{{ selectedRows.length > 0 ? `(${selectedRows.length})` : '' }}
        </ElButton>
      </template>

      <!-- 配置键（等宽字体） -->
      <template #cell-key="{ row }">
        <span class="font-mono">{{ row.key }}</span>
      </template>

      <!-- 配置值：键值对标签，每对一行，超过约 200px 内部滚动 -->
      <template #cell-value="{ row }">
        <div v-if="parseConfigValue(row.value).length > 0">
          <div
            class="max-h-[200px] overflow-y-auto rounded border border-solid border-[#ebeef5] bg-[#fafafa] p-2"
          >
            <div
              v-for="(pair, index) in parseConfigValue(row.value)"
              :key="index"
              class="mb-1 last:mb-0"
            >
              <ElTag size="small">{{ pair.key }} → {{ pair.value }}</ElTag>
            </div>
          </div>
          <div class="mt-0.5 text-xs text-[#909399]">
            共 {{ parseConfigValue(row.value).length }} 对
          </div>
        </div>
        <span v-else>-</span>
      </template>

      <template #cell-actions="{ row }">
        <ElButton link type="primary" :icon="Edit" @click="onEdit(row)">编辑</ElButton>
        <ElButton link type="primary" :icon="Eye" @click="onView(row)">查看</ElButton>
        <ElButton link type="danger" :icon="Trash2" @click="onDelete(row)">删除</ElButton>
      </template>
    </Grid>

    <!-- 查看弹窗：只读键值对列表 -->
    <ElDialog
      v-model="viewVisible"
      :title="`查看配置 · ${viewKey}`"
      width="560px"
    >
      <ElTable :data="viewPairs" max-height="420" size="small" border>
        <ElTableColumn prop="key" label="键" min-width="40%" />
        <ElTableColumn prop="value" label="值" min-width="60%" />
      </ElTable>
      <div class="mt-1 text-xs text-[#909399]">
        共 {{ viewPairs.length }} 对 · 备注：{{ viewRemark || '-' }}
      </div>
    </ElDialog>
  </Page>
</template>
```

- [ ] **Step 4: 类型检查**

Run: `cd web && pnpm check:type`
Expected: 无类型错误（若 `Eye` 图标不存在于 `@vben/icons`，把查看按钮改为不带图标的 `link` 按钮）。

- [ ] **Step 5: Commit**

```bash
git add web/apps/web-ele/src/views/config-center
git commit -m "feat: 配置中心页面（键值对列表/编辑/批量粘贴导入/查看弹窗）"
```

---

### Task 5: 菜单初始化与文档

**Files:**
- Modify: `backend-fastapi/scripts/init_all_menus.py`
- Modify: `AGENTS.md`

- [ ] **Step 1: init_all_menus.py 增加菜单**

在 `system-permission` 条目（`"order": 6` 的 dict）之后、`]` 之前插入：
```python
    {
        "id": "system-config-center",
        "name": "SystemConfigCenter",
        "title": "配置中心",
        "path": "/system/config-center",
        "type": "menu",
        "component": "/views/config-center/index",
        "parent_id": "system-root",
        "order": 7,
    },
```
同时把末尾打印清单里 `"    - 权限管理"` 之后加一行 `"    - 配置中心"`。

- [ ] **Step 2: AGENTS.md 核心模块表加一行**

在 `| config_template | ... |` 行之后加：
```
| `config_center` | 配置中心 - 通用键值对配置管理、/api/public 免鉴权外部查询 |
```

- [ ] **Step 3: 尝试执行菜单初始化（DB 可达时）**

Run: `cd backend-fastapi && python scripts/init_all_menus.py`
Expected: 重建菜单并输出「配置中心」；DB 不可达则记录为部署步骤。

- [ ] **Step 4: Commit**

```bash
git add backend-fastapi/scripts/init_all_menus.py AGENTS.md
git commit -m "feat: 系统管理下新增配置中心菜单"
```

---

### Task 6: 后端接口联调验证

- [ ] **Step 1: 启动后端并验证**（DB 可达时）

Run: `cd backend-fastapi && python main.py`（后台）
```bash
# 免鉴权查询（先在页面或用 curl 创建配置）
curl -s 'http://localhost:8000/api/public/config-center/query?key=not_exist'   # 期望 404 {"detail":"配置项不存在: not_exist"}
```
用页面登录后创建 `ocr_config`（键值对 充许→允许、聊关→聊天），再：
```bash
curl -s 'http://localhost:8000/api/public/config-center/query?key=ocr_config'  # 期望 {"充许":"允许","聊关":"聊天"}
```

- [ ] **Step 2: 记录验证结果**（DB 不可达则把启动/迁移/菜单命令写进交付说明）

---

### Task 7: ocr_service text_replacer（TDD）

**Files:**
- Test: `tests/test_text_replacer.py`
- Modify: `ocr_service/config.py`（3 个新配置字段）
- Create: `ocr_service/text_replacer.py`

**Interfaces:**
- Produces: `get_replace_map() -> dict[str, str]`、`set_replace_map(dict)`、`apply_replacements(text: str) -> str`、`parse_replace_map(data) -> dict[str, str]`、`fetch_replace_map(url, key, timeout) -> dict[str, str]`、`refresh_replace_map(url, key, timeout) -> bool`（Task 8 消费）。

- [ ] **Step 1: 写失败测试**

```python
"""text_replacer 单元测试：替换逻辑 + 配置拉取解析 + 定时刷新语义。"""
import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ocr_service import text_replacer
from ocr_service.text_replacer import (
    apply_replacements,
    fetch_replace_map,
    parse_replace_map,
    refresh_replace_map,
    set_replace_map,
)


@pytest.fixture(autouse=True)
def clean_replace_map():
    """每个用例前后清空全局替换字典，避免串扰。"""
    set_replace_map({})
    yield
    set_replace_map({})


# ---------------- apply_replacements ----------------

def test_apply_replacements_basic():
    set_replace_map({"充许": "允许"})
    assert apply_replacements("充许用户聊天") == "允许用户聊天"


def test_apply_replacements_multiple_pairs():
    set_replace_map({"充许": "允许", "聊关": "聊天"})
    assert apply_replacements("充许聊关") == "允许聊天"


def test_apply_replacements_empty_map_passthrough():
    assert apply_replacements("充许") == "充许"


def test_apply_replacements_order_overlap():
    """按配置顺序执行：A->B 且 B->C 会链式叠加（预期行为）。"""
    set_replace_map({"A": "B", "B": "C"})
    assert apply_replacements("A") == "C"


def test_apply_replacements_skips_empty_key():
    set_replace_map({"": "X", "充许": "允许"})
    assert apply_replacements("充许") == "允许"


# ---------------- parse_replace_map ----------------

def test_parse_replace_map_valid():
    assert parse_replace_map({"充许": "允许"}) == {"充许": "允许"}


def test_parse_replace_map_rejects_non_dict():
    with pytest.raises(ValueError):
        parse_replace_map(["充许", "允许"])


def test_parse_replace_map_rejects_non_str_value():
    with pytest.raises(ValueError):
        parse_replace_map({"a": 1})


def test_parse_replace_map_rejects_non_str_key():
    with pytest.raises(ValueError):
        parse_replace_map({1: "a"})


# ---------------- fetch_replace_map ----------------

def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_fetch_replace_map_success(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["key"] == "ocr_config"
        return httpx.Response(200, json={"充许": "允许", "聊关": "聊天"})

    monkeypatch.setattr(
        text_replacer, "_create_client", lambda timeout: _mock_client(handler)
    )
    mapping = asyncio.run(
        fetch_replace_map("http://platform/api/public/config-center/query", "ocr_config", 5.0)
    )
    assert mapping == {"充许": "允许", "聊关": "聊天"}


def test_fetch_replace_map_404(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "配置项不存在: ocr_config"})

    monkeypatch.setattr(
        text_replacer, "_create_client", lambda timeout: _mock_client(handler)
    )
    with pytest.raises(RuntimeError, match="404"):
        asyncio.run(
            fetch_replace_map("http://platform/api/public/config-center/query", "ocr_config", 5.0)
        )


def test_fetch_replace_map_invalid_json(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    monkeypatch.setattr(
        text_replacer, "_create_client", lambda timeout: _mock_client(handler)
    )
    with pytest.raises(Exception):
        asyncio.run(
            fetch_replace_map("http://platform/api/public/config-center/query", "ocr_config", 5.0)
        )


def test_fetch_replace_map_non_dict(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["a", "b"])

    monkeypatch.setattr(
        text_replacer, "_create_client", lambda timeout: _mock_client(handler)
    )
    with pytest.raises(ValueError):
        asyncio.run(
            fetch_replace_map("http://platform/api/public/config-center/query", "ocr_config", 5.0)
        )


# ---------------- refresh_replace_map ----------------

def test_refresh_replace_map_success_updates_map(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"充许": "允许"})

    monkeypatch.setattr(
        text_replacer, "_create_client", lambda timeout: _mock_client(handler)
    )
    assert asyncio.run(
        refresh_replace_map("http://platform/q", "ocr_config", 5.0)
    ) is True
    assert apply_replacements("充许") == "允许"


def test_refresh_replace_map_failure_keeps_old(monkeypatch):
    set_replace_map({"充许": "允许"})

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    monkeypatch.setattr(
        text_replacer, "_create_client", lambda timeout: _mock_client(handler)
    )
    assert asyncio.run(
        refresh_replace_map("http://platform/q", "ocr_config", 5.0)
    ) is False
    assert apply_replacements("充许") == "允许"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd /d/code/ocr_service && ./venv/Scripts/python.exe -m pytest tests/test_text_replacer.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'ocr_service.text_replacer'`）

- [ ] **Step 3: 实现 config.py 新字段与 text_replacer.py**

`ocr_service/config.py`：`ServiceConfig` 在 `default_match_method: str = "template"` 之后加：
```python
    # 配置中心（测试平台）替换配置
    config_center_url: str = ""  # 免鉴权查询地址，空=禁用替换功能
    config_center_key: str = "ocr_config"  # 拉取的配置键
    config_center_timeout: float = 5.0  # 请求超时（秒）
```
`from_env()` 在 `default_match_method=...` 之后加：
```python
            # 配置中心（测试平台）替换配置
            config_center_url=os.getenv("OCR_CONFIG_CENTER_URL", "").strip(),
            config_center_key=os.getenv("OCR_CONFIG_CENTER_KEY", "ocr_config"),
            config_center_timeout=float(os.getenv("OCR_CONFIG_CENTER_TIMEOUT", "5.0")),
```

`ocr_service/text_replacer.py`：
```python
"""
OCR 识别文本替换配置。

从测试平台配置中心拉取替换规则（如 {"充许":"允许","聊关":"聊天"}），
在识别结果进入任何 reg_/文本匹配之前对文本做整串替换。
"""

import logging
from typing import Dict

import httpx

logger = logging.getLogger(__name__)

# 全局替换字典（键=待替换文本，值=替换后文本）；空字典表示不替换
_replace_map: Dict[str, str] = {}


def get_replace_map() -> Dict[str, str]:
    """获取当前替换字典。"""
    return _replace_map


def set_replace_map(mapping: Dict[str, str]) -> None:
    """设置替换字典。"""
    global _replace_map
    _replace_map = dict(mapping)


def apply_replacements(text: str) -> str:
    """按配置顺序对文本逐对替换。"""
    for wrong, right in _replace_map.items():
        if wrong:
            text = text.replace(wrong, right)
    return text


def parse_replace_map(data) -> Dict[str, str]:
    """校验接口返回数据为 {str: str} 字典。"""
    if not isinstance(data, dict):
        raise ValueError(f"配置中心返回的不是 JSON 对象: {type(data).__name__}")
    result: Dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError(f"配置值键值对必须是字符串: {key!r}={value!r}")
        result[key] = value
    return result


def _create_client(timeout: float) -> httpx.AsyncClient:
    """创建 HTTP 客户端（独立函数便于测试注入 MockTransport）。"""
    return httpx.AsyncClient(timeout=timeout)


async def fetch_replace_map(url: str, key: str, timeout: float) -> Dict[str, str]:
    """从配置中心拉取替换字典。"""
    async with _create_client(timeout) as client:
        response = await client.get(url, params={"key": key})
    if response.status_code != 200:
        raise RuntimeError(
            f"配置中心返回 HTTP {response.status_code}: {response.text[:200]}"
        )
    return parse_replace_map(response.json())


async def refresh_replace_map(url: str, key: str, timeout: float) -> bool:
    """拉取并应用替换配置；失败保留旧配置。返回是否成功。"""
    try:
        mapping = await fetch_replace_map(url, key, timeout)
    except Exception as exc:
        logger.error(
            "[CONFIG] 替换配置拉取失败，保留旧配置(当前 %d 对): %s",
            len(_replace_map),
            exc,
        )
        return False
    set_replace_map(mapping)
    logger.info("[CONFIG] 替换配置已更新: key=%s, 共 %d 对规则", key, len(mapping))
    return True
```

- [ ] **Step 4: 运行测试确认通过**

Run: `./venv/Scripts/python.exe -m pytest tests/test_text_replacer.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_text_replacer.py ocr_service/text_replacer.py ocr_service/config.py
git commit -m "feat: 文本替换配置模块（拉取/校验/应用，TDD）"
```

---

### Task 8: ocr_service 接线（识别替换 + 启动拉取 + 每日 12:00 刷新）

**Files:**
- Modify: `ocr_service/core/ocr_engine.py`（recognize() 解析后应用替换）
- Modify: `ocr_service/server.py`（日志过滤器 + lifespan + 定时任务）
- Modify: `docker-compose.yml`（配置中心环境变量）
- Modify: `AGENTS.md`（配置表补 3 行）

**Interfaces:**
- Consumes: Task 7 的 `apply_replacements/get_replace_map/refresh_replace_map`、`get_config()` 的 `config_center_url/config_center_key/config_center_timeout`。
- Produces: 所有 OCR 接口返回替换后的文本；`_seconds_until_next_noon(now) -> float`（可测）。

- [ ] **Step 1: ocr_engine.py 应用替换**

`ocr_service/core/ocr_engine.py` 头部 import 区加：
```python
from ocr_service.text_replacer import apply_replacements, get_replace_map
```
`recognize()` 中 `texts = OCRResult.parse_from_paddleocr(ocr_result, confidence_threshold, scale)` 之后、`duration_ms = ...` 之前插入：
```python
            # 应用配置中心替换规则（在所有 reg_/文本匹配之前）
            replace_map = get_replace_map()
            if replace_map:
                for text_block in texts:
                    text_block.text = apply_replacements(text_block.text)
```

- [ ] **Step 2: server.py 日志过滤器放行 [CONFIG]**

`RequestResponseFilter.filter` 改为：
```python
    def filter(self, record):
        msg = record.getMessage()
        # 允许包含 [REQUEST]、[RESPONSE]、[OCR_RAW]、[MATCH]、[CONFIG] 或 ERROR 级别的日志
        return "[REQUEST]" in msg or "[RESPONSE]" in msg or "[OCR_RAW]" in msg or "[MATCH]" in msg or "[CONFIG]" in msg or record.levelno >= logging.ERROR
```

- [ ] **Step 3: server.py 增加 lifespan 与定时刷新**

import 区加：
```python
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
```
以及：
```python
from ocr_service.text_replacer import refresh_replace_map
```

在 `create_app()` 之前加入以下代码块：
```python
def _seconds_until_next_noon(now: datetime = None) -> float:
    """距下一个本地时间 12:00 的秒数。"""
    now = now or datetime.now()
    target = now.replace(hour=12, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def _config_refresh_loop(url: str, key: str, timeout: float) -> None:
    """每天 12:00 拉取替换配置；失败则每 10 分钟重试直到成功。"""
    while True:
        wait_seconds = _seconds_until_next_noon()
        logger.info("[CONFIG] 下一次替换配置同步在 %.0f 秒后", wait_seconds)
        await asyncio.sleep(wait_seconds)
        while not await refresh_replace_map(url, key, timeout):
            logger.error("[CONFIG] 定时刷新失败，10 分钟后重试")
            await asyncio.sleep(10 * 60)


async def _pull_config_on_startup(url: str, key: str, timeout: float) -> None:
    """启动时拉取替换配置，最多 3 次（间隔 0/2/4 秒），失败不阻塞启动。"""
    for attempt, delay in enumerate((0, 2, 4), start=1):
        if delay:
            await asyncio.sleep(delay)
        if await refresh_replace_map(url, key, timeout):
            return
        logger.error("[CONFIG] 启动拉取替换配置失败(第 %d/3 次)", attempt)
    logger.error("[CONFIG] 启动拉取替换配置最终失败，以空规则运行，等待定时任务重试")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """应用生命周期：启动拉取替换配置，并注册每日 12:00 定时刷新任务。"""
    config = get_config()
    refresh_task = None
    if config.config_center_url:
        logger.info("[CONFIG] 检测到配置中心地址，开始拉取替换配置: %s", config.config_center_url)
        await _pull_config_on_startup(
            config.config_center_url, config.config_center_key, config.config_center_timeout
        )
        refresh_task = asyncio.create_task(
            _config_refresh_loop(
                config.config_center_url, config.config_center_key, config.config_center_timeout
            )
        )
    else:
        logger.info("[CONFIG] 未配置 OCR_CONFIG_CENTER_URL，跳过替换配置拉取")

    yield

    if refresh_task:
        refresh_task.cancel()
        try:
            await refresh_task
        except asyncio.CancelledError:
            pass
```

`create_app()` 中 `app = FastAPI(...)` 增加 `lifespan=_lifespan` 参数：
```python
    app = FastAPI(
        title="OCR Service",
        description="基于 PaddleOCR 的文字识别和 OpenCV 图像匹配服务",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=_lifespan,
    )
```

- [ ] **Step 4: docker-compose.yml 增加配置中心环境变量**

在 `- OCR_MATCH_METHOD=template` 之后加：
```yaml
      # ==================== 配置中心（测试平台）替换配置 ====================
      # 平台免鉴权查询地址（注释或留空=禁用替换功能），例如:
      # - OCR_CONFIG_CENTER_URL=http://192.168.0.100:8000/api/public/config-center/query
      # 拉取的配置键
      - OCR_CONFIG_CENTER_KEY=ocr_config
      # 请求超时（秒）
      - OCR_CONFIG_CENTER_TIMEOUT=5
```

- [ ] **Step 5: AGENTS.md 配置表补 3 行**

在 `| OCR_MATCH_METHOD | template | 默认匹配方法 |` 之后加：
```
| OCR_CONFIG_CENTER_URL | （空） | 测试平台免鉴权查询地址，空=禁用替换功能 |
| OCR_CONFIG_CENTER_KEY | ocr_config | 拉取的替换配置键 |
| OCR_CONFIG_CENTER_TIMEOUT | 5.0 | 配置拉取请求超时（秒） |
```

- [ ] **Step 6: 全量测试 + 启动冒烟**

Run: `./venv/Scripts/python.exe -m pytest tests/ -v` → 全部 PASS
Run: `./venv/Scripts/python.exe -m pytest tests/test_text_replacer.py -v`（含 `_seconds_until_next_noon` 需补测？——补充进 Task 7 测试文件）

补充测试（加到 Task 7 测试文件末尾，Task 7 实现前写好即红）：
```python
# ---------------- _seconds_until_next_noon ----------------

def test_seconds_until_next_noon_before_noon():
    from datetime import datetime

    from ocr_service.server import _seconds_until_next_noon

    assert _seconds_until_next_noon(datetime(2026, 9, 11, 6, 0, 0)) == 6 * 3600


def test_seconds_until_next_noon_after_noon():
    from datetime import datetime

    from ocr_service.server import _seconds_until_next_noon

    assert _seconds_until_next_noon(datetime(2026, 9, 11, 13, 0, 0)) == 23 * 3600


def test_seconds_until_next_noon_exactly_noon():
    from datetime import datetime

    from ocr_service.server import _seconds_until_next_noon

    assert _seconds_until_next_noon(datetime(2026, 9, 11, 12, 0, 0)) == 24 * 3600
```

启动冒烟（无 OCR_CONFIG_CENTER_URL，确认不报错、日志含「跳过」）：
Run: `./venv/Scripts/python.exe -c "from ocr_service.server import app; print('app ok', app.router.lifespan_context is not None)"`
Expected: `app ok True`

- [ ] **Step 7: Commit**

```bash
git add ocr_service/core/ocr_engine.py ocr_service/server.py docker-compose.yml AGENTS.md tests/test_text_replacer.py
git commit -m "feat: 识别结果替换接入（reg_ 匹配前）+ 启动拉取 + 每日12点定时刷新"
```

---

### Task 9: 端到端验收（人工/半自动）

- [ ] 平台：页面「系统管理 → 配置中心」可见，新增 `ocr_config`（充许→允许、聊关→聊天）
- [ ] `curl 'http://<platform>:8000/api/public/config-center/query?key=ocr_config'`（无 Token）返回字典
- [ ] ocr_service 设 `OCR_CONFIG_CENTER_URL` 重启，日志出现 `[CONFIG] 替换配置已更新`
- [ ] 识别含「充许」的图：`/ocr/get_ocr_texts` 返回「允许」；`/ocr/get_coord_by_text` 用 `filter_text=允许` 与 `reg_允[许]` 命中
- [ ] 停掉平台再重启 ocr_service：服务可用（空规则）、日志有 ERROR

## Self-Review 记录

- Spec 覆盖：表/CRUD/免鉴权/页面(列表+编辑+粘贴+查看)/菜单/迁移 → Task 1-5；ocr_service 拉取/替换/定时 → Task 7-8；部署与验收 → Task 6/9。✔
- 占位符：无 TBD/TODO；所有代码块完整。✔
- 类型一致：`parse_config_value`（TS）对应 `parseConfigValue`；`refresh_replace_map(url, key, timeout) -> bool` 在 Task 7 定义、Task 8 消费一致；`_seconds_until_next_noon(now: datetime = None)` 测试传 datetime。✔
- 修正：设计稿中「批量删除」需要后端接口 → Task 1 补 `POST /batch/delete`；搜索按 key/remark 两个参数（与设计稿两个字段一致）。✔
