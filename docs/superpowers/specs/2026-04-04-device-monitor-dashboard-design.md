# 设备监控看板设计文档

## 概述

新增"概览 > 设备监控"菜单，展示设备监控看板，包含6个数据模块。

## 一、数据库设计

### 1.1 新建申请日志表 `env_machine_log`

```sql
CREATE TABLE env_machine_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace VARCHAR(64) NOT NULL,           -- 机器分类
    machine_id UUID NOT NULL,                  -- 机器ID
    ip VARCHAR(45),                            -- 机器IP
    device_type VARCHAR(20) NOT NULL,          -- 机器类型: windows/mac/android/ios
    device_sn VARCHAR(64),                     -- 设备SN（移动端）
    mark VARCHAR(255),                         -- 申请的标签（用于TOP10统计）
    action VARCHAR(20) NOT NULL,               -- 操作类型: apply/release
    result VARCHAR(20) NOT NULL,               -- 结果: success/fail
    fail_reason VARCHAR(255),                  -- 失败原因（如 env not enough）
    apply_time TIMESTAMP,                      -- 申请时间
    release_time TIMESTAMP,                    -- 释放时间
    duration_minutes INTEGER,                  -- 占用时长（分钟）
    sys_create_datetime TIMESTAMP DEFAULT NOW(),

    INDEX ix_env_machine_log_create_time (sys_create_datetime),
    INDEX ix_env_machine_log_namespace_time (namespace, sys_create_datetime),
    INDEX ix_env_machine_log_machine_id (machine_id)
);
```

**记录时机：**
- 申请时：记录一条日志，action=apply，result=success/fail
- 释放时：更新对应申请记录的 release_time 和 duration_minutes

## 二、后端改造

### 2.1 新建模块文件

在 `backend-fastapi/core/env_machine/` 目录下新增：
- `log_model.py` - 日志模型
- `log_schema.py` - 日志 Schema
- `log_service.py` - 日志服务（含统计方法）

### 2.2 改造申请/释放接口

修改 `backend-fastapi/core/env_machine/pool_manager.py`：
- `allocate_machines()` 方法：申请时写入日志
- `release_machine()` 方法：释放时更新日志

### 2.3 新增统计 API

在 `backend-fastapi/core/env_machine/api.py` 新增：

```
GET /api/core/env-machine/dashboard/stats
```

返回数据结构：
```json
{
  "device_stats": {
    "total": 128,
    "online": 100,
    "offline": 28,
    "by_type": [
      {"type": "windows", "total": 50, "enabled": 40, "disabled": 10},
      {"type": "mac", "total": 30, "enabled": 25, "disabled": 5},
      {"type": "android", "total": 20, "enabled": 18, "disabled": 2},
      {"type": "ios", "total": 28, "enabled": 23, "disabled": 5}
    ]
  },
  "apply_24h": {
    "total": 256,
    "success": 250,
    "failed": 6
  },
  "top10_tags": [
    {"tag": "windows_1", "count": 45},
    ...
  ],
  "top20_duration": [
    {"ip": "192.168.1.100", "device_type": "windows", "duration_minutes": 480, "duration_display": "8h"},
    ...
  ],
  "top10_insufficient": [
    {"tag": "windows_5", "count": 3},
    ...
  ],
  "offline_machines": [
    {"id": "xxx", "ip": "192.168.1.100", "device_type": "windows", "offline_duration": "2小时"},
    ...
  ]
}
```

**查询参数：**
- `namespace`: 可选，筛选指定 namespace，默认查询全部

### 2.4 新增清理任务函数

在 `backend-fastapi/core/scheduler/tasks.py` 新增：

```python
async def cleanup_env_machine_log_task(job_code: str = None, days: int = 7, **kwargs):
    """清理执行机申请日志，保留最近N天"""
    ...
```

### 2.5 更新初始化脚本

在 `backend-fastapi/scripts/init_scheduler_jobs.py` 的 `internal_jobs` 列表中新增：

```python
{
    'name': '执行机申请日志清理',
    'code': 'env_machine_log_cleanup',
    'description': '清理过期的执行机申请日志',
    'group': 'env_machine',
    'trigger_type': 'cron',
    'cron_expression': '0 3 * * *',
    'task_func': 'core.scheduler.tasks.cleanup_env_machine_log_task',
    'task_kwargs': '{"days": 7}',
    'status': 1,
    'priority': 1,
    'remark': '清理7天前的申请日志',
},
```

## 三、前端实现

### 3.1 新增菜单

**一级菜单：概览**
- 菜单名称：概览
- 路由路径：/overview
- 图标：dashboard

**二级菜单：设备监控**
- 菜单名称：设备监控
- 路由路径：/overview/device-monitor
- 组件：views/device-monitor/index.vue

### 3.2 看板页面布局

**布局方案：左右分栏（方案C）**

```
┌─────────────────────────────────────────────────────────┐
│                    顶部筛选栏（namespace选择）              │
├──────────────────┬──────────────────────────────────────┤
│     左侧面板      │              右侧面板                  │
│   （实时状态）    │           （历史统计）                  │
│                  │                                       │
│ ┌──────────────┐ │ ┌───────────────────────────────────┐ │
│ │设备台数统计   │ │ │ 24h申请总次数                      │ │
│ │总数/在线/离线 │ │ │ 256 | 成功250 | 资源不足6          │ │
│ │Win/Mac/And/IOS│ │ └───────────────────────────────────┘ │
│ │启用/未启用    │ │ ┌─────────────┐ ┌─────────────┐      │
│ └──────────────┘ │ │TOP10标签申请│ │TOP10资源不足│      │
│                  │ │ (10条无滚动)│ │ (10条无滚动)│      │
│ ┌──────────────┐ │ └─────────────┘ └─────────────┘      │
│ │异步机器排查   │ │ ┌───────────────────────────────────┐ │
│ │（启用但离线） │ │ │ 机器占用时长 TOP20                  │ │
│ │ 支持滚动     │ │ │ (显示15条高度，支持滚动)            │ │
│ └──────────────┘ │ └───────────────────────────────────┘ │
└──────────────────┴──────────────────────────────────────┘
```

### 3.3 图表样式

**柱状图样式：**
- 时长紧跟在柱状图末端，无灰色背景填充
- 按比例显示柱状图长度（以最大值为100%）

**时长显示规则：**
- 小于60分钟：显示 "xm"（如 45m）
- 大于等于60分钟：显示 "xh"（如 8h）

### 3.4 数据刷新

- 自动刷新：每30分钟刷新一次
- 手动刷新：提供刷新按钮

### 3.5 前端文件结构

```
web/apps/web-ele/src/
├── api/core/
│   └── device-monitor.ts          # API 接口定义
├── views/device-monitor/
│   └── index.vue                   # 看板页面组件
├── router/routes/modules/
│   └── overview.ts                 # 路由配置
```

## 四、实施步骤

1. **后端 - 数据库迁移**：创建 env_machine_log 表
2. **后端 - Model/Schema/Service**：申请日志模块代码
3. **后端 - 改造申请/释放接口**：写入日志记录
4. **后端 - 统计API**：6个模块的数据统计接口
5. **后端 - 清理任务函数**：添加到 tasks.py
6. **后端 - 初始化脚本**：更新 init_scheduler_jobs.py
7. **前端 - 路由/菜单**：新增"概览 > 设备监控"菜单
8. **前端 - 看板页面**：Vue组件 + 横向柱状图

## 五、技术选型

- 图表库：CSS 实现横向柱状图（无需引入 ECharts，简化实现）
- 数据刷新：setInterval + 手动刷新按钮
- 响应式：左右分栏自适应