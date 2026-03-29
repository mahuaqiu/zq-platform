# 用例日志分析系统设计文档

> 日期：2026-03-29
> 作者：Claude Code

## 1. 系统概述

用例日志分析系统用于展示测试用例执行完成后的结果分析，支持多轮重试场景下的失败统计分析、AI智能分析、历史对比等功能。

### 核心功能

- **实时数据上报**：测试执行失败时，逐条推送失败记录到系统
- **超时自动分析**：可配置超时时间，自动触发汇总分析
- **多维度统计**：轮次分析、失败步骤分布、同比变化等
- **AI智能分析**：后续规划定时任务调用本地AI服务进行分析
- **可视化展示**：列表页 + 详情页，包含图表展示

---

## 2. 页面设计

### 2.1 报告列表页

**访问路径**：`/test-report/list`

**页面功能**：
- 按任务名称筛选
- 展示所有任务执行的报告汇总
- 点击查看详情进入详情页

**展示字段**：

| 字段 | 说明 | 示例 |
|------|------|------|
| 任务名称 | 执行的任务名称 | 登录模块回归测试_2026-03-29 |
| 执行时间 | 任务执行时间 | 2026-03-29 14:30 |
| 用例总数 | 本次执行的用例总数 | 120 |
| 失败总数 | 最终失败的用例数（仅最后一轮失败） | 12 |
| 通过率 | 通过百分比 | 90% |
| 同比变化 | 与上次执行对比，↓下降（绿色），↑上升（红色），首次显示-- | ↓3 |
| 操作 | 查看详情链接 | 查看详情 |

**排序规则**：按执行时间倒序，最新在上面

**筛选功能**：任务名称模糊搜索

---

### 2.2 报告详情页

**访问路径**：`/test-report/detail/:task_id`

**页面布局**（从上到下）：

#### 顶部信息区
- 任务名称
- 执行时间
- 操作按钮（导出报告、返回列表）

#### 统计卡片区（6个卡片）
1. **用例总数**：本次执行的用例总数
2. **通过率**：通过百分比
3. **失败总数**：最终失败的用例数
4. **同比上次执行**：与上次对比变化（如 ↓3，上次失败15个）
5. **每轮都失败**：所有轮次都失败的用例数（重点关注）
6. **不稳定用例**：前几轮失败，最后一轮通过的用例数

#### AI分析结论区
- 展示AI分析结果（等待定时任务触发分析）
- 分析状态显示

#### 轮次分析区
- 标题："轮次分析"
- 动态展示每轮失败数的卡片（如：第1轮失败17、第2轮失败12、第3轮失败12）
- 数量根据实际轮次动态渲染

#### 失败步骤分布（Top 20）
- 横向柱状图
- 左侧步骤名称，中间柱状图（按比例），右侧数值紧跟柱子
- 示例：断言失败 ████████████ 8

#### 失败记录表格（Tab分类）

**术语定义**：
- **本轮失败**：最后一轮失败的用例（对应 fail_total）
- **全程失败**：所有轮次均失败的用例（对应 fail_always）
- **不稳定用例**：前几轮失败，最后一轮通过的用例（对应 fail_unstable）

- Tab分类：本轮失败、全程失败、不稳定用例、全部记录
- 表格字段：
  - 用例名称
  - 失败步骤
  - 失败日志（默认收缩，点击展开查看完整日志）
  - 失败时间
  - 操作（查看完整日志 - 弹窗展示HTML）

---

## 3. 数据流程

### 3.1 数据上报流程

```
测试框架执行用例
    ↓
用例失败 → 推送失败记录到 API
    ↓
存储到 test_report_detail 表
    ↓
（无新数据推送超过超时时间）
    ↓
自动触发汇总分析
    ↓
生成 test_report_summary 记录
```

### 3.2 上报 API 设计

**接口**：`POST /api/test-report/fail`

**请求参数**：
```json
{
  "task_id": "abc123",
  "task_name": "登录模块回归测试_2026-03-29",
  "total_cases": 120,
  "case_name": "登录-密码错误提示验证",
  "case_fail_step": "断言失败",
  "case_fail_log": "AssertionError: Expected '密码错误'...",
  "case_round": 1,
  "log_url": "http://logs.example.com/case_001.html",
  "fail_time": "2026-03-29 14:35:00"
}
```

### 3.3 汇总分析流程

**触发机制**：使用 APScheduler 定时任务（每5分钟扫描一次）

扫描逻辑：
1. 查询 `test_report_detail` 表中存在记录但 `test_report_summary` 表无对应 task_id 的数据
2. 按 task_id 分组，取每组最后一条记录的 `sys_create_datetime` 作为 `last_report_time`
3. 判断 `now() - last_report_time > ANALYZE_TIMEOUT_MINUTES`
4. 满足条件则触发汇总分析

分析逻辑：
1. 查询该 task_id 所有明细记录
2. 统计各轮次失败数 → round_stats
3. 统计最后一轮失败的用例 → fail_total
4. 统计所有轮次都失败的用例 → fail_always
5. 统计不稳定用例（前几轮失败，最后一轮无记录）→ fail_unstable
6. 统计失败步骤分布 → step_distribution
7. 计算通过率 → pass_rate = (total_cases - fail_total) / total_cases * 100
8. 查询上次同任务执行记录（按 task_base_name 匹配）→ compare_change, last_fail_total
9. 设置 execute_time = 第一条失败记录的 fail_time
10. 设置 analysis_status = pending
11. 存储汇总数据到 test_report_summary

**同比计算说明**：
- task_base_name = task_name 去除日期后缀（如 "登录模块回归测试_2026-03-29" → "登录模块回归测试")
- 查询 task_base_name 相同且 execute_time < 当前任务 execute_time 的最近一条记录
- compare_change = fail_total - last_fail_total（正数表示上升↑，负数表示下降↓）
- 首次执行时 compare_change = null

---

## 4. 数据库设计

### 4.1 test_report_detail（失败明细表）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | String(21) | Y | 主键（NanoId） |
| task_id | String(21) | Y | 任务执行ID |
| task_name | String(100) | Y | 任务名称 |
| total_cases | Integer | Y | 用例总数（每次上报携带，用于汇总） |
| case_name | String(200) | Y | 用例标题 |
| case_fail_step | String(100) | Y | 失败步骤名称 |
| case_fail_log | Text | Y | 失败日志 |
| case_round | Integer | Y | 失败轮次（1/2/3...） |
| log_url | String(500) | N | 完整日志地址（HTML） |
| fail_time | DateTime | N | 失败时间 |

**继承 BaseModel 字段**：sort, is_deleted, sys_create_datetime, sys_update_datetime, sys_creator_id, sys_modifier_id

**索引**：
- `idx_task_id`：task_id（查询明细）
- `idx_task_case_round`：(task_id, case_name, case_round)（统计同用例多轮次）

---

### 4.2 test_report_summary（汇总表）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | String(21) | Y | 主键（NanoId） |
| task_id | String(21) | Y | 任务执行ID |
| task_name | String(100) | Y | 任务名称 |
| task_base_name | String(100) | N | 任务基础名称（去除日期后缀，用于同比计算） |
| total_cases | Integer | Y | 用例总数 |
| fail_total | Integer | Y | 失败总数（最后一轮失败的用例） |
| pass_rate | String(10) | Y | 通过率（如 "90%"） |
| compare_change | Integer | N | 同比变化（正数↑，负数↓，null首次） |
| last_fail_total | Integer | N | 上次执行失败数（用于同比计算） |
| round_stats | JSON | N | 轮次统计 |
| fail_always | Integer | N | 每轮都失败数（所有轮次均失败） |
| fail_unstable | Integer | N | 不稳定用例数（前几轮失败，最后一轮通过） |
| step_distribution | JSON | N | 失败步骤分布 |
| ai_analysis | Text | N | AI分析结论 |
| analysis_status | String(20) | N | 分析状态（pending/completed） |
| execute_time | DateTime | N | 执行时间（取第一条失败记录的 fail_time） |
| last_report_time | DateTime | N | 最后上报时间（用于超时判断） |

**继承 BaseModel 字段**

**索引**：
- `uq_task_id`：task_id（唯一）
- `idx_task_name`：task_name（模糊搜索）
- `idx_task_base_name`：task_base_name（同比查询）
- `idx_execute_time`：execute_time（排序查询）
- `idx_last_report_time`：last_report_time（超时扫描）

**JSON 字段格式**：

round_stats：
```json
[
  {"round": 1, "fail_count": 17},
  {"round": 2, "fail_count": 12},
  {"round": 3, "fail_count": 12}
]
```

step_distribution：
```json
[
  {"step": "断言失败", "count": 8},
  {"step": "元素定位失败", "count": 5},
  {"step": "超时等待", "count": 4}
]
```

---

### 4.3 系统配置（集成到 Settings 类）

在 `app/config.py` 的 `Settings` 类中添加：

```python
# 测试报告配置
ANALYZE_TIMEOUT_MINUTES: int = 30  # 超时自动分析时间（分钟）
AI_ANALYSIS_SERVICE_URL: Optional[str] = None  # 本地AI服务地址（后续规划）
TEST_REPORT_API_TOKEN: Optional[str] = None  # 上报API专用Token（认证）
```

---

## 5. API 接口设计

### 5.1 认证说明

- 上报接口 `POST /api/test-report/fail` 使用独立 Token 认证
- 测试框架携带配置的 `TEST_REPORT_API_TOKEN` 在请求头：`Authorization: Bearer {token}`
- 查询接口使用系统标准的 JWT 认证（登录后访问）

### 5.2 上报接口

- `POST /api/test-report/fail` - 推送失败用例记录

### 5.3 查询接口

- `GET /api/test-report/list` - 获取报告列表（支持 task_name 筛选、分页）
- `GET /api/test-report/summary/{task_id}` - 获取单个报告汇总
- `GET /api/test-report/detail/{task_id}` - 获取报告明细列表
  - 查询参数 `category`：分类筛选（`final_fail` / `always_fail` / `unstable` / `all`）
- `GET /api/test-report/log/{task_id}/{case_name}` - 获取用例完整日志（或直接返回 log_url）

---

## 6. 后续规划

### 6.1 AI分析功能

- 定时任务扫描 analysis_status = pending 的记录
- 调用可配置的本地AI服务
- 分析内容：失败原因归类、根因建议、关注用例列表
- 更新 ai_analysis 字段，设置 analysis_status = completed

### 6.2 扩展功能

- 导出报告功能（PDF/Excel）
- 报告趋势分析（同一任务历史趋势图）
- 失败用例关联问题单

---

## 7. 模块结构

遵循项目现有架构，模块位于 `backend-fastapi/core/test_report/`：

```
test_report/
├── __init__.py
├── model.py        # 数据模型定义
├── schema.py       # Pydantic Schema 定义
├── service.py      # 业务逻辑（CRUD + 汇总分析）
├── api.py          # FastAPI 路由定义
├── scheduler.py    # APScheduler 定时任务（超时扫描触发汇总）
├── auth.py         # Token认证中间件（上报接口专用）
└── utils.py        # 工具函数（task_name解析等）
```

前端模块位于 `web/apps/web-ele/src/views/test-report/`：

```
test-report/
├── list/
│   └── index.vue               # 报告列表页
├── detail/
│   └── index.vue               # 报告详情页
│   └── components/
│       ├── StatsCards.vue      # 统计卡片组件
│       ├── RoundAnalysis.vue   # 轮次分析组件
│       ├── StepDistribution.vue # 失败步骤分布组件
│       ├── FailTable.vue       # 失败记录表格组件
│       └── LogDialog.vue       # 日志弹窗组件
```