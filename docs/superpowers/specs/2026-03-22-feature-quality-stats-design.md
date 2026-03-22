# 特性质量统计模块设计文档

## 概述

新增"特性质量统计"一级菜单，包含三个子菜单：需求进展、需求质量评价、修改引入问题。本文档主要描述"需求进展"页面的实现设计。

## 第一部分：数据库设计

### feature_analysis 表结构

```sql
CREATE TABLE feature_analysis (
    -- 主键与继承字段
    id VARCHAR(21) PRIMARY KEY,
    sort INTEGER DEFAULT 0,
    is_deleted BOOLEAN DEFAULT FALSE,
    sys_create_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sys_update_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sys_creator_id VARCHAR(21),
    sys_modifier_id VARCHAR(21),

    -- 业务字段
    feature_id_father VARCHAR(64),      -- 父工作项ID
    feature_id VARCHAR(64),             -- 需求ID
    feature_desc VARCHAR(255),          -- 需求标题
    feature_services VARCHAR(64),       -- 开发归属
    feature_task_id VARCHAR(64),        -- 需求task id
    feature_task_service VARCHAR(64),   -- 测试归属
    feature_owner VARCHAR(64),          -- 测试责任人
    feature_dev_owner VARCHAR(64),      -- 开发责任人
    feature_safe_test VARCHAR(64),      -- 涉及安全
    feature_code VARCHAR(64),           -- 代码量
    feature_test_count VARCHAR(64),     -- 需求转测次数
    feature_test_expect_time VARCHAR(64), -- 预计转测时间
    feature_test_start_time VARCHAR(64),  -- 实际转测时间
    feature_test_end_time VARCHAR(64),    -- 完成测试时间
    feature_judge TEXT,                 -- 特性质量评价
    feature_bug_total VARCHAR(64),      -- 问题单数量
    feature_bug_serious VARCHAR(64),    -- 严重以上数量
    feature_bug_general VARCHAR(64),    -- 一般数量
    feature_bug_prompt VARCHAR(64),     -- 提示数量
    feature_bug_detail VARCHAR(255),    -- 引入问题单号
    feature_progress TEXT,              -- 测试进展
    feature_risk TEXT,                  -- 风险与关键问题
    feature_version VARCHAR(64),        -- 需求归属版本
    sync_time VARCHAR(64),              -- 数据同步时间
    create_by VARCHAR(64),              -- 创建者
    create_time VARCHAR(64),            -- 创建时间
    modify_time VARCHAR(64)             -- 修改时间
);

-- 索引
CREATE INDEX idx_feature_analysis_version ON feature_analysis(feature_version);
CREATE INDEX idx_feature_analysis_deleted ON feature_analysis(is_deleted);
```

## 第二部分：后端 API 设计

### API 端点

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 获取需求列表 | GET | `/api/core/feature-analysis` | 分页查询，支持版本筛选 |
| 获取版本列表 | GET | `/api/core/feature-analysis/versions` | 返回所有版本选项 |
| 及时转测情况 | GET | `/api/core/feature-analysis/chart/timely-test` | 饼图数据（预留） |
| 需求转测情况 | GET | `/api/core/feature-analysis/chart/test-status` | 饼图数据（预留） |
| 已转测需求验证情况 | GET | `/api/core/feature-analysis/chart/verify-status` | 饼图数据（预留） |

### 列表查询请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，默认1 |
| pageSize | int | 否 | 每页数量，默认20 |
| version | string | 否 | 版本筛选 |

### 列表查询响应结构

```json
{
  "items": [
    {
      "id": "xxx",
      "featureIdFather": "EP202602253111",
      "featureId": "FE202630554422",
      "featureDesc": "特性标题名称",
      "featureOwner": "张三",
      "featureTaskService": "服务端",
      "featureSafeTest": "否",
      "featureTestExpectTime": "2026-02-01",
      "featureTestStartTime": "2026-02-01",
      "testStatus": "已完成",
      "featureProgress": "已完成测试，发现问题10个，关联用例50条",
      "featureRisk": "无风险"
    }
  ],
  "total": 100
}
```

### 版本列表响应结构

```json
{
  "items": ["V1.0.0", "V1.1.0", "V2.0.0"]
}
```

### 饼图数据响应结构（预留）

```json
{
  "seriesData": [
    { "name": "及时转测", "value": 50 },
    { "name": "延迟转测", "value": 30 }
  ]
}
```

### 测试状态计算逻辑

```python
def get_test_status(item):
    if item.feature_test_end_time:
        return "已完成"
    elif item.feature_test_start_time:
        return "测试中"
    else:
        return "未开始"
```

## 第三部分：前端页面设计

### 页面结构

```
需求进展页面
├── 筛选区域（版本下拉框）
├── 饼图区域（三个饼图并排）
│   ├── 及时转测情况
│   ├── 需求转测情况
│   └── 已转测需求验证情况
└── 数据表格区域
    └── 需求明细列表（分页）
```

### 组件结构

```
views/feature-analysis/
├── progress/
│   ├── index.vue              # 主页面
│   └── components/
│       ├── FilterBar.vue      # 筛选栏
│       ├── PieCharts.vue      # 饼图区域
│       └── FeatureTable.vue   # 数据表格
```

### API 接口定义

```
api/core/feature-analysis.ts
```

### 表格列定义

| 列名 | 字段 | 宽度 |
|------|------|------|
| 父工作项编码号 | featureIdFather | 150px |
| 需求编号 | featureId | 150px |
| 标题 | featureDesc | 自适应 |
| 测试责任人 | featureOwner | 100px |
| 测试归属 | featureTaskService | 100px |
| 涉及安全 | featureSafeTest | 80px |
| 预计转测时间 | featureTestExpectTime | 120px |
| 实际转测情况 | featureTestStartTime | 120px |
| 测试状态 | testStatus | 80px |
| 测试进展 | featureProgress | 200px |
| 风险与关键问题 | featureRisk | 150px |

## 第四部分：菜单初始化脚本设计

### 菜单结构

```
特性质量统计（一级菜单，目录类型）
├── 需求进展（二级菜单）
├── 需求质量评价（二级菜单，占位）
└── 修改引入问题（二级菜单，占位）
```

### 菜单数据

| 字段 | 特性质量统计 | 需求进展 | 需求质量评价 | 修改引入问题 |
|------|-------------|---------|-------------|-------------|
| name | FeatureQuality | FeatureProgress | FeatureQualityEval | FeatureBugIntro |
| title | 特性质量统计 | 需求进展 | 需求质量评价 | 修改引入问题 |
| path | /feature-quality | /feature-quality/progress | /feature-quality/eval | /feature-quality/bug-intro |
| type | catalog | menu | menu | menu |
| component | - | feature-analysis/progress/index | - | - |
| icon | 数据图表 | - | - | - |

### 初始化脚本位置

`backend-fastapi/scripts/init_feature_analysis_menu.py`

脚本功能：
1. 检查菜单是否已存在
2. 不存在则插入菜单数据
3. 支持重复执行不报错

## 第五部分：文件清单

### 后端文件

```
backend-fastapi/
├── core/
│   └── feature_analysis/
│       ├── __init__.py
│       ├── model.py           # 数据库模型
│       ├── schema.py          # Pydantic Schema
│       ├── service.py         # 业务逻辑
│       └── api.py             # API 路由
├── scripts/
│   └── init_feature_analysis_menu.py  # 菜单初始化脚本
└── alembic/versions/
    └── xxx_add_feature_analysis.py    # 数据库迁移文件
```

### 前端文件

```
web/apps/web-ele/src/
├── api/core/
│   └── feature-analysis.ts    # API 接口定义
└── views/feature-analysis/
    └── progress/
        ├── index.vue          # 主页面
        └── components/
            ├── FilterBar.vue  # 筛选栏
            ├── PieCharts.vue  # 饼图区域
            └── FeatureTable.vue # 数据表格
```

## 实现顺序

1. 后端：创建 feature_analysis 模块（model → schema → service → api）
2. 后端：注册路由到 core/router.py
3. 后端：创建数据库迁移文件
4. 后端：创建菜单初始化脚本
5. 前端：创建 API 接口定义
6. 前端：创建页面组件
7. 后端：执行数据库迁移和菜单初始化
8. 测试验证