# 需求质量评价页面与筛选增强实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现需求质量评价页面和需求进展页面筛选增强功能

**Architecture:** 后端新增质量评价 API 和筛选增强 API，前端新建需求质量评价页面并增强需求进展页面的筛选和排序功能

**Tech Stack:** FastAPI, SQLAlchemy, Vue 3, Element Plus, TypeScript

**Spec:** `docs/superpowers/specs/2026-03-22-feature-quality-eval-design.md`

---

## 文件结构

### 后端文件
| 文件 | 操作 | 说明 |
|------|------|------|
| `backend-fastapi/core/feature_analysis/schema.py` | 修改 | 新增 QualityEvaluationResponse |
| `backend-fastapi/core/feature_analysis/service.py` | 修改 | 新增质量评价查询、筛选逻辑、延期天数计算 |
| `backend-fastapi/core/feature_analysis/api.py` | 修改 | 新增/修改接口 |

### 前端文件
| 文件 | 操作 | 说明 |
|------|------|------|
| `web/apps/web-ele/src/api/core/feature-analysis.ts` | 修改 | 新增 API 接口定义 |
| `web/apps/web-ele/src/views/feature-analysis/eval/index.vue` | 新建 | 需求质量评价主页面 |
| `web/apps/web-ele/src/views/feature-analysis/eval/components/FilterBar.vue` | 新建 | 筛选栏组件 |
| `web/apps/web-ele/src/views/feature-analysis/eval/components/QualityTable.vue` | 新建 | 质量评价表格组件 |
| `web/apps/web-ele/src/views/feature-analysis/progress/index.vue` | 修改 | 重构筛选条件状态管理 |
| `web/apps/web-ele/src/views/feature-analysis/progress/components/FilterBar.vue` | 修改 | 增强筛选功能 |
| `web/apps/web-ele/src/views/feature-analysis/progress/components/FeatureTable.vue` | 修改 | 支持新筛选参数和排序 |
| `backend-fastapi/scripts/init_feature_analysis_menu.py` | 修改 | 更新菜单配置 |

---

## Task 1: 后端 Schema 新增 QualityEvaluationResponse

**Files:**
- Modify: `backend-fastapi/core/feature_analysis/schema.py`

- [ ] **Step 1: 新增 QualityEvaluationResponse 类**

在 `schema.py` 文件末尾添加：

```python
class QualityEvaluationResponse(BaseModel):
    """需求质量评价响应"""
    id: str
    feature_id: Optional[str] = Field(None, alias="featureId", description="需求编号")
    feature_desc: Optional[str] = Field(None, alias="featureDesc", description="特性名称")
    feature_owner: Optional[str] = Field(None, alias="featureOwner", description="责任人")
    delay_days: Optional[int] = Field(None, alias="delayDays", description="延期天数")
    test_count: Optional[str] = Field(None, alias="testCount", description="需求转测次数")
    bug_total: Optional[str] = Field(None, alias="bugTotal", description="问题单总数")
    bug_serious: Optional[str] = Field(None, alias="bugSerious", description="严重问题数量")
    bug_intro_count: Optional[str] = Field(None, alias="bugIntroCount", description="修改引入数量")
    code_lines: Optional[str] = Field(None, alias="codeLines", description="新增代码量")
    quality_judge: Optional[str] = Field(None, alias="qualityJudge", description="特性质量评价")

    class Config:
        populate_by_name = True
        from_attributes = True
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/feature_analysis/schema.py
git commit -m "feat: 新增 QualityEvaluationResponse Schema"
```

---

## Task 2: 后端 Service 新增方法和延期天数计算

**Files:**
- Modify: `backend-fastapi/core/feature_analysis/service.py`

- [ ] **Step 1: 新增延期天数计算函数**

在 `FeatureAnalysisService` 类中添加静态方法：

```python
from datetime import datetime
from typing import Optional, List, Tuple, Any

@staticmethod
def parse_date(date_str: str) -> datetime:
    """
    解析日期字符串，支持多种格式

    :param date_str: 日期字符串
    :return: datetime 对象
    :raises ValueError: 无法解析时抛出
    """
    formats = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析日期: {date_str}")


@staticmethod
def calculate_delay_days(expect_time: Optional[str], actual_time: Optional[str]) -> Optional[int]:
    """
    计算延期天数

    :param expect_time: 预计转测时间
    :param actual_time: 实际转测时间
    :return: 延期天数（正数表示延期，负数表示提前，None表示无法计算）
    """
    if not expect_time or not actual_time:
        return None

    try:
        expect_date = FeatureAnalysisService.parse_date(expect_time)
        actual_date = FeatureAnalysisService.parse_date(actual_time)
        delta = actual_date - expect_date
        return delta.days
    except Exception:
        return None
```

- [ ] **Step 2: 新增 get_quality_list 方法**

> **注意**：延期天数为计算字段，无法在 SQL 层面排序。采用方案：**获取数据后在 Python 层排序**（适用于中等数据量）。

```python
from sqlalchemy import case

@classmethod
async def get_quality_list(
    cls,
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    version: Optional[str] = None,
    feature_id: Optional[str] = None,
    feature_desc: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None
) -> Tuple[List[dict], int]:
    """
    获取质量评价列表

    :param db: 数据库会话
    :param page: 页码
    :param page_size: 每页数量
    :param version: 版本筛选
    :param feature_id: FE编号筛选（模糊匹配）
    :param feature_desc: FE名称筛选（模糊匹配）
    :param sort_by: 排序字段
    :param sort_order: 排序方式
    :return: (数据列表, 总数)
    """
    # 构建基础查询
    query = select(FeatureAnalysis).where(FeatureAnalysis.is_deleted == False)  # noqa: E712

    # 筛选条件（处理空字符串）
    if version and version.strip():
        query = query.where(FeatureAnalysis.feature_version == version)
    if feature_id and feature_id.strip():
        query = query.where(FeatureAnalysis.feature_id.like(f"%{feature_id}%"))
    if feature_desc and feature_desc.strip():
        query = query.where(FeatureAnalysis.feature_desc.like(f"%{feature_desc}%"))

    # 获取总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    items = result.scalars().all()

    # 构建响应数据
    response_items = []
    for item in items:
        item_dict = {
            "id": item.id,
            "feature_id": item.feature_id,
            "feature_desc": item.feature_desc,
            "feature_owner": item.feature_owner,
            "delay_days": cls.calculate_delay_days(
                item.feature_test_expect_time,
                item.feature_test_start_time
            ),
            "test_count": item.feature_test_count,
            "bug_total": item.feature_bug_total,
            "bug_serious": item.feature_bug_serious,
            "bug_intro_count": None,  # 预留字段
            "code_lines": item.feature_code,
            "quality_judge": item.feature_judge,
        }
        response_items.append(item_dict)

    # Python 层排序（处理计算字段）
    if sort_by and sort_order:
        reverse = sort_order == "desc"

        def get_sort_value(item: dict):
            val = item.get(sort_by)
            # 处理 None 值，排序时放到最后
            if val is None:
                return float('inf') if reverse else float('-inf')
            # 尝试数值排序
            try:
                return int(val) if isinstance(val, str) else val
            except (ValueError, TypeError):
                return val

        response_items.sort(key=get_sort_value, reverse=reverse)

    return response_items, total
```

- [ ] **Step 3: 新增 get_list_with_filters 方法（筛选增强）**

```python
from sqlalchemy import case

@classmethod
async def get_list_with_filters(
    cls,
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    version: Optional[str] = None,
    feature_id_father: Optional[str] = None,
    feature_id: Optional[str] = None,
    feature_owner: Optional[str] = None,
    feature_task_service: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None
) -> Tuple[List[FeatureAnalysis], int]:
    """
    获取列表（支持多条件筛选）

    :param db: 数据库会话
    :param page: 页码
    :param page_size: 每页数量
    :param version: 版本筛选
    :param feature_id_father: EP编号筛选（模糊匹配）
    :param feature_id: FE编号筛选（模糊匹配）
    :param feature_owner: 测试责任人筛选（精确匹配）
    :param feature_task_service: 测试归属筛选（精确匹配）
    :param sort_by: 排序字段
    :param sort_order: 排序方式
    :return: (数据列表, 总数)
    """
    # 构建基础查询
    query = select(FeatureAnalysis).where(FeatureAnalysis.is_deleted == False)  # noqa: E712

    # 筛选条件（处理空字符串）
    if version and version.strip():
        query = query.where(FeatureAnalysis.feature_version == version)
    if feature_id_father and feature_id_father.strip():
        query = query.where(FeatureAnalysis.feature_id_father.like(f"%{feature_id_father}%"))
    if feature_id and feature_id.strip():
        query = query.where(FeatureAnalysis.feature_id.like(f"%{feature_id}%"))
    if feature_owner and feature_owner.strip():
        query = query.where(FeatureAnalysis.feature_owner == feature_owner)
    if feature_task_service and feature_task_service.strip():
        query = query.where(FeatureAnalysis.feature_task_service == feature_task_service)

    # 排序
    if sort_by and sort_order:
        if sort_by == "testStatus":
            # 测试状态排序：未开始(1) < 测试中(2) < 已完成(3)
            status_order = case(
                (FeatureAnalysis.feature_test_end_time.isnot(None), 3),  # 已完成
                (FeatureAnalysis.feature_test_start_time.isnot(None), 2),  # 测试中
                else_=1  # 未开始
            )
            if sort_order == "asc":
                query = query.order_by(status_order.asc())
            else:
                query = query.order_by(status_order.desc())
        else:
            # 其他字段排序
            sort_field_map = {
                "featureTestExpectTime": FeatureAnalysis.feature_test_expect_time,
                "featureTestStartTime": FeatureAnalysis.feature_test_start_time,
            }
            field = sort_field_map.get(sort_by)
            if field is not None:
                # 处理 NULL 值排序
                if sort_order == "asc":
                    query = query.order_by(field.asc().nulls_last())
                else:
                    query = query.order_by(field.desc().nulls_last())

    # 获取总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    items = result.scalars().all()

    return items, total
```

- [ ] **Step 4: 新增 get_owners 方法**

```python
@classmethod
async def get_owners(cls, db: AsyncSession) -> List[str]:
    """
    获取所有测试责任人列表（去重）

    :param db: 数据库会话
    :return: 责任人列表
    """
    result = await db.execute(
        select(distinct(FeatureAnalysis.feature_owner))
        .where(
            FeatureAnalysis.is_deleted == False,  # noqa: E712
            FeatureAnalysis.feature_owner.isnot(None),
            FeatureAnalysis.feature_owner != ''
        )
        .order_by(FeatureAnalysis.feature_owner)
    )
    owners = [row[0] for row in result.all()]
    return owners
```

- [ ] **Step 5: 新增 get_task_services 方法**

```python
@classmethod
async def get_task_services(cls, db: AsyncSession) -> List[str]:
    """
    获取所有测试归属列表（去重）

    :param db: 数据库会话
    :return: 测试归属列表
    """
    result = await db.execute(
        select(distinct(FeatureAnalysis.feature_task_service))
        .where(
            FeatureAnalysis.is_deleted == False,  # noqa: E712
            FeatureAnalysis.feature_task_service.isnot(None),
            FeatureAnalysis.feature_task_service != ''
        )
        .order_by(FeatureAnalysis.feature_task_service)
    )
    services = [row[0] for row in result.all()]
    return services
```

- [ ] **Step 6: 添加缺失的 import**

在文件顶部添加：

```python
from sqlalchemy import select, distinct, func
```

- [ ] **Step 7: 提交**

```bash
git add backend-fastapi/core/feature_analysis/service.py
git commit -m "feat: 新增质量评价查询和筛选增强方法"
```

---

## Task 3: 后端 API 新增和修改接口

**Files:**
- Modify: `backend-fastapi/core/feature_analysis/api.py`

- [ ] **Step 1: 新增 QualityEvaluationResponse import**

在文件顶部的 import 部分添加：

```python
from core.feature_analysis.schema import (
    FeatureAnalysisResponse,
    PieChartDataResponse,
    PieChartDataItem,
    VersionListResponse,
    QualityEvaluationResponse  # 新增
)
```

- [ ] **Step 2: 修改 get_feature_list 接口（筛选增强）**

替换现有的 `get_feature_list` 函数：

```python
@router.get("", response_model=PaginatedResponse[FeatureAnalysisResponse], summary="获取需求列表")
async def get_feature_list(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize", description="每页数量"),
    version: Optional[str] = Query(None, description="版本筛选"),
    feature_id_father: Optional[str] = Query(None, alias="featureIdFather", description="EP编号筛选"),
    feature_id: Optional[str] = Query(None, alias="featureId", description="FE编号筛选"),
    feature_owner: Optional[str] = Query(None, alias="featureOwner", description="测试责任人筛选"),
    feature_task_service: Optional[str] = Query(None, alias="featureTaskService", description="测试归属筛选"),
    sort_by: Optional[str] = Query(None, alias="sortBy", description="排序字段"),
    sort_order: Optional[str] = Query(None, alias="sortOrder", description="排序方式"),
    db: AsyncSession = Depends(get_db)
):
    """获取需求列表（分页，支持多条件筛选和排序）"""
    items, total = await FeatureAnalysisService.get_list_with_filters(
        db, page=page, page_size=page_size, version=version,
        feature_id_father=feature_id_father, feature_id=feature_id,
        feature_owner=feature_owner, feature_task_service=feature_task_service,
        sort_by=sort_by, sort_order=sort_order
    )

    response_items = []
    for item in items:
        item_dict = {
            "id": item.id,
            "featureIdFather": item.feature_id_father,
            "featureId": item.feature_id,
            "featureDesc": item.feature_desc,
            "featureOwner": item.feature_owner,
            "featureTaskService": item.feature_task_service,
            "featureSafeTest": item.feature_safe_test,
            "featureTestExpectTime": item.feature_test_expect_time,
            "featureTestStartTime": item.feature_test_start_time,
            "testStatus": item.get_test_status(),
            "featureProgress": item.feature_progress,
            "featureRisk": item.feature_risk,
        }
        response_items.append(FeatureAnalysisResponse(**item_dict))

    return PaginatedResponse(items=response_items, total=total)
```

- [ ] **Step 3: 新增质量评价接口**

在文件末尾添加：

```python
@router.get("/quality", response_model=PaginatedResponse[QualityEvaluationResponse], summary="获取质量评价列表")
async def get_quality_list(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize", description="每页数量"),
    version: Optional[str] = Query(None, description="版本筛选"),
    feature_id: Optional[str] = Query(None, alias="featureId", description="FE编号筛选"),
    feature_desc: Optional[str] = Query(None, alias="featureDesc", description="FE名称筛选"),
    sort_by: Optional[str] = Query(None, alias="sortBy", description="排序字段"),
    sort_order: Optional[str] = Query(None, alias="sortOrder", description="排序方式"),
    db: AsyncSession = Depends(get_db)
):
    """获取质量评价列表（分页，支持筛选和排序）"""
    items, total = await FeatureAnalysisService.get_quality_list(
        db, page=page, page_size=page_size, version=version,
        feature_id=feature_id, feature_desc=feature_desc,
        sort_by=sort_by, sort_order=sort_order
    )

    response_items = [QualityEvaluationResponse(**item) for item in items]
    return PaginatedResponse(items=response_items, total=total)
```

- [ ] **Step 4: 新增测试责任人列表接口**

```python
@router.get("/owners", response_model=VersionListResponse, summary="获取测试责任人列表")
async def get_owners(
    db: AsyncSession = Depends(get_db)
):
    """获取所有测试责任人列表（去重）"""
    owners = await FeatureAnalysisService.get_owners(db)
    return VersionListResponse(items=owners)
```

- [ ] **Step 5: 新增测试归属列表接口**

```python
@router.get("/task-services", response_model=VersionListResponse, summary="获取测试归属列表")
async def get_task_services(
    db: AsyncSession = Depends(get_db)
):
    """获取所有测试归属列表（去重）"""
    services = await FeatureAnalysisService.get_task_services(db)
    return VersionListResponse(items=services)
```

- [ ] **Step 6: 提交**

```bash
git add backend-fastapi/core/feature_analysis/api.py
git commit -m "feat: 新增质量评价接口和筛选增强接口"
```

---

## Task 4: 前端 API 接口定义

**Files:**
- Modify: `web/apps/web-ele/src/api/core/feature-analysis.ts`

- [ ] **Step 1: 新增 QualityEvaluationItem 类型定义**

在 `FeatureAnalysisItem` 接口后添加：

```typescript
export interface QualityEvaluationItem {
  id: string;
  featureId: string | null;
  featureDesc: string | null;
  featureOwner: string | null;
  delayDays: number | null;
  testCount: string | null;
  bugTotal: string | null;
  bugSerious: string | null;
  bugIntroCount: string | null;
  codeLines: string | null;
  qualityJudge: string | null;
}
```

- [ ] **Step 2: 修改 getFeatureListApi 参数**

替换现有的 `getFeatureListApi` 函数：

```typescript
/**
 * 获取需求列表
 */
export async function getFeatureListApi(params: {
  page?: number;
  pageSize?: number;
  version?: string;
  featureIdFather?: string;
  featureId?: string;
  featureOwner?: string;
  featureTaskService?: string;
  sortBy?: string;
  sortOrder?: string;
}): Promise<PaginatedResponse<FeatureAnalysisItem>> {
  return requestClient.get(BASE_URL, { params });
}
```

- [ ] **Step 3: 新增 getQualityListApi**

```typescript
/**
 * 获取质量评价列表
 */
export async function getQualityListApi(params: {
  page?: number;
  pageSize?: number;
  version?: string;
  featureId?: string;
  featureDesc?: string;
  sortBy?: string;
  sortOrder?: string;
}): Promise<PaginatedResponse<QualityEvaluationItem>> {
  return requestClient.get(`${BASE_URL}/quality`, { params });
}
```

- [ ] **Step 4: 新增 getOwnerListApi**

```typescript
/**
 * 获取测试责任人列表
 */
export async function getOwnerListApi(): Promise<{ items: string[] }> {
  return requestClient.get(`${BASE_URL}/owners`);
}
```

- [ ] **Step 5: 新增 getTaskServiceListApi**

```typescript
/**
 * 获取测试归属列表
 */
export async function getTaskServiceListApi(): Promise<{ items: string[] }> {
  return requestClient.get(`${BASE_URL}/task-services`);
}
```

- [ ] **Step 6: 提交**

```bash
git add web/apps/web-ele/src/api/core/feature-analysis.ts
git commit -m "feat: 新增质量评价和筛选增强 API 接口定义"
```

---

## Task 5: 新建需求质量评价页面 - FilterBar 组件

**Files:**
- Create: `web/apps/web-ele/src/views/feature-analysis/eval/components/FilterBar.vue`

- [ ] **Step 1: 创建 FilterBar.vue 组件**

```vue
<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';

import { ElSelect, ElOption, ElInput } from 'element-plus';

import { getVersionListApi } from '#/api/core/feature-analysis';

defineOptions({ name: 'EvalFilterBar' });

export interface FilterParams {
  version?: string;
  featureId?: string;
  featureDesc?: string;
}

const props = defineProps<{
  modelValue: FilterParams;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: FilterParams];
}>();

const versions = ref<string[]>([]);
const loading = ref(false);

const localParams = ref<FilterParams>({ ...props.modelValue });

// 加载版本列表
async function loadVersions() {
  loading.value = true;
  try {
    const res = await getVersionListApi();
    versions.value = res.items || [];
  } catch (error) {
    console.error('加载版本列表失败:', error);
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
  loadVersions();
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
      <span class="text-sm text-gray-600">FE编号：</span>
      <ElInput
        v-model="localParams.featureId"
        placeholder="请输入FE编号"
        clearable
        style="width: 180px"
        @blur="() => emit('update:modelValue', { ...localParams.value })"
        @clear="() => updateFilter('featureId', undefined)"
      />
    </div>

    <div class="flex items-center gap-2">
      <span class="text-sm text-gray-600">FE名称：</span>
      <ElInput
        v-model="localParams.featureDesc"
        placeholder="请输入FE名称"
        clearable
        style="width: 200px"
        @blur="() => emit('update:modelValue', { ...localParams.value })"
        @clear="() => updateFilter('featureDesc', undefined)"
      />
    </div>
  </div>
</template>

<style scoped>
.filter-bar {
  padding: 12px 0;
}
</style>
```

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/feature-analysis/eval/components/FilterBar.vue
git commit -m "feat: 新建需求质量评价页面 FilterBar 组件"
```

---

## Task 6: 新建需求质量评价页面 - QualityTable 组件

**Files:**
- Create: `web/apps/web-ele/src/views/feature-analysis/eval/components/QualityTable.vue`

- [ ] **Step 1: 创建 QualityTable.vue 组件**

```vue
<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';

import { ElTable, ElTableColumn, ElPagination } from 'element-plus';

import type { QualityEvaluationItem } from '#/api/core/feature-analysis';
import { getQualityListApi } from '#/api/core/feature-analysis';
import type { FilterParams } from './FilterBar.vue';

defineOptions({ name: 'QualityTable' });

const props = defineProps<{
  filterParams: FilterParams;
}>();

const tableData = ref<QualityEvaluationItem[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(20);
const loading = ref(false);

// 排序状态
const currentSort = ref<{ prop: string; order: string | null }>({
  prop: '',
  order: null,
});

// 加载表格数据
async function loadTableData() {
  loading.value = true;
  try {
    const sortBy = currentSort.value.prop || undefined;
    const sortOrder = currentSort.value.order
      ? currentSort.value.order === 'ascending' ? 'asc' : 'desc'
      : undefined;

    const res = await getQualityListApi({
      page: currentPage.value,
      pageSize: pageSize.value,
      ...props.filterParams,
      sortBy,
      sortOrder,
    });
    tableData.value = res.items || [];
    total.value = res.total || 0;
  } catch (error) {
    console.error('加载表格数据失败:', error);
  } finally {
    loading.value = false;
  }
}

// 排序变化
function handleSortChange({ prop, order }: { prop: string; order: string | null }) {
  currentSort.value = { prop, order };
  currentPage.value = 1;
  loadTableData();
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
  <div class="quality-table">
    <ElTable
      v-loading="loading"
      :data="tableData"
      border
      stripe
      style="width: 100%"
      @sort-change="handleSortChange"
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
        label="特性名称"
        min-width="200"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ showEmpty(row.featureDesc) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="featureOwner"
        label="责任人"
        width="100"
      >
        <template #default="{ row }">
          {{ showEmpty(row.featureOwner) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="delayDays"
        label="延期天数"
        width="100"
        sortable="custom"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.delayDays) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="testCount"
        label="需求转测次数"
        width="120"
        sortable="custom"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.testCount) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="bugTotal"
        label="问题单总数"
        width="100"
        sortable="custom"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.bugTotal) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="bugSerious"
        label="严重问题数量"
        width="120"
        sortable="custom"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.bugSerious) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="bugIntroCount"
        label="修改引入数量"
        width="120"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.bugIntroCount) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="codeLines"
        label="新增代码量"
        width="100"
        sortable="custom"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.codeLines) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="qualityJudge"
        label="特性质量评价"
        min-width="150"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ showEmpty(row.qualityJudge) }}
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
.quality-table {
  background: white;
  border-radius: 8px;
}
</style>
```

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/feature-analysis/eval/components/QualityTable.vue
git commit -m "feat: 新建需求质量评价页面 QualityTable 组件"
```

---

## Task 7: 新建需求质量评价页面 - 主页面

**Files:**
- Create: `web/apps/web-ele/src/views/feature-analysis/eval/index.vue`

- [ ] **Step 1: 创建 index.vue 主页面**

```vue
<script setup lang="ts">
import { ref } from 'vue';

import { Page } from '@vben/common-ui';

import FilterBar, { type FilterParams } from './components/FilterBar.vue';
import QualityTable from './components/QualityTable.vue';

defineOptions({ name: 'FeatureQualityEval' });

const filterParams = ref<FilterParams>({});
</script>

<template>
  <Page auto-content-height>
    <div class="feature-quality-eval p-4">
      <!-- 筛选区域 -->
      <FilterBar v-model="filterParams" />

      <!-- 数据表格区域 -->
      <div class="mt-4">
        <QualityTable :filter-params="filterParams" />
      </div>
    </div>
  </Page>
</template>

<style scoped>
.feature-quality-eval {
  height: 100%;
  overflow-y: auto;
}
</style>
```

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/feature-analysis/eval/index.vue
git commit -m "feat: 新建需求质量评价主页面"
```

---

## Task 8: 修改需求进展页面 - FilterBar 组件

**Files:**
- Modify: `web/apps/web-ele/src/views/feature-analysis/progress/components/FilterBar.vue`

- [ ] **Step 1: 重写 FilterBar.vue 组件**

```vue
<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';

import { ElSelect, ElOption, ElInput } from 'element-plus';

import { getVersionListApi, getOwnerListApi, getTaskServiceListApi } from '#/api/core/feature-analysis';

defineOptions({ name: 'FilterBar' });

export interface ProgressFilterParams {
  version?: string;
  featureIdFather?: string;
  featureId?: string;
  featureOwner?: string;
  featureTaskService?: string;
}

const props = defineProps<{
  modelValue: ProgressFilterParams;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: ProgressFilterParams];
}>();

const versions = ref<string[]>([]);
const owners = ref<string[]>([]);
const taskServices = ref<string[]>([]);
const loading = ref(false);

const localParams = ref<ProgressFilterParams>({ ...props.modelValue });

// 加载下拉选项数据
async function loadOptions() {
  loading.value = true;
  try {
    const [versionRes, ownerRes, taskServiceRes] = await Promise.all([
      getVersionListApi(),
      getOwnerListApi(),
      getTaskServiceListApi(),
    ]);
    versions.value = versionRes.items || [];
    owners.value = ownerRes.items || [];
    taskServices.value = taskServiceRes.items || [];
  } catch (error) {
    console.error('加载筛选选项失败:', error);
  } finally {
    loading.value = false;
  }
}

// 更新筛选条件
function updateFilter(key: keyof ProgressFilterParams, value: string | undefined) {
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
        style="width: 160px"
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
      <span class="text-sm text-gray-600">EP编号：</span>
      <ElInput
        v-model="localParams.featureIdFather"
        placeholder="请输入EP编号"
        clearable
        style="width: 150px"
        @blur="() => emit('update:modelValue', { ...localParams.value })"
        @clear="() => updateFilter('featureIdFather', undefined)"
      />
    </div>

    <div class="flex items-center gap-2">
      <span class="text-sm text-gray-600">FE编号：</span>
      <ElInput
        v-model="localParams.featureId"
        placeholder="请输入FE编号"
        clearable
        style="width: 150px"
        @blur="() => emit('update:modelValue', { ...localParams.value })"
        @clear="() => updateFilter('featureId', undefined)"
      />
    </div>

    <div class="flex items-center gap-2">
      <span class="text-sm text-gray-600">测试责任人：</span>
      <ElSelect
        v-model="localParams.featureOwner"
        placeholder="请选择"
        clearable
        filterable
        :loading="loading"
        style="width: 120px"
        @change="(val: string | undefined) => updateFilter('featureOwner', val)"
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
      <span class="text-sm text-gray-600">测试归属：</span>
      <ElSelect
        v-model="localParams.featureTaskService"
        placeholder="请选择"
        clearable
        filterable
        :loading="loading"
        style="width: 140px"
        @change="(val: string | undefined) => updateFilter('featureTaskService', val)"
      >
        <ElOption
          v-for="service in taskServices"
          :key="service"
          :label="service"
          :value="service"
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

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/feature-analysis/progress/components/FilterBar.vue
git commit -m "feat: 增强需求进展页面 FilterBar 组件"
```

---

## Task 9: 修改需求进展页面 - FeatureTable 组件

**Files:**
- Modify: `web/apps/web-ele/src/views/feature-analysis/progress/components/FeatureTable.vue`

- [ ] **Step 1: 修改 FeatureTable.vue 组件**

在 `<script setup>` 部分修改：

```vue
<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';

import { ElTable, ElTableColumn, ElTag, ElPagination } from 'element-plus';

import type { FeatureAnalysisItem } from '#/api/core/feature-analysis';
import { getFeatureListApi } from '#/api/core/feature-analysis';
import type { ProgressFilterParams } from './FilterBar.vue';

defineOptions({ name: 'FeatureTable' });

const props = defineProps<{
  filterParams: ProgressFilterParams;
}>();

const tableData = ref<FeatureAnalysisItem[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(20);
const loading = ref(false);

// 排序状态
const currentSort = ref<{ prop: string; order: string | null }>({
  prop: '',
  order: null,
});

// 加载表格数据
async function loadTableData() {
  loading.value = true;
  try {
    const sortBy = currentSort.value.prop || undefined;
    const sortOrder = currentSort.value.order
      ? currentSort.value.order === 'ascending' ? 'asc' : 'desc'
      : undefined;

    const res = await getFeatureListApi({
      page: currentPage.value,
      pageSize: pageSize.value,
      ...props.filterParams,
      sortBy,
      sortOrder,
    });
    tableData.value = res.items || [];
    total.value = res.total || 0;
  } catch (error) {
    console.error('加载表格数据失败:', error);
  } finally {
    loading.value = false;
  }
}

// 排序变化
function handleSortChange({ prop, order }: { prop: string; order: string | null }) {
  currentSort.value = { prop, order };
  currentPage.value = 1;
  loadTableData();
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

// 获取测试状态标签类型
function getStatusType(status: string): 'success' | 'warning' | 'info' {
  switch (status) {
    case '已完成':
      return 'success';
    case '测试中':
      return 'warning';
    default:
      return 'info';
  }
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
```

在 `<template>` 部分修改，添加排序功能：

```vue
<template>
  <div class="feature-table">
    <ElTable
      v-loading="loading"
      :data="tableData"
      border
      stripe
      style="width: 100%"
      @sort-change="handleSortChange"
    >
      <ElTableColumn
        prop="featureIdFather"
        label="父工作项编码号"
        width="150"
        show-overflow-tooltip
      />
      <ElTableColumn
        prop="featureId"
        label="需求编号"
        width="150"
        show-overflow-tooltip
      />
      <ElTableColumn
        prop="featureDesc"
        label="标题"
        min-width="200"
        show-overflow-tooltip
      />
      <ElTableColumn
        prop="featureOwner"
        label="测试责任人"
        width="100"
      />
      <ElTableColumn
        prop="featureTaskService"
        label="测试归属"
        width="100"
      />
      <ElTableColumn
        prop="featureSafeTest"
        label="涉及安全"
        width="80"
        align="center"
      />
      <ElTableColumn
        prop="featureTestExpectTime"
        label="预计转测时间"
        width="120"
        sortable="custom"
      />
      <ElTableColumn
        prop="featureTestStartTime"
        label="实际转测情况"
        width="120"
        sortable="custom"
      />
      <ElTableColumn
        prop="testStatus"
        label="测试状态"
        width="80"
        align="center"
        sortable="custom"
      >
        <template #default="{ row }">
          <ElTag :type="getStatusType(row.testStatus)" size="small">
            {{ row.testStatus }}
          </ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="featureProgress"
        label="测试进展"
        width="200"
        show-overflow-tooltip
      />
      <ElTableColumn
        prop="featureRisk"
        label="风险与关键问题"
        width="150"
        show-overflow-tooltip
      />
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
.feature-table {
  background: white;
  border-radius: 8px;
}
</style>
```

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/feature-analysis/progress/components/FeatureTable.vue
git commit -m "feat: 增强需求进展页面 FeatureTable 组件，支持筛选和排序"
```

---

## Task 10: 修改需求进展页面 - 主页面

**Files:**
- Modify: `web/apps/web-ele/src/views/feature-analysis/progress/index.vue`

- [ ] **Step 1: 修改 index.vue 主页面**

```vue
<script setup lang="ts">
import { ref } from 'vue';

import { Page } from '@vben/common-ui';

import FilterBar, { type ProgressFilterParams } from './components/FilterBar.vue';
import PieCharts from './components/PieCharts.vue';
import FeatureTable from './components/FeatureTable.vue';

defineOptions({ name: 'FeatureProgress' });

const filterParams = ref<ProgressFilterParams>({});
</script>

<template>
  <Page auto-content-height>
    <div class="feature-progress p-4">
      <!-- 筛选区域 -->
      <FilterBar v-model="filterParams" />

      <!-- 饼图区域 -->
      <PieCharts :version="filterParams.version" />

      <!-- 数据表格区域 -->
      <FeatureTable :filter-params="filterParams" />
    </div>
  </Page>
</template>

<style scoped>
.feature-progress {
  height: 100%;
  overflow-y: auto;
}
</style>
```

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/feature-analysis/progress/index.vue
git commit -m "feat: 修改需求进展主页面，支持多筛选条件"
```

---

## Task 11: 更新菜单配置

**Files:**
- Modify: `backend-fastapi/scripts/init_feature_analysis_menu.py`

- [ ] **Step 1: 修改菜单初始化脚本**

> **注意**：原脚本在菜单存在时会跳过，需要添加更新逻辑。

替换整个 `init_menus` 函数：

```python
async def init_menus():
    """初始化特性质量统计菜单"""
    async with AsyncSessionLocal() as db:
        try:
            # 检查一级菜单是否已存在
            result = await db.execute(
                select(Menu).where(Menu.name == "FeatureQuality")
            )
            parent_menu = result.scalar_one_or_none()

            if not parent_menu:
                # 创建一级菜单：特性质量统计
                parent_menu = Menu(
                    id="fq_catalog",
                    name="FeatureQuality",
                    title="特性质量统计",
                    path="/feature-quality",
                    type="catalog",
                    icon="lucide:chart-pie",
                    order=50,
                    hideInMenu=False,
                    hideChildrenInMenu=False,
                )
                db.add(parent_menu)
                await db.flush()
                print("创建一级菜单：特性质量统计")

            # 检查并更新/创建需求进展菜单
            result = await db.execute(
                select(Menu).where(Menu.name == "FeatureProgress")
            )
            progress_menu = result.scalar_one_or_none()
            if not progress_menu:
                progress_menu = Menu(
                    id="fq_progress",
                    name="FeatureProgress",
                    title="需求进展",
                    path="/feature-quality/progress",
                    type="menu",
                    component="feature-analysis/progress/index",
                    parent_id=parent_menu.id,
                    order=1,
                    hideInMenu=False,
                )
                db.add(progress_menu)
                print("创建菜单：需求进展")
            else:
                print("菜单已存在：需求进展")

            # 检查并更新/创建需求质量评价菜单
            result = await db.execute(
                select(Menu).where(Menu.name == "FeatureQualityEval")
            )
            eval_menu = result.scalar_one_or_none()
            if not eval_menu:
                eval_menu = Menu(
                    id="fq_eval",
                    name="FeatureQualityEval",
                    title="需求质量评价",
                    path="/feature-quality/eval",
                    type="menu",
                    component="feature-analysis/eval/index",
                    parent_id=parent_menu.id,
                    order=2,
                    hideInMenu=False,
                )
                db.add(eval_menu)
                print("创建菜单：需求质量评价")
            else:
                # 更新已存在菜单的 component 字段
                eval_menu.component = "feature-analysis/eval/index"
                print("更新菜单：需求质量评价")

            # 检查并更新/创建修改引入问题菜单
            result = await db.execute(
                select(Menu).where(Menu.name == "FeatureBugIntro")
            )
            bug_menu = result.scalar_one_or_none()
            if not bug_menu:
                bug_menu = Menu(
                    id="fq_bug",
                    name="FeatureBugIntro",
                    title="修改引入问题",
                    path="/feature-quality/bug-intro",
                    type="menu",
                    component="",
                    parent_id=parent_menu.id,
                    order=3,
                    hideInMenu=False,
                )
                db.add(bug_menu)
                print("创建菜单：修改引入问题")
            else:
                print("菜单已存在：修改引入问题")

            await db.commit()
            print("菜单初始化完成！")

        except Exception as e:
            await db.rollback()
            print(f"初始化失败: {e}")
            raise
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/scripts/init_feature_analysis_menu.py
git commit -m "feat: 更新需求质量评价菜单配置"
```

---

## Task 12: 验证和最终提交

- [ ] **Step 1: 检查后端代码**

```bash
cd backend-fastapi && python -c "from core.feature_analysis.api import router; print('Backend OK')"
```

- [ ] **Step 2: 检查前端代码**

```bash
cd web && pnpm check:type
```

- [ ] **Step 3: 最终提交（如有遗漏）**

```bash
git add -A
git status
```

---

## 验证清单

- [ ] 后端 API 可正常访问
- [ ] 前端页面可正常渲染
- [ ] 筛选功能正常工作
- [ ] 排序功能正常工作
- [ ] 分页功能正常工作
- [ ] 延期天数正确计算
- [ ] 菜单正确显示新页面