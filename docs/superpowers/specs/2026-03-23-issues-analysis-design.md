# 修改引入问题页面设计文档

## 概述

本设计包含三个任务：
1. **新建 issues_analysis 表**：存储问题分析数据
2. **修改引入问题页面**：展示问题列表，固定筛选"修改引入"问题
3. **feature_analysis 表增加字段**：新增修改引入数量字段

---

## 任务一：新建 issues_analysis 表

### 1.1 表结构设计

```sql
CREATE TABLE issues_analysis (
    -- 主键与继承字段
    id VARCHAR(21) PRIMARY KEY,
    sort INTEGER DEFAULT 0,
    is_deleted BOOLEAN DEFAULT FALSE,
    sys_create_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sys_update_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sys_creator_id VARCHAR(21),
    sys_modifier_id VARCHAR(21),

    -- 业务字段
    issues_id VARCHAR(64),           -- 问题编号
    issues_title VARCHAR(64),        -- 问题名称
    issues_services VARCHAR(64),     -- 问题归属
    issues_owner VARCHAR(64),        -- 开发责任人
    issues_test_owner VARCHAR(64),   -- 测试责任人
    issues_severity VARCHAR(64),     -- 严重程度
    issues_probability VARCHAR(64),  -- 重现概率
    issues_status VARCHAR(64),       -- 问题状态
    issues_version VARCHAR(64),      -- 发现问题版本
    feature_id VARCHAR(64),          -- 关联需求ID（需求编号）
    feature_desc VARCHAR(64),        -- 需求名称
    sync_time VARCHAR(64),           -- 数据同步时间
    create_by VARCHAR(64),           -- 创建者
    create_time VARCHAR(64),         -- 创建时间
    modify_time VARCHAR(64),         -- 修改时间
);

-- 索引
CREATE INDEX idx_issues_version ON issues_analysis(issues_version);
CREATE INDEX idx_issues_deleted ON issues_analysis(is_deleted);
```

### 1.2 后端模块结构

```
backend-fastapi/core/issues_analysis/
├── __init__.py
├── model.py           # 数据库模型
├── schema.py          # Pydantic Schema
├── service.py         # 业务逻辑
└── api.py             # API 路由
```

### 1.3 后端模型定义

```python
# model.py
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

---

## 任务二：修改引入问题页面

### 2.1 页面布局

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ 筛选区域                                                                      │
│ [版本: 下拉选择] [需求标题: 输入框] [责任人: 下拉选择] [严重程度: 下拉选择]    │
│ [查询] [重置]                                                                │
├──────────────────────────────────────────────────────────────────────────────┤
│ 数据表格                                                                      │
│ ┌─────────┬────────┬────────┬────────┬──────┬────────┬────────┬────────┬... │
│ │需求编号 │需求名称│问题单  │问题名称│归属  │责任人  │严重程度│重现概率│     │
│ ├─────────┼────────┼────────┼────────┼──────┼────────┼────────┼────────┤     │
│ │FE001   │特性A   │ISS001  │修改引入│服务端│张三    │严重    │必现    │     │
│ └─────────┴────────┴────────┴────────┴──────┴────────┴────────┴────────┴... │
├──────────────────────────────────────────────────────────────────────────────┤
│ 分页                                                        [共 100 条] [...] │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 筛选条件

| 筛选项 | 字段 | 类型 | 匹配方式 |
|--------|------|------|----------|
| 版本 | issues_version | 下拉选择 | 精确匹配 |
| 需求标题 | feature_desc | 输入框 | 模糊匹配 |
| 责任人 | issues_owner | 下拉选择 | 精确匹配 |
| 严重程度 | issues_severity | 下拉选择 | 精确匹配 |

**固定查询条件**：问题标题（issues_title）包含"修改引入"，不在页面展示，后台自动添加。

### 2.3 表格字段定义

| 列名 | 字段名 | 数据来源 | 宽度 |
|------|--------|----------|------|
| 需求编号 | featureId | feature_id | 150px |
| 需求名称 | featureDesc | feature_desc | 200px |
| 问题单 | issuesId | issues_id | 120px |
| 问题名称 | issuesTitle | issues_title | 自适应 |
| 归属 | issuesServices | issues_services | 100px |
| 责任人 | issuesOwner | issues_owner | 100px |
| 严重程度 | issuesSeverity | issues_severity | 100px |
| 重现概率 | issuesProbability | issues_probability | 100px |
| 问题状态 | issuesStatus | issues_status | 100px |
| 发现版本 | issuesVersion | issues_version | 120px |

### 2.4 后端 API 设计

#### 2.4.1 获取问题列表

**接口**：`GET /api/core/issues-analysis`

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，默认 1 |
| pageSize | int | 否 | 每页数量，默认 20 |
| version | string | 否 | 版本筛选（精确匹配） |
| featureDesc | string | 否 | 需求标题（模糊匹配） |
| owner | string | 否 | 责任人（精确匹配） |
| severity | string | 否 | 严重程度（精确匹配） |

**固定条件**：`issues_title LIKE '%修改引入%'`

**响应格式**：

```json
{
  "items": [
    {
      "id": "uuid",
      "featureId": "FE001",
      "featureDesc": "特性名称",
      "issuesId": "ISS001",
      "issuesTitle": "修改引入-问题标题",
      "issuesServices": "服务端",
      "issuesOwner": "张三",
      "issuesSeverity": "严重",
      "issuesProbability": "必现",
      "issuesStatus": "待处理",
      "issuesVersion": "V1.0.0"
    }
  ],
  "total": 100
}
```

#### 2.4.2 获取责任人列表

**接口**：`GET /api/core/issues-analysis/owners`

**响应格式**：

```json
{
  "items": ["张三", "李四", "王五"]
}
```

#### 2.4.3 获取严重程度列表

**接口**：`GET /api/core/issues-analysis/severities`

**响应格式**：

```json
{
  "items": ["严重", "一般", "提示"]
}
```

#### 2.4.4 版本列表接口

复用现有接口：`GET /api/core/feature-analysis/versions`

### 2.5 后端 Schema 定义

```python
# schema.py
from pydantic import BaseModel, Field
from typing import Optional

class IssuesAnalysisResponse(BaseModel):
    """问题分析响应"""
    id: str
    feature_id: Optional[str] = Field(None, alias="featureId", description="需求编号")
    feature_desc: Optional[str] = Field(None, alias="featureDesc", description="需求名称")
    issues_id: Optional[str] = Field(None, alias="issuesId", description="问题单")
    issues_title: Optional[str] = Field(None, alias="issuesTitle", description="问题名称")
    issues_services: Optional[str] = Field(None, alias="issuesServices", description="归属")
    issues_owner: Optional[str] = Field(None, alias="issuesOwner", description="责任人")
    issues_severity: Optional[str] = Field(None, alias="issuesSeverity", description="严重程度")
    issues_probability: Optional[str] = Field(None, alias="issuesProbability", description="重现概率")
    issues_status: Optional[str] = Field(None, alias="issuesStatus", description="问题状态")
    issues_version: Optional[str] = Field(None, alias="issuesVersion", description="发现版本")

    class Config:
        populate_by_name = True
        from_attributes = True
```

### 2.6 前端组件结构

```
views/feature-analysis/bug-intro/
├── index.vue              # 主页面
└── components/
    ├── FilterBar.vue      # 筛选栏（版本、需求标题、责任人、严重程度）
    └── IssuesTable.vue    # 问题表格
```

### 2.7 前端 API 定义

```typescript
// api/core/issues-analysis.ts

export interface IssuesAnalysisItem {
  id: string;
  featureId: string | null;
  featureDesc: string | null;
  issuesId: string | null;
  issuesTitle: string | null;
  issuesServices: string | null;
  issuesOwner: string | null;
  issuesSeverity: string | null;
  issuesProbability: string | null;
  issuesStatus: string | null;
  issuesVersion: string | null;
}

export interface IssuesListParams {
  page?: number;
  pageSize?: number;
  version?: string;
  featureDesc?: string;
  owner?: string;
  severity?: string;
}

// 获取问题列表
export async function getIssuesListApi(params: IssuesListParams): Promise<PaginatedResponse<IssuesAnalysisItem>> {
  return requestClient.get(BASE_URL, { params });
}

// 获取责任人列表
export async function getIssuesOwnersApi(): Promise<{ items: string[] }> {
  return requestClient.get(`${BASE_URL}/owners`);
}

// 获取严重程度列表
export async function getIssuesSeveritiesApi(): Promise<{ items: string[] }> {
  return requestClient.get(`${BASE_URL}/severities`);
}
```

---

## 任务三：feature_analysis 表增加字段

### 3.1 字段定义

新增字段：`feature_bug_introduce VARCHAR(64)` - 修改引入数量

### 3.2 模型修改

在 `core/feature_analysis/model.py` 中新增：

```python
feature_bug_introduce = Column(String(64), nullable=True, comment="修改引入数量")
```

### 3.3 数据库迁移

创建迁移文件添加新字段。

### 3.4 前端显示

需求质量评价页面已预留 `bugIntroCount` 列（参见 2026-03-22-feature-quality-eval-design.md），后端模型增加字段后自动显示。

---

## 文件清单

### 后端新增文件

| 文件 | 说明 |
|------|------|
| `core/issues_analysis/__init__.py` | 模块初始化 |
| `core/issues_analysis/model.py` | 数据库模型 |
| `core/issues_analysis/schema.py` | Pydantic Schema |
| `core/issues_analysis/service.py` | 业务逻辑 |
| `core/issues_analysis/api.py` | API 路由 |
| `alembic/versions/xxx_add_issues_analysis.py` | 数据库迁移（新建表） |
| `alembic/versions/xxx_add_feature_bug_introduce.py` | 数据库迁移（增加字段） |

### 后端修改文件

| 文件 | 说明 |
|------|------|
| `core/router.py` | 注册 issues_analysis 路由 |
| `core/feature_analysis/model.py` | 新增 feature_bug_introduce 字段 |
| `scripts/init_feature_analysis_menu.py` | 更新修改引入问题菜单的 component 字段 |

### 前端新增文件

| 文件 | 说明 |
|------|------|
| `api/core/issues-analysis.ts` | API 接口定义 |
| `views/feature-analysis/bug-intro/index.vue` | 主页面 |
| `views/feature-analysis/bug-intro/components/FilterBar.vue` | 筛选栏组件 |
| `views/feature-analysis/bug-intro/components/IssuesTable.vue` | 问题表格组件 |

---

## 实现顺序

1. **后端**：创建 issues_analysis 模块（model → schema → service → api）
2. **后端**：注册路由到 core/router.py
3. **后端**：修改 feature_analysis/model.py 新增字段
4. **后端**：创建数据库迁移文件
5. **后端**：更新菜单初始化脚本
6. **前端**：创建 API 接口定义
7. **前端**：创建页面组件
8. **后端**：执行数据库迁移和菜单初始化
9. **测试验证**