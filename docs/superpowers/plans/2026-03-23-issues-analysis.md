# 修改引入问题页面实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建 issues_analysis 表和修改引入问题页面，并在 feature_analysis 表新增修改引入数量字段

**Architecture:** 后端采用 FastAPI + SQLAlchemy 异步 ORM，前端采用 Vue 3 + Element Plus。遵循现有 feature_analysis 模块的代码模式。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vue 3, Element Plus, TypeScript

---

## Task 1: 创建后端 issues_analysis 模块目录

**Files:**
- Create: `backend-fastapi/core/issues_analysis/__init__.py`
- Create: `backend-fastapi/core/issues_analysis/model.py`
- Create: `backend-fastapi/core/issues_analysis/schema.py`
- Create: `backend-fastapi/core/issues_analysis/service.py`
- Create: `backend-fastapi/core/issues_analysis/api.py`

- [ ] **Step 1: 创建模块目录和 __init__.py**

```bash
mkdir -p backend-fastapi/core/issues_analysis
```

创建 `backend-fastapi/core/issues_analysis/__init__.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
问题分析模块 - Issues Analysis Module
"""
```

- [ ] **Step 2: 创建 model.py**

创建 `backend-fastapi/core/issues_analysis/model.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
问题分析模型 - Issues Analysis Model
"""
from sqlalchemy import Column, String, Index

from app.base_model import BaseModel


class IssuesAnalysis(BaseModel):
    """问题分析表"""
    __tablename__ = "issues_analysis"

    # 问题信息
    issues_id = Column(String(64), nullable=True, comment="问题编号")
    issues_title = Column(String(64), nullable=True, comment="问题名称")
    issues_services = Column(String(64), nullable=True, comment="问题归属")
    issues_owner = Column(String(64), nullable=True, comment="开发责任人")
    issues_test_owner = Column(String(64), nullable=True, comment="测试责任人")
    issues_severity = Column(String(64), nullable=True, comment="严重程度")
    issues_probability = Column(String(64), nullable=True, comment="重现概率")
    issues_status = Column(String(64), nullable=True, comment="问题状态")
    issues_version = Column(String(64), nullable=True, comment="发现问题版本")

    # 关联需求
    feature_id = Column(String(64), nullable=True, comment="关联需求ID")
    feature_desc = Column(String(64), nullable=True, comment="需求名称")

    # 同步信息
    sync_time = Column(String(64), nullable=True, comment="数据同步时间")
    create_by = Column(String(64), nullable=True, comment="创建者")
    create_time = Column(String(64), nullable=True, comment="创建时间")
    modify_time = Column(String(64), nullable=True, comment="修改时间")

    __table_args__ = (
        Index('idx_issues_version', 'issues_version'),
        Index('idx_issues_deleted', 'is_deleted'),
    )
```

- [ ] **Step 3: 创建 schema.py**

创建 `backend-fastapi/core/issues_analysis/schema.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
问题分析 Schema - Issues Analysis Schema
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class IssuesAnalysisBase(BaseModel):
    """问题分析基础 Schema"""
    issues_id: Optional[str] = Field(None, alias="issuesId", description="问题编号")
    issues_title: Optional[str] = Field(None, alias="issuesTitle", description="问题名称")
    issues_services: Optional[str] = Field(None, alias="issuesServices", description="问题归属")
    issues_owner: Optional[str] = Field(None, alias="issuesOwner", description="开发责任人")
    issues_test_owner: Optional[str] = Field(None, alias="issuesTestOwner", description="测试责任人")
    issues_severity: Optional[str] = Field(None, alias="issuesSeverity", description="严重程度")
    issues_probability: Optional[str] = Field(None, alias="issuesProbability", description="重现概率")
    issues_status: Optional[str] = Field(None, alias="issuesStatus", description="问题状态")
    issues_version: Optional[str] = Field(None, alias="issuesVersion", description="发现问题版本")
    feature_id: Optional[str] = Field(None, alias="featureId", description="关联需求ID")
    feature_desc: Optional[str] = Field(None, alias="featureDesc", description="需求名称")
    sync_time: Optional[str] = Field(None, alias="syncTime", description="数据同步时间")
    create_by: Optional[str] = Field(None, alias="createBy", description="创建者")
    create_time: Optional[str] = Field(None, alias="createTime", description="创建时间")
    modify_time: Optional[str] = Field(None, alias="modifyTime", description="修改时间")

    class Config:
        populate_by_name = True


class IssuesAnalysisCreate(IssuesAnalysisBase):
    """创建问题分析"""
    pass


class IssuesAnalysisUpdate(IssuesAnalysisBase):
    """更新问题分析"""
    pass


class IssuesAnalysisResponse(IssuesAnalysisBase):
    """问题分析响应"""
    id: str

    class Config:
        populate_by_name = True
        from_attributes = True


class VersionListResponse(BaseModel):
    """版本列表响应"""
    items: List[str]
```

- [ ] **Step 4: 创建 service.py**

创建 `backend-fastapi/core/issues_analysis/service.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
问题分析服务 - Issues Analysis Service
"""
from typing import List, Optional, Tuple

from sqlalchemy import select, distinct, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_service import BaseService
from core.issues_analysis.model import IssuesAnalysis
from core.issues_analysis.schema import IssuesAnalysisCreate, IssuesAnalysisUpdate


class IssuesAnalysisService(BaseService[IssuesAnalysis, IssuesAnalysisCreate, IssuesAnalysisUpdate]):
    """问题分析服务"""

    model = IssuesAnalysis
    excel_columns = {}
    excel_sheet_name = "问题分析"

    @classmethod
    async def get_list_with_filters(
        cls,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        version: Optional[str] = None,
        feature_desc: Optional[str] = None,
        issues_owner: Optional[str] = None,
        issues_severity: Optional[str] = None,
    ) -> Tuple[List[IssuesAnalysis], int]:
        """
        获取问题列表（固定条件：问题标题包含"修改引入"）

        :param db: 数据库会话
        :param page: 页码
        :param page_size: 每页数量
        :param version: 版本筛选
        :param feature_desc: 需求标题筛选（模糊匹配）
        :param issues_owner: 责任人筛选
        :param issues_severity: 严重程度筛选
        :return: (数据列表, 总数)
        """
        query = select(IssuesAnalysis).where(
            IssuesAnalysis.is_deleted == False,  # noqa: E712
            IssuesAnalysis.issues_title.like("%修改引入%")  # 固定条件
        )

        # 动态筛选条件
        if version and version.strip():
            query = query.where(IssuesAnalysis.issues_version == version)
        if feature_desc and feature_desc.strip():
            query = query.where(IssuesAnalysis.feature_desc.like(f"%{feature_desc}%"))
        if issues_owner and issues_owner.strip():
            query = query.where(IssuesAnalysis.issues_owner == issues_owner)
        if issues_severity and issues_severity.strip():
            query = query.where(IssuesAnalysis.issues_severity == issues_severity)

        # 统计总数
        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar() or 0

        # 分页
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await db.execute(query)
        items = result.scalars().all()

        return items, total

    @classmethod
    async def get_versions(cls, db: AsyncSession) -> List[str]:
        """获取所有版本列表（去重）"""
        result = await db.execute(
            select(distinct(IssuesAnalysis.issues_version))
            .where(
                IssuesAnalysis.is_deleted == False,  # noqa: E712
                IssuesAnalysis.issues_version.isnot(None),
                IssuesAnalysis.issues_version != ''
            )
            .order_by(IssuesAnalysis.issues_version.desc())
        )
        versions = [row[0] for row in result.all()]
        return versions

    @classmethod
    async def get_owners(cls, db: AsyncSession) -> List[str]:
        """获取所有责任人列表（去重）"""
        result = await db.execute(
            select(distinct(IssuesAnalysis.issues_owner))
            .where(
                IssuesAnalysis.is_deleted == False,  # noqa: E712
                IssuesAnalysis.issues_owner.isnot(None),
                IssuesAnalysis.issues_owner != ''
            )
            .order_by(IssuesAnalysis.issues_owner)
        )
        owners = [row[0] for row in result.all()]
        return owners

    @classmethod
    async def get_severities(cls, db: AsyncSession) -> List[str]:
        """获取所有严重程度列表（去重）"""
        result = await db.execute(
            select(distinct(IssuesAnalysis.issues_severity))
            .where(
                IssuesAnalysis.is_deleted == False,  # noqa: E712
                IssuesAnalysis.issues_severity.isnot(None),
                IssuesAnalysis.issues_severity != ''
            )
            .order_by(IssuesAnalysis.issues_severity)
        )
        severities = [row[0] for row in result.all()]
        return severities
```

- [ ] **Step 5: 创建 api.py**

创建 `backend-fastapi/core/issues_analysis/api.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
问题分析 API - Issues Analysis API
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.base_schema import PaginatedResponse
from core.issues_analysis.schema import (
    IssuesAnalysisResponse,
    VersionListResponse
)
from core.issues_analysis.service import IssuesAnalysisService

router = APIRouter(prefix="/issues-analysis", tags=["问题分析"])


@router.get("", response_model=PaginatedResponse[IssuesAnalysisResponse], summary="获取问题列表")
async def get_issues_list(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize", description="每页数量"),
    version: Optional[str] = Query(None, description="版本筛选"),
    feature_desc: Optional[str] = Query(None, alias="featureDesc", description="需求标题筛选"),
    issues_owner: Optional[str] = Query(None, alias="issuesOwner", description="责任人筛选"),
    issues_severity: Optional[str] = Query(None, alias="issuesSeverity", description="严重程度筛选"),
    db: AsyncSession = Depends(get_db)
):
    """获取问题列表（固定条件：问题标题包含"修改引入"）"""
    items, total = await IssuesAnalysisService.get_list_with_filters(
        db, page=page, page_size=page_size, version=version,
        feature_desc=feature_desc, issues_owner=issues_owner, issues_severity=issues_severity
    )

    response_items = [IssuesAnalysisResponse.model_validate(item) for item in items]
    return PaginatedResponse(items=response_items, total=total)


@router.get("/versions", response_model=VersionListResponse, summary="获取版本列表")
async def get_versions(
    db: AsyncSession = Depends(get_db)
):
    """获取所有版本列表（去重）"""
    versions = await IssuesAnalysisService.get_versions(db)
    return VersionListResponse(items=versions)


@router.get("/owners", response_model=VersionListResponse, summary="获取责任人列表")
async def get_owners(
    db: AsyncSession = Depends(get_db)
):
    """获取所有责任人列表（去重）"""
    owners = await IssuesAnalysisService.get_owners(db)
    return VersionListResponse(items=owners)


@router.get("/severities", response_model=VersionListResponse, summary="获取严重程度列表")
async def get_severities(
    db: AsyncSession = Depends(get_db)
):
    """获取所有严重程度列表（去重）"""
    severities = await IssuesAnalysisService.get_severities(db)
    return VersionListResponse(items=severities)
```

- [ ] **Step 6: 提交后端模块**

```bash
git add backend-fastapi/core/issues_analysis/
git commit -m "feat: 创建 issues_analysis 后端模块"
```

---

## Task 2: 注册路由到 core/router.py

**Files:**
- Modify: `backend-fastapi/core/router.py`

- [ ] **Step 1: 导入并注册路由**

在 `backend-fastapi/core/router.py` 中添加：

```python
# 在导入区域添加
from core.issues_analysis.api import router as issues_analysis_router

# 在注册路由区域添加
router.include_router(issues_analysis_router)
```

完整修改：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Core模块统一路由入口
"""
from fastapi import APIRouter

from core.auth.api import router as auth_router
from core.dept.api import router as dept_router
from core.dict.api import router as dict_router
from core.dict_item.api import router as dict_item_router
from core.menu.api import router as menu_router
from core.permission.api import router as permission_router
from core.post.api import router as post_router
from core.role.api import router as role_router
from core.user.api import router as user_router
from core.file_manager.router import router as file_manager_router
from core.redis_monitor.api import router as redis_monitor_router
from core.server_monitor.api import router as server_monitor_router
from core.database_monitor.api import router as database_monitor_router
from core.redis_manager.api import router as redis_manager_router
from core.database_manager.api import router as database_manager_router
from core.message.api import router as message_router
from core.message.api import announcement_router
from core.page_manager.api import router as page_manager_router
from core.login_log.api import router as login_log_router
from core.data_source.api import router as data_source_router
from core.oauth.api import router as oauth_router
from core.feature_analysis.api import router as feature_analysis_router
from core.issues_analysis.api import router as issues_analysis_router

router = APIRouter()

# 注册子模块路由
router.include_router(auth_router)
router.include_router(dept_router)
router.include_router(dict_router)
router.include_router(dict_item_router)
router.include_router(menu_router)
router.include_router(permission_router)
router.include_router(post_router)
router.include_router(role_router)
router.include_router(user_router)
router.include_router(file_manager_router)
router.include_router(redis_monitor_router)
router.include_router(server_monitor_router)
router.include_router(database_monitor_router)
router.include_router(redis_manager_router)
router.include_router(database_manager_router)
router.include_router(message_router)
router.include_router(announcement_router)
router.include_router(page_manager_router)
router.include_router(login_log_router)
router.include_router(data_source_router)
router.include_router(oauth_router)
router.include_router(feature_analysis_router)
router.include_router(issues_analysis_router)
```

- [ ] **Step 2: 提交路由注册**

```bash
git add backend-fastapi/core/router.py
git commit -m "feat: 注册 issues_analysis 路由"
```

---

## Task 3: 修改 feature_analysis 模型新增字段

**Files:**
- Modify: `backend-fastapi/core/feature_analysis/model.py`

- [ ] **Step 1: 在模型中添加字段**

在 `backend-fastapi/core/feature_analysis/model.py` 的 `FeatureAnalysis` 类中添加字段：

在 `feature_bug_detail` 字段后添加：

```python
    feature_bug_introduce = Column(String(64), nullable=True, comment="修改引入数量")
```

- [ ] **Step 2: 修改 QualityEvaluationResponse**

在 `backend-fastapi/core/feature_analysis/schema.py` 中，`QualityEvaluationResponse` 已有 `bug_intro_count` 字段，但需要在 service 中关联新字段。

修改 `backend-fastapi/core/feature_analysis/service.py` 的 `get_quality_list` 方法：

找到 `bug_intro_count` 的赋值行：
```python
"bug_intro_count": None,
```

改为：
```python
"bug_intro_count": item.feature_bug_introduce,
```

- [ ] **Step 3: 提交模型修改**

```bash
git add backend-fastapi/core/feature_analysis/
git commit -m "feat: feature_analysis 表新增修改引入数量字段"
```

---

## Task 4: 创建数据库迁移文件

**Files:**
- Create: `backend-fastapi/alembic/versions/xxx_add_issues_analysis_and_bug_introduce.py`

- [ ] **Step 1: 生成迁移文件**

```bash
cd backend-fastapi
alembic revision --autogenerate -m "add issues_analysis table and feature_bug_introduce field"
```

- [ ] **Step 2: 执行迁移**

```bash
alembic upgrade head
```

- [ ] **Step 3: 提交迁移文件**

```bash
git add backend-fastapi/alembic/versions/
git commit -m "feat: 添加数据库迁移文件"
```

---

## Task 5: 更新菜单初始化脚本

**Files:**
- Modify: `backend-fastapi/scripts/init_feature_analysis_menu.py`

- [ ] **Step 1: 更新修改引入问题菜单的 component 字段**

在 `backend-fastapi/scripts/init_feature_analysis_menu.py` 中，找到创建 `bug_menu` 的部分（约第99-114行），修改如下：

**修改1**：新建菜单时的 component 字段

将第106行：
```python
component="",
```

改为：
```python
component="feature-analysis/bug-intro/index",
```

**修改2**：替换已存在菜单的 else 分支（第113-114行）

将：
```python
else:
    print("菜单已存在：修改引入问题")
```

改为：
```python
else:
    # 更新已存在菜单的 component 字段
    bug_menu.component = "feature-analysis/bug-intro/index"
    print("更新菜单：修改引入问题")
```

- [ ] **Step 2: 提交脚本修改**

```bash
git add backend-fastapi/scripts/init_feature_analysis_menu.py
git commit -m "feat: 更新修改引入问题菜单配置"
```

---

## Task 6: 创建前端 API 接口定义

**Files:**
- Create: `web/apps/web-ele/src/api/core/issues-analysis.ts`

- [ ] **Step 1: 创建 API 文件**

创建 `web/apps/web-ele/src/api/core/issues-analysis.ts`：

```typescript
/**
 * 问题分析 API
 */
import { requestClient } from '#/api/request';

const BASE_URL = '/api/core/issues-analysis';

// 类型定义
export interface IssuesAnalysisItem {
  id: string;
  issuesId: string | null;
  issuesTitle: string | null;
  issuesServices: string | null;
  issuesOwner: string | null;
  issuesTestOwner: string | null;
  issuesSeverity: string | null;
  issuesProbability: string | null;
  issuesStatus: string | null;
  issuesVersion: string | null;
  featureId: string | null;
  featureDesc: string | null;
  syncTime: string | null;
  createBy: string | null;
  createTime: string | null;
  modifyTime: string | null;
}

export interface IssuesListParams {
  page?: number;
  pageSize?: number;
  version?: string;
  featureDesc?: string;
  issuesOwner?: string;
  issuesSeverity?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

export interface VersionListResponse {
  items: string[];
}

// API 接口

/**
 * 获取问题列表
 */
export async function getIssuesListApi(params: IssuesListParams): Promise<PaginatedResponse<IssuesAnalysisItem>> {
  return requestClient.get(BASE_URL, { params });
}

/**
 * 获取版本列表
 */
export async function getIssuesVersionsApi(): Promise<VersionListResponse> {
  return requestClient.get(`${BASE_URL}/versions`);
}

/**
 * 获取责任人列表
 */
export async function getIssuesOwnersApi(): Promise<VersionListResponse> {
  return requestClient.get(`${BASE_URL}/owners`);
}

/**
 * 获取严重程度列表
 */
export async function getIssuesSeveritiesApi(): Promise<VersionListResponse> {
  return requestClient.get(`${BASE_URL}/severities`);
}
```

- [ ] **Step 2: 提交 API 文件**

```bash
git add web/apps/web-ele/src/api/core/issues-analysis.ts
git commit -m "feat: 创建 issues-analysis 前端 API 接口"
```

---

## Task 7: 创建前端页面组件

**Files:**
- Create: `web/apps/web-ele/src/views/feature-analysis/bug-intro/index.vue`
- Create: `web/apps/web-ele/src/views/feature-analysis/bug-intro/components/FilterBar.vue`
- Create: `web/apps/web-ele/src/views/feature-analysis/bug-intro/components/IssuesTable.vue`

- [ ] **Step 1: 创建主页面 index.vue**

创建 `web/apps/web-ele/src/views/feature-analysis/bug-intro/index.vue`：

```vue
<script setup lang="ts">
import { ref } from 'vue';

import { Page } from '@vben/common-ui';

import FilterBar, { type FilterParams } from './components/FilterBar.vue';
import IssuesTable from './components/IssuesTable.vue';

defineOptions({ name: 'FeatureBugIntro' });

const filterParams = ref<FilterParams>({});
</script>

<template>
  <Page auto-content-height>
    <div class="feature-bug-intro p-4">
      <!-- 筛选区域 -->
      <FilterBar v-model="filterParams" />

      <!-- 数据表格区域 -->
      <div class="mt-4">
        <IssuesTable :filter-params="filterParams" />
      </div>
    </div>
  </Page>
</template>

<style scoped>
.feature-bug-intro {
  height: 100%;
  overflow-y: auto;
}
</style>
```

- [ ] **Step 2: 创建筛选栏 FilterBar.vue**

创建 `web/apps/web-ele/src/views/feature-analysis/bug-intro/components/FilterBar.vue`：

```vue
<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';

import { ElSelect, ElOption, ElInput } from 'element-plus';

import {
  getIssuesVersionsApi,
  getIssuesOwnersApi,
  getIssuesSeveritiesApi,
} from '#/api/core/issues-analysis';

defineOptions({ name: 'BugIntroFilterBar' });

export interface FilterParams {
  version?: string;
  featureDesc?: string;
  issuesOwner?: string;
  issuesSeverity?: string;
}

const props = defineProps<{
  modelValue: FilterParams;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: FilterParams];
}>();

const versions = ref<string[]>([]);
const owners = ref<string[]>([]);
const severities = ref<string[]>([]);
const loading = ref(false);

const localParams = ref<FilterParams>({ ...props.modelValue });

// 加载下拉选项
async function loadOptions() {
  loading.value = true;
  try {
    const [versionsRes, ownersRes, severitiesRes] = await Promise.all([
      getIssuesVersionsApi(),
      getIssuesOwnersApi(),
      getIssuesSeveritiesApi(),
    ]);
    versions.value = versionsRes.items || [];
    owners.value = ownersRes.items || [];
    severities.value = severitiesRes.items || [];
  } catch (error) {
    console.error('加载选项失败:', error);
  } finally {
    loading.value = false;
  }
}

// 更新筛选条件
function updateFilter(key: keyof FilterParams, value: string | undefined) {
  localParams.value = { ...localParams.value, [key]: value || undefined };
  emit('update:modelValue', localParams.value);
}

watch(
  () => props.modelValue,
  (val) => {
    localParams.value = { ...val };
  },
  { deep: true }
);

onMounted(() => {
  loadOptions();
});
</script>

<template>
  <div class="filter-bar flex flex-wrap items-center gap-4">
    <div class="flex items-center gap-2">
      <span class="text-sm text-gray-600">版本：</span>
      <ElSelect
        v-model="localParams.version"
        placeholder="请选择版本"
        clearable
        :loading="loading"
        style="width: 180px"
        @change="(val: string | undefined) => updateFilter('version', val)"
      >
        <ElOption
          v-for="version in versions"
          :key="version"
          :label="version"
          :value="version"
        />
      </ElSelect>
    </div>

    <div class="flex items-center gap-2">
      <span class="text-sm text-gray-600">需求标题：</span>
      <ElInput
        v-model="localParams.featureDesc"
        placeholder="请输入需求标题"
        clearable
        style="width: 180px"
        @blur="() => emit('update:modelValue', { ...localParams })"
        @clear="() => updateFilter('featureDesc', undefined)"
      />
    </div>

    <div class="flex items-center gap-2">
      <span class="text-sm text-gray-600">责任人：</span>
      <ElSelect
        v-model="localParams.issuesOwner"
        placeholder="请选择责任人"
        clearable
        :loading="loading"
        style="width: 150px"
        @change="(val: string | undefined) => updateFilter('issuesOwner', val)"
      >
        <ElOption
          v-for="owner in owners"
          :key="owner"
          :label="owner"
          :value="owner"
        />
      </ElSelect>
    </div>

    <div class="flex items-center gap-2">
      <span class="text-sm text-gray-600">严重程度：</span>
      <ElSelect
        v-model="localParams.issuesSeverity"
        placeholder="请选择严重程度"
        clearable
        :loading="loading"
        style="width: 150px"
        @change="(val: string | undefined) => updateFilter('issuesSeverity', val)"
      >
        <ElOption
          v-for="severity in severities"
          :key="severity"
          :label="severity"
          :value="severity"
        />
      </ElSelect>
    </div>
  </div>
</template>

<style scoped>
.filter-bar {
  padding: 12px 0;
}
</style>
```

- [ ] **Step 3: 创建表格组件 IssuesTable.vue**

创建 `web/apps/web-ele/src/views/feature-analysis/bug-intro/components/IssuesTable.vue`：

```vue
<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';

import { ElTable, ElTableColumn, ElPagination } from 'element-plus';

import type { IssuesAnalysisItem } from '#/api/core/issues-analysis';
import { getIssuesListApi } from '#/api/core/issues-analysis';

defineOptions({ name: 'IssuesTable' });

export interface FilterParams {
  version?: string;
  featureDesc?: string;
  issuesOwner?: string;
  issuesSeverity?: string;
}

const props = defineProps<{
  filterParams: FilterParams;
}>();

const tableData = ref<IssuesAnalysisItem[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(20);
const loading = ref(false);

// 加载表格数据
async function loadTableData() {
  loading.value = true;
  try {
    const res = await getIssuesListApi({
      page: currentPage.value,
      pageSize: pageSize.value,
      ...props.filterParams,
    });
    tableData.value = res.items || [];
    total.value = res.total || 0;
  } catch (error) {
    console.error('加载表格数据失败:', error);
  } finally {
    loading.value = false;
  }
}

// 分页变更
function handlePageChange(page: number) {
  currentPage.value = page;
  loadTableData();
}

function handleSizeChange(size: number) {
  pageSize.value = size;
  currentPage.value = 1;
  loadTableData();
}

// 显示空值
function showEmpty(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') {
    return '-';
  }
  return String(value);
}

watch(
  () => props.filterParams,
  () => {
    currentPage.value = 1;
    loadTableData();
  },
  { deep: true }
);

onMounted(() => {
  loadTableData();
});
</script>

<template>
  <div class="issues-table">
    <ElTable
      v-loading="loading"
      :data="tableData"
      border
      stripe
      style="width: 100%"
    >
      <ElTableColumn
        prop="featureId"
        label="需求编号"
        width="150"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ showEmpty(row.featureId) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="featureDesc"
        label="需求名称"
        width="200"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ showEmpty(row.featureDesc) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesId"
        label="问题单"
        width="120"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesId) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesTitle"
        label="问题名称"
        min-width="200"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesTitle) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesServices"
        label="归属"
        width="100"
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesServices) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesOwner"
        label="责任人"
        width="100"
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesOwner) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesSeverity"
        label="严重程度"
        width="100"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesSeverity) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesProbability"
        label="重现概率"
        width="100"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesProbability) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesStatus"
        label="问题状态"
        width="100"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesStatus) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesVersion"
        label="发现版本"
        width="120"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesVersion) }}
        </template>
      </ElTableColumn>
    </ElTable>

    <div class="pagination-wrapper mt-4 flex justify-end">
      <ElPagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>

<style scoped>
.issues-table {
  background: white;
  border-radius: 8px;
}
</style>
```

- [ ] **Step 4: 提交前端页面**

```bash
git add web/apps/web-ele/src/views/feature-analysis/bug-intro/
git commit -m "feat: 创建修改引入问题页面组件"
```

---

## Task 8: 执行菜单初始化和验证

**Files:**
- Execute: 菜单初始化脚本

- [ ] **Step 1: 执行菜单初始化脚本**

```bash
cd backend-fastapi
python scripts/init_feature_analysis_menu.py
```

预期输出：
```
创建一级菜单：特性质量统计
菜单已存在：需求进展
更新菜单：需求质量评价
更新菜单：修改引入问题
菜单初始化完成！
```

- [ ] **Step 2: 启动后端服务验证 API**

```bash
cd backend-fastapi
python main.py
```

访问 http://localhost:8000/docs 验证以下接口：
- GET /api/core/issues-analysis
- GET /api/core/issues-analysis/versions
- GET /api/core/issues-analysis/owners
- GET /api/core/issues-analysis/severities

- [ ] **Step 3: 启动前端服务验证页面**

```bash
cd web
pnpm dev
```

访问修改引入问题页面验证：
- 筛选功能
- 表格显示
- 分页功能

- [ ] **Step 4: 提交所有更改**

```bash
git add .
git commit -m "feat: 完成修改引入问题页面开发"
```

---

## 文件变更清单

### 后端新增文件

| 文件 | 说明 |
|------|------|
| `core/issues_analysis/__init__.py` | 模块初始化 |
| `core/issues_analysis/model.py` | 数据库模型 |
| `core/issues_analysis/schema.py` | Pydantic Schema |
| `core/issues_analysis/service.py` | 业务逻辑 |
| `core/issues_analysis/api.py` | API 路由 |

### 后端修改文件

| 文件 | 说明 |
|------|------|
| `core/router.py` | 注册 issues_analysis 路由 |
| `core/feature_analysis/model.py` | 新增 feature_bug_introduce 字段 |
| `core/feature_analysis/service.py` | 关联 bug_intro_count 字段 |
| `scripts/init_feature_analysis_menu.py` | 更新菜单配置 |

### 前端新增文件

| 文件 | 说明 |
|------|------|
| `api/core/issues-analysis.ts` | API 接口定义 |
| `views/feature-analysis/bug-intro/index.vue` | 主页面 |
| `views/feature-analysis/bug-intro/components/FilterBar.vue` | 筛选栏组件 |
| `views/feature-analysis/bug-intro/components/IssuesTable.vue` | 问题表格组件 |