# 定时任务模块恢复与界面重设计 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 恢复定时任务管理模块，重新设计前端界面为设备管理风格

**Architecture:** 后端从git历史恢复APScheduler模块，前端重新编写Vue页面采用简洁实用的表格+搜索区布局

**Tech Stack:** FastAPI + APScheduler 4.x + Vue 3 + Element Plus + TypeScript

---

## 文件结构

**后端（从git历史恢复）：**
- `backend-fastapi/scheduler/__init__.py` - 模块初始化
- `backend-fastapi/scheduler/model.py` - SchedulerJob, SchedulerLog 数据模型
- `backend-fastapi/scheduler/schema.py` - Pydantic Schema
- `backend-fastapi/scheduler/service.py` - SchedulerService 单例封装
- `backend-fastapi/scheduler/tasks.py` - 任务函数示例
- `backend-fastapi/scheduler/api.py` - FastAPI路由

**后端（修改）：**
- `backend-fastapi/core/router.py` - 注册scheduler路由

**前端（新建）：**
- `web/apps/web-ele/src/api/core/scheduler.ts` - API接口定义
- `web/apps/web-ele/src/views/scheduler/index.vue` - 任务列表页面
- `web/apps/web-ele/src/views/scheduler/log.vue` - 执行日志页面
- `web/apps/web-ele/src/views/scheduler/data.ts` - 常量和工具函数
- `web/apps/web-ele/src/views/scheduler/modules/task-form-modal.vue` - 任务表单弹窗
- `web/apps/web-ele/src/views/scheduler/modules/log-detail-modal.vue` - 日志详情弹窗
- `web/apps/web-ele/src/views/scheduler/modules/clean-log-modal.vue` - 清理日志弹窗
- `web/apps/web-ele/src/locales/langs/zh-CN/scheduler.json` - 中文国际化
- `web/apps/web-ele/src/router/routes/modules/scheduler.ts` - 路由配置

**数据库初始化：**
- `backend-fastapi/scripts/init_scheduler_menu.py` - 初始化菜单脚本

---

## Task 1: 恢复后端模块文件

**Files:**
- Create: `backend-fastapi/scheduler/__init__.py`
- Create: `backend-fastapi/scheduler/model.py`
- Create: `backend-fastapi/scheduler/schema.py`
- Create: `backend-fastapi/scheduler/service.py`
- Create: `backend-fastapi/scheduler/tasks.py`
- Create: `backend-fastapi/scheduler/api.py`

- [ ] **Step 1: 创建scheduler目录并恢复model.py**

```bash
mkdir -p backend-fastapi/scheduler
git show 5359f62:backend-fastapi/scheduler/model.py > backend-fastapi/scheduler/model.py
```

- [ ] **Step 2: 恢复schema.py**

```bash
git show 5359f62:backend-fastapi/scheduler/schema.py > backend-fastapi/scheduler/schema.py
```

- [ ] **Step 3: 恢复service.py**

```bash
git show 5359f62:backend-fastapi/scheduler/service.py > backend-fastapi/scheduler/service.py
```

- [ ] **Step 4: 恢复tasks.py**

```bash
git show 5359f62:backend-fastapi/scheduler/tasks.py > backend-fastapi/scheduler/tasks.py
```

- [ ] **Step 5: 恢复api.py**

```bash
git show 5359f62:backend-fastapi/scheduler/api.py > backend-fastapi/scheduler/api.py
```

- [ ] **Step 6: 创建__init__.py**

```bash
echo '# 定时任务调度模块' > backend-fastapi/scheduler/__init__.py
```

- [ ] **Step 7: 提交后端模块恢复**

```bash
git add backend-fastapi/scheduler/
git commit -m "feat(scheduler): 恢复定时任务后端模块"
```

---

## Task 2: 注册后端路由

**Files:**
- Modify: `backend-fastapi/core/router.py`

- [ ] **Step 1: 修改router.py添加scheduler路由**

在导入区域添加：
```python
from core.scheduler.api import router as scheduler_router
```

在路由注册区域添加：
```python
router.include_router(scheduler_router)
```

- [ ] **Step 2: 提交路由注册**

```bash
git add backend-fastapi/core/router.py
git commit -m "feat(scheduler): 注册定时任务路由"
```

---

## Task 3: 创建前端API接口

**Files:**
- Create: `web/apps/web-ele/src/api/core/scheduler.ts`

- [ ] **Step 1: 创建scheduler.ts API文件**

完整代码见spec文档中定义的接口，包含：
- SchedulerJob, SchedulerLog 类型定义
- 分页查询、创建、更新、删除API
- 执行任务、获取统计API
- 日志查询、详情、清理API

- [ ] **Step 2: 提交API文件**

```bash
git add web/apps/web-ele/src/api/core/scheduler.ts
git commit -m "feat(scheduler): 添加前端API接口定义"
```

---

## Task 4: 创建前端常量和工具函数

**Files:**
- Create: `web/apps/web-ele/src/views/scheduler/data.ts`

- [ ] **Step 1: 创建data.ts**

包含触发类型选项、状态选项、格式化函数等。

- [ ] **Step 2: 提交常量文件**

```bash
git add web/apps/web-ele/src/views/scheduler/data.ts
git commit -m "feat(scheduler): 添加前端常量和工具函数"
```

---

## Task 5: 创建任务列表页面

**Files:**
- Create: `web/apps/web-ele/src/views/scheduler/index.vue`

- [ ] **Step 1: 创建index.vue页面**

参考env-machine页面风格，包含：
- 搜索区域（灰色背景 #fafafa）
- 统计卡片（4个渐变色）
- 任务表格（带边框）
- 分页组件
- 操作按钮（执行/编辑/删除）

执行按钮使用 ElMessageBox.confirm 确认后再调用API。

- [ ] **Step 2: 提交任务列表页面**

```bash
git add web/apps/web-ele/src/views/scheduler/index.vue
git commit -m "feat(scheduler): 创建任务列表页面"
```

---

## Task 6: 创建执行日志页面

**Files:**
- Create: `web/apps/web-ele/src/views/scheduler/log.vue`

- [ ] **Step 1: 创建log.vue页面**

包含：
- 搜索区域（任务下拉、状态、时间范围）
- 统计卡片（简洁风格）
- 日志表格
- 分页组件
- 清理日志按钮

- [ ] **Step 2: 提交执行日志页面**

```bash
git add web/apps/web-ele/src/views/scheduler/log.vue
git commit -m "feat(scheduler): 创建执行日志页面"
```

---

## Task 7: 创建任务表单弹窗

**Files:**
- Create: `web/apps/web-ele/src/views/scheduler/modules/task-form-modal.vue`

- [ ] **Step 1: 创建任务表单弹窗组件**

使用ElDialog + ElForm，包含：
- 任务名称、编码输入
- 触发类型选择（动态显示配置字段）
- 任务函数路径
- 任务参数（JSON）
- 分组、状态、备注

- [ ] **Step 2: 提交表单弹窗组件**

```bash
git add web/apps/web-ele/src/views/scheduler/modules/task-form-modal.vue
git commit -m "feat(scheduler): 创建任务表单弹窗"
```

---

## Task 8: 创建日志详情弹窗

**Files:**
- Create: `web/apps/web-ele/src/views/scheduler/modules/log-detail-modal.vue`

- [ ] **Step 1: 创建日志详情弹窗组件**

显示完整执行信息，包含异常堆栈区域。

- [ ] **Step 2: 提交日志详情弹窗**

```bash
git add web/apps/web-ele/src/views/scheduler/modules/log-detail-modal.vue
git commit -m "feat(scheduler): 创建日志详情弹窗"
```

---

## Task 9: 创建清理日志弹窗

**Files:**
- Create: `web/apps/web-ele/src/views/scheduler/modules/clean-log-modal.vue`

- [ ] **Step 1: 创建清理日志弹窗组件**

包含保留天数选择、状态筛选、警告提示。

- [ ] **Step 2: 提交清理日志弹窗**

```bash
git add web/apps/web-ele/src/views/scheduler/modules/clean-log-modal.vue
git commit -m "feat(scheduler): 创建清理日志弹窗"
```

---

## Task 10: 创建前端路由配置

**Files:**
- Create: `web/apps/web-ele/src/router/routes/modules/scheduler.ts`

- [ ] **Step 1: 创建路由配置文件**

```typescript
import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    name: 'SchedulerLog',
    path: '/scheduler/log',
    component: () => import('#/views/scheduler/log.vue'),
    meta: {
      hideInMenu: true,
      title: '执行日志',
    },
  },
];

export default routes;
```

- [ ] **Step 2: 提交路由配置**

```bash
git add web/apps/web-ele/src/router/routes/modules/scheduler.ts
git commit -m "feat(scheduler): 添加前端路由配置"
```

---

## Task 11: 添加国际化文件

**Files:**
- Create: `web/apps/web-ele/src/locales/langs/zh-CN/scheduler.json`

- [ ] **Step 1: 创建中文国际化文件**

- [ ] **Step 2: 提交国际化文件**

```bash
git add web/apps/web-ele/src/locales/langs/zh-CN/scheduler.json
git commit -m "feat(scheduler): 添加中文国际化"
```

---

## Task 12: 创建菜单初始化脚本

**Files:**
- Create: `backend-fastapi/scripts/init_scheduler_menu.py`

- [ ] **Step 1: 创建菜单初始化脚本**

参考项目中的 init_env_machine_menu.py 脚本格式，创建：
- 一级菜单：定时任务
- 二级菜单：任务列表（/scheduler）、执行日志（/scheduler/log）

- [ ] **Step 2: 提交初始化脚本**

```bash
git add backend-fastapi/scripts/init_scheduler_menu.py
git commit -m "feat(scheduler): 添加菜单初始化脚本"
```

---

## Task 13: 数据库迁移与初始化

- [ ] **Step 1: 生成数据库迁移文件**

```bash
cd backend-fastapi && alembic revision --autogenerate -m "add scheduler tables"
```

- [ ] **Step 2: 执行数据库迁移**

```bash
cd backend-fastapi && alembic upgrade head
```

- [ ] **Step 3: 执行菜单初始化**

```bash
cd backend-fastapi && python scripts/init_scheduler_menu.py
```

- [ ] **Step 4: 提交迁移文件**

```bash
git add backend-fastapi/alembic/versions/
git commit -m "feat(scheduler): 添加数据库迁移文件"
```

---

## Task 14: 验证测试

- [ ] **Step 1: 启动后端服务验证**

检查服务启动、API文档可访问

- [ ] **Step 2: 启动前端服务验证**

检查页面加载、菜单显示、API调用

- [ ] **Step 3: 功能测试**

测试创建、编辑、删除、执行任务、查看日志、清理日志

---

## 最终提交

```bash
git add .
git commit -m "feat(scheduler): 完成定时任务模块恢复与界面重设计"
```