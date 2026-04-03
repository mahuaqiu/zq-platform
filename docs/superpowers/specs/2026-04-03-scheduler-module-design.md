# 定时任务模块恢复与界面重设计

**日期**: 2026-04-03
**状态**: 设计已确认，待实现

## 概述

恢复之前删除的定时任务管理模块（scheduler），并重新设计前端界面风格，采用设备管理界面的简洁实用风格。

## 背景

用户之前删除了定时任务相关的前端页面和后端代码，现在需要恢复该功能用于定时执行Python脚本。原模块基于 APScheduler 4.x 实现，功能完整但界面风格需要重新设计。

## 功能需求

### 核心功能

1. **任务管理**
   - 创建、编辑、删除定时任务
   - 支持三种触发类型：Cron表达式、固定间隔(Interval)、指定时间(Date)
   - 任务分组管理
   - 任务启用/禁用/暂停状态切换

2. **任务执行**
   - 立即执行任务（手动触发，不影响原有调度）
   - 执行前弹出确认框

3. **执行日志**
   - 独立页面查看所有任务的执行历史
   - 支持按任务、状态、时间范围筛选
   - 查看执行详情（结果、异常堆栈）
   - 清理旧日志功能

## 界面设计

### 菜单结构

```
定时任务（一级菜单）
├── 任务列表（二级菜单）
└── 执行日志（二级菜单）
```

### 页面布局

#### 任务列表页面

**搜索区域**（灰色背景卡片 #fafafa）：
- 任务名称（模糊搜索）
- 触发类型（下拉：Cron/Interval/Date）
- 任务状态（下拉：启用/禁用/暂停）
- 任务分组（模糊搜索）
- 查询/重置按钮
- 新增任务按钮（右侧，绿色）

**统计卡片**（渐变色背景，4个）：
- 总任务数（紫色渐变）
- 启用任务（绿色渐变）
- 执行成功率（粉色渐变）
- 今日执行次数（蓝色渐变）

**任务表格**：
| 列名 | 说明 |
|------|------|
| 任务名称 | 显示名称 |
| 任务编码 | code格式化显示 |
| 触发类型 | Cron/Interval/Date |
| 触发配置 | Cron表达式或间隔秒数 |
| 任务函数 | 函数路径 |
| 状态 | 启用/禁用/暂停（颜色区分）|
| 执行次数 | 总执行次数 |
| 下次执行 | 预计下次执行时间 |
| 操作 | 执行/编辑/删除 |

**操作列按钮**：
- **执行**（蓝色）- 弹出确认框后立即执行
- **编辑**（蓝色）- 打开编辑弹窗
- **删除**（红色）- 弹出确认框后删除

**分页**：底部右侧，支持切换每页条数

#### 新增/编辑任务弹窗

**表单字段**：
- 任务名称（必填）
- 任务编码（必填，唯一标识）
- 触发类型（下拉选择）
- 触发配置（根据类型动态显示）
  - Cron：表达式输入框 + 格式说明
  - Interval：间隔秒数输入框
  - Date：日期时间选择器
- 任务函数路径（必填）
- 任务参数（JSON格式，可选）
- 任务分组（默认default）
- 任务状态（启用/禁用/暂停）
- 备注

#### 执行日志页面

**搜索区域**：
- 任务名称（下拉选择全部任务）
- 执行状态（成功/失败/超时）
- 开始时间/结束时间（日期选择）
- 查询/重置按钮
- 清理日志按钮（右侧，红色）

**统计卡片**（简洁风格）：
- 总执行次数
- 成功次数（绿色背景）
- 失败次数（红色背景）
- 成功率（蓝色背景）

**日志表格**：
| 列名 | 说明 |
|------|------|
| 任务名称 | 执行的任务名称 |
| 执行时间 | 开始时间 |
| 状态 | 成功/失败/超时（颜色+背景）|
| 耗时 | 执行秒数 |
| 执行结果/异常 | 简要信息 |
| 执行主机 | hostname |
| 操作 | 详情 |

**日志详情弹窗**：
- 任务名称、编码
- 执行状态、开始/结束时间、耗时
- 执行主机、进程ID、重试次数
- 执行结果（完整信息）
- 异常堆栈（失败时显示）

**清理日志弹窗**：
- 保留最近N天（7/30/90/180）
- 清理状态筛选（全部/仅失败/仅成功）
- 警告提示：清理后无法恢复

## 后端模块结构

恢复以下后端文件（从git历史 `5359f62` 提取）：

```
backend-fastapi/scheduler/
├── __init__.py
├── model.py          # SchedulerJob, SchedulerLog 数据模型
├── schema.py         # Pydantic Schema定义
├── service.py        # SchedulerService 单例封装
├── tasks.py          # 任务函数定义
├── api.py            # FastAPI路由
└── router.py         # 路由注册
```

### 数据模型

**SchedulerJob**（定时任务）：
- id, name, code（唯一编码）
- trigger_type, cron_expression, interval_seconds, run_date
- task_func（函数路径）, task_args, task_kwargs
- status（0禁用/1启用/2暂停）
- 统计字段：total_run_count, success_count, failure_count
- 执行时间：last_run_time, next_run_time

**SchedulerLog**（执行日志）：
- job_id, job_name, job_code
- status（pending/running/success/failed/timeout）
- start_time, end_time, duration
- result, exception, traceback
- hostname, process_id, retry_count

## 前端文件结构

```
web/apps/web-ele/src/
├── api/core/
│   └── scheduler.ts          # API接口定义
├── views/
│   └── scheduler/
│       ├── index.vue         # 任务列表页面
│       ├── log.vue           # 执行日志页面
│       ├── data.ts           # 常量和工具函数
│       └── modules/
│           ├── task-form-modal.vue    # 新增/编辑弹窗
│           ├── execute-confirm.vue    # 执行确认弹窗
│           ├── log-detail-modal.vue   # 日志详情弹窗
│           └── clean-log-modal.vue    # 清理日志弹窗
├── locales/langs/zh-CN/
│   └── scheduler.json        # 中文国际化
└── router/routes/modules/
    └── scheduler.ts          # 路由配置
```

## 样式规范

参考设备管理界面（env-machine）风格：

- **搜索区域**：`background: #fafafa`, `padding: 16px`, `border-radius: 4px`
- **表格边框**：`border: 1px solid #e8e8e8`
- **表头背景**：`background: #fafafa`
- **状态颜色**：
  - 成功/启用：`#52c41a`
  - 失败/禁用：`#ff4d4f`
  - 暂停/超时：`#faad14`
  - 链接：`#1890ff`
- **链接样式**：无下划线，hover时显示下划线

## 实现步骤

1. 恢复后端模块（从git历史提取）
2. 注册后端路由
3. 创建前端API接口
4. 创建任务列表页面
5. 创建执行日志页面
6. 创建各类弹窗组件
7. 配置路由和菜单
8. 测试验证

## 任务函数使用说明

用户需要定时执行Python脚本时：

1. 在 `scheduler/tasks.py` 中定义任务函数：
```python
async def my_script_task(job_code: str = None, **kwargs):
    import subprocess
    result = subprocess.run(['python', '/path/to/script.py'], capture_output=True)
    return result.stdout.decode()
```

2. 通过Web界面创建任务：
   - 任务函数路径：`scheduler.tasks.my_script_task`
   - 触发类型：Cron
   - Cron表达式：如 `0 2 * * *`（每天凌晨2点）

3. 调度器自动按计划执行任务

## 注意事项

- APScheduler 4.x 使用异步上下文管理器方式运行
- 调度器在应用启动时自动初始化（通过lifespan）
- 任务执行日志会自动记录到数据库
- 支持任务失败重试配置