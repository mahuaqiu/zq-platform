# 需求质量评价页面与筛选增强设计

## 概述

本设计包含两个独立任务：
1. **需求质量评价页面**：新建页面展示需求质量评价表格
2. **需求进展页面筛选增强**：在现有筛选基础上新增4个筛选字段

## 任务一：需求质量评价页面

### 1.1 前端结构

新建页面目录：

```
views/feature-analysis/eval/
├── index.vue              # 主页面
└── components/
    ├── FilterBar.vue      # 筛选栏（版本、FE编号、FE名称）
    └── QualityTable.vue   # 质量评价表格
```

### 1.2 页面布局

```
┌─────────────────────────────────────────────────────────────┐
│ 筛选区域                                                    │
│ [版本: 下拉选择] [FE编号: 输入框] [FE名称: 输入框]          │
├─────────────────────────────────────────────────────────────┤
│ 数据表格                                                    │
│ ┌─────────┬────────┬──────┬────────┬────────┬────────┬...  │
│ │需求编号 │特性名称│责任人│延期天数│转测次数│问题单数│      │
│ ├─────────┼────────┼──────┼────────┼────────┼────────┤      │
│ │ FE001   │特性A   │张三  │ 3      │ 2      │ 5      │      │
│ └─────────┴────────┴──────┴────────┴────────┴────────┴...  │
├─────────────────────────────────────────────────────────────┤
│ 分页                                                        │
│                                    [共 100 条] [1][2][3]... │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 表格字段定义

| 列名 | 字段名 | 数据来源 | 宽度 |
|------|--------|----------|------|
| 需求编号 | featureId | feature_id | 150px |
| 特性名称 | featureDesc | feature_desc | 自适应 |
| 责任人 | featureOwner | feature_owner | 100px |
| 延期天数 | delayDays | 计算字段 | 100px |
| 需求转测次数 | testCount | feature_test_count | 120px |
| 问题单总数 | bugTotal | feature_bug_total | 100px |
| 严重问题数量 | bugSerious | feature_bug_serious | 120px |
| 修改引入数量 | bugIntroCount | 预留字段（暂为空） | 120px |
| 新增代码量 | codeLines | feature_code | 100px |
| 特性质量评价 | qualityJudge | feature_judge | 自适应 |

### 1.4 后端 API 设计

**接口路径**：`GET /api/core/feature-analysis/quality`

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，默认 1，最小 1 |
| pageSize | int | 否 | 每页数量，默认 20，范围 1-100 |
| version | string | 否 | 版本筛选（精确匹配） |
| featureId | string | 否 | FE编号筛选（模糊匹配，包含匹配） |
| featureDesc | string | 否 | FE名称筛选（模糊匹配，包含匹配） |

**参数命名规则**：
- 前端使用驼峰命名（如 `featureId`）
- 后端使用 `Query` 参数配合 `alias` 进行转换
- 空字符串参数等同于未传参，不作为筛选条件

**响应格式**：

```json
{
  "items": [
    {
      "id": "uuid",
      "featureId": "FE001",
      "featureDesc": "特性描述",
      "featureOwner": "张三",
      "delayDays": 3,
      "testCount": "2",
      "bugTotal": "5",
      "bugSerious": "1",
      "bugIntroCount": null,
      "codeLines": "1000",
      "qualityJudge": "质量评价内容"
    }
  ],
  "total": 100
}
```

### 1.5 延期天数计算逻辑

后端计算，前端直接展示：

```python
from datetime import datetime
from typing import Optional

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


def calculate_delay_days(expect_time: str, actual_time: str) -> Optional[int]:
    """
    计算延期天数

    :param expect_time: 预计转测时间 (feature_test_expect_time)
    :param actual_time: 实际转测时间 (feature_test_start_time)
    :return: 延期天数（正数表示延期，负数表示提前，None表示无法计算）
    """
    if not expect_time or not actual_time:
        return None

    try:
        expect_date = parse_date(expect_time)
        actual_date = parse_date(actual_time)
        delta = actual_date - expect_date
        return delta.days
    except Exception:
        return None
```

**空值处理**：
- 当 `delayDays` 为 `null` 时，前端表格显示 `-`
- 当 `bugIntroCount` 为 `null` 时，前端表格显示 `-`

### 1.6 后端 Schema 定义

在 `core/feature_analysis/schema.py` 中新增：

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

### 1.7 前端 API 定义

在 `api/core/feature-analysis.ts` 中新增：

```typescript
// 类型定义
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

// API 接口
export async function getQualityListApi(params: {
  page?: number;
  pageSize?: number;
  version?: string;
  featureId?: string;
  featureDesc?: string;
}): Promise<PaginatedResponse<QualityEvaluationItem>> {
  return requestClient.get(`${BASE_URL}/quality`, { params });
}
```

---

## 任务二：需求进展页面筛选增强

### 2.1 现有筛选

| 筛选项 | 字段 | 类型 |
|--------|------|------|
| 版本 | feature_version | 下拉选择 |

### 2.2 新增筛选

| 筛选项 | 字段 | 类型 | 筛选方式 |
|--------|------|------|----------|
| EP编号 | feature_id_father | 输入框 | 模糊匹配 |
| FE编号 | feature_id | 输入框 | 模糊匹配 |
| 测试责任人 | feature_owner | 下拉选择 | 精确匹配 |
| 测试归属 | feature_task_service | 下拉选择 | 精确匹配 |

### 2.3 筛选栏布局

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ [版本 ▼] [EP编号    ] [FE编号    ] [测试责任人 ▼] [测试归属 ▼]              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.4 后端 API 修改

修改现有接口 `GET /api/core/feature-analysis`，新增查询参数：

| 参数 | 类型 | 说明 |
|------|------|------|
| featureIdFather | string | EP编号筛选（模糊匹配，包含匹配） |
| featureId | string | FE编号筛选（模糊匹配，包含匹配） |
| featureOwner | string | 测试责任人筛选（精确匹配） |
| featureTaskService | string | 测试归属筛选（精确匹配） |

**后端参数定义示例**：

```python
@router.get("", response_model=PaginatedResponse[FeatureAnalysisResponse])
async def get_feature_list(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    version: Optional[str] = Query(None),
    feature_id_father: Optional[str] = Query(None, alias="featureIdFather"),
    feature_id: Optional[str] = Query(None, alias="featureId"),
    feature_owner: Optional[str] = Query(None, alias="featureOwner"),
    feature_task_service: Optional[str] = Query(None, alias="featureTaskService"),
    db: AsyncSession = Depends(get_db)
):
    ...
```

**筛选逻辑**：
- 模糊匹配：使用 SQL `LIKE '%keyword%'` 实现
- 精确匹配：使用 SQL `=` 实现
- 空字符串或 `None` 参数不作为筛选条件

### 2.5 新增后端接口

**获取测试责任人列表**：

`GET /api/core/feature-analysis/owners`

响应：
```json
{
  "items": ["张三", "李四", "王五"]
}
```

**获取测试归属列表**：

`GET /api/core/feature-analysis/task-services`

响应：
```json
{
  "items": ["开发一组", "开发二组", "测试组"]
}
```

### 2.6 前端组件修改

**FilterBar.vue 修改**：

1. 新增 props 支持多筛选条件
2. 新增 API 调用获取责任人/归属列表
3. 布局调整为横向排列 5 个筛选项
4. 使用 `v-model` 双向绑定筛选条件对象

**index.vue 修改**：

现有代码只传递 `version` 单个参数，需要重构为筛选条件对象：

```typescript
// 筛选条件对象
const filterParams = ref({
  version: undefined,
  featureIdFather: undefined,
  featureId: undefined,
  featureOwner: undefined,
  featureTaskService: undefined,
});
```

**FeatureTable.vue 修改**：

1. 修改 props 接收完整筛选条件对象
2. 监听筛选条件变化重新加载数据

### 2.7 前端 API 新增

在 `api/core/feature-analysis.ts` 中新增：

```typescript
// 获取测试责任人列表
export async function getOwnerListApi(): Promise<{ items: string[] }> {
  return requestClient.get(`${BASE_URL}/owners`);
}

// 获取测试归属列表
export async function getTaskServiceListApi(): Promise<{ items: string[] }> {
  return requestClient.get(`${BASE_URL}/task-services`);
}
```

修改 `getFeatureListApi` 参数类型：

```typescript
export async function getFeatureListApi(params: {
  page?: number;
  pageSize?: number;
  version?: string;
  featureIdFather?: string;  // 新增
  featureId?: string;         // 新增
  featureOwner?: string;      // 新增
  featureTaskService?: string; // 新增
}): Promise<PaginatedResponse<FeatureAnalysisItem>> {
  return requestClient.get(BASE_URL, { params });
}
```

---

## 实现文件清单

### 后端文件修改

| 文件 | 操作 | 说明 |
|------|------|------|
| `core/feature_analysis/api.py` | 修改 | 新增质量评价接口、筛选增强接口 |
| `core/feature_analysis/service.py` | 修改 | 新增质量评价查询、筛选逻辑、计算延期天数 |
| `core/feature_analysis/schema.py` | 修改 | 新增 QualityEvaluationResponse |

### 前端文件修改

| 文件 | 操作 | 说明 |
|------|------|------|
| `api/core/feature-analysis.ts` | 修改 | 新增 API 接口定义 |
| `views/feature-analysis/progress/index.vue` | 修改 | 重构筛选条件状态管理 |
| `views/feature-analysis/progress/components/FilterBar.vue` | 修改 | 增强筛选功能，新增4个筛选项 |
| `views/feature-analysis/progress/components/FeatureTable.vue` | 修改 | 支持新筛选参数 |
| `views/feature-analysis/progress/components/PieCharts.vue` | 修改 | 支持新筛选参数（如需要） |

### 前端文件新增

| 文件 | 说明 |
|------|------|
| `views/feature-analysis/eval/index.vue` | 需求质量评价主页面 |
| `views/feature-analysis/eval/components/FilterBar.vue` | 筛选栏组件 |
| `views/feature-analysis/eval/components/QualityTable.vue` | 质量评价表格组件 |

### 菜单配置

更新 `scripts/init_feature_analysis_menu.py` 中需求质量评价菜单的 component 字段：

```python
eval_menu = Menu(
    id="fq_eval",
    name="FeatureQualityEval",
    title="需求质量评价",
    path="/feature-quality/eval",
    type="menu",
    component="feature-analysis/eval/index",  # 更新此字段
    parent_id=parent_menu.id,
    order=2,
)
```

---

## 数据依赖

所有数据来源于 `feature_analysis` 表，字段映射：

| 显示名称 | 数据库字段 |
|----------|------------|
| 版本 | feature_version |
| EP编号 | feature_id_father |
| FE编号 | feature_id |
| FE名称 | feature_desc |
| 测试责任人 | feature_owner |
| 测试归属 | feature_task_service |
| 需求转测次数 | feature_test_count |
| 问题单总数 | feature_bug_total |
| 严重问题数量 | feature_bug_serious |
| 新增代码量 | feature_code |
| 特性质量评价 | feature_judge |
| 预计转测时间 | feature_test_expect_time |
| 实际转测时间 | feature_test_start_time |