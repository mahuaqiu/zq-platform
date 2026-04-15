# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

zq-platform 是一个企业级后台管理系统，采用前后端分离架构：
- **后端**: FastAPI + SQLAlchemy 异步 ORM + PostgreSQL
- **前端**: Vue 3 + Element Plus + Vben Admin，pnpm monorepo 架构

## 核心模块

### 后端模块 (`backend-fastapi/core/`)

| 模块 | 说明 |
|------|------|
| `auth` | 认证授权（JWT Token） |
| `user` | 用户管理 |
| `role` | 角色管理 |
| `permission` | 权限管理 |
| `dept` | 部门管理 |
| `menu` | 菜单管理 |
| `login_log` | 登录日志 |
| `oauth` | OAuth 第三方登录 |
| `env_machine` | 执行机管理（设备管理）- 设备列表页面（合并集成验证/APP/音视频/公共设备）、手工使用页面 |
| `feature_analysis` | 特性分析 |
| `issues_analysis` | 问题分析 |
| `test_report` | 测试报告 |
| `scheduler` | 定时任务 |
| `ai_assistant` | AI助手 |
| `websocket` | WebSocket 实时通信 |

## 常用命令

### 前端开发 (在 `web/` 目录下)

```bash
# 安装依赖
pnpm install

# 启动开发服务器
pnpm dev

# 构建生产版本
pnpm build:ele

# 代码检查
pnpm lint

# 代码格式化
pnpm format

# 类型检查
pnpm check:type

# 运行单元测试
pnpm test:unit
```

### 后端开发 (在 `backend-fastapi/` 目录下)

```bash
# 创建虚拟环境
conda create -n zq-fastapi python=3.12
conda activate zq-fastapi

# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
python main.py
# 或
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 数据库迁移
alembic revision --autogenerate -m "描述信息"
alembic upgrade head

# 数据导入导出
python scripts/dumpdata.py -o db_init.json -f
python scripts/loaddata.py db_init.json

# 初始化菜单脚本
python scripts/init_env_machine_menu.py    # 设备管理菜单（设备列表+手工使用）
# 或使用更新脚本合并旧菜单
python scripts/update_env_machine_menu.py  # 合并4个子菜单为设备列表
python scripts/init_upgrade_menu.py        # 升级管理菜单（设备管理子菜单）
python scripts/init_scheduler_menu.py      # 定时任务菜单
python scripts/init_scheduler_jobs.py      # 定时任务数据初始化
python scripts/init_overview_menu.py       # 概览菜单
python scripts/init_feature_analysis_menu.py  # 特性分析菜单
python scripts/init_test_report_menu.py    # 测试报告菜单
python scripts/init_ai_assistant_menu.py   # AI助手菜单
```

## 架构说明

### 前端 Monorepo 结构

```
web/
├── apps/web-ele/           # Element Plus 主应用
│   └── src/
│       ├── api/            # API 接口定义
│       ├── views/          # 页面组件
│       ├── router/         # 路由配置
│       └── store/          # 状态管理
├── packages/               # 共享包
│   ├── @core/              # 核心 UI 组件和组合式函数
│   ├── stores/             # Pinia 状态管理
│   ├── utils/              # 工具函数
│   └── request/            # HTTP 请求封装
└── internal/               # 内部工具（lint 配置、vite 配置等）
```

### 后端模块结构

每个业务模块 (`core/xxx/`) 包含：
- `model.py` - SQLAlchemy 模型定义
- `schema.py` - Pydantic Schema 定义
- `service.py` - 业务逻辑层，继承 `BaseService`
- `api.py` - FastAPI 路由定义

**路由注册**: 在 `backend-fastapi/core/router.py` 中统一注册所有子模块路由

### BaseModel 和 BaseService

所有模型继承 `BaseModel`（位于 `app/base_model.py`），自动包含：
- `id`: UUID 主键
- `sort`: 排序字段
- `is_deleted`: 软删除标记
- `sys_create_datetime`, `sys_update_datetime`: 时间戳
- `sys_creator_id`, `sys_modifier_id`: 操作人ID

所有服务继承 `BaseService`（位于 `app/base_service.py`），提供通用 CRUD 操作。

## 开发规范

### 新建后端模块

1. 在 `core/` 下创建模块目录，包含 `model.py`, `schema.py`, `service.py`, `api.py`
2. 在 `core/router.py` 中导入并注册路由
3. 执行 `alembic revision --autogenerate -m "add xxx table"` 和 `alembic upgrade head`

### 新建前端页面

1. 在 `apps/web-ele/src/views/` 创建页面组件
2. 在 `apps/web-ele/src/router/routes/modules/` 添加路由配置
3. 在 `apps/web-ele/src/api/` 添加接口定义

### 代码风格

- 前端使用 ESLint + Prettier + Stylelint，运行 `pnpm lint` 检查
- 后端 API 路由使用小写短横线命名：`/api/core/user-profile`
- 静态路由在前，动态路由在后：`/api/core/menu/check/name` → `/api/core/menu/{menu_id}`

## 环境配置

后端环境配置文件位于 `backend-fastapi/env/`，支持多环境：
- `dev.env` - 开发环境
- `uat.env` - UAT 环境
- `prod.env` - 生产环境

通过环境变量 `ENV` 切换：`export ENV=prod`

前端环境配置位于 `apps/web-ele/.env` 系列。

## API 文档

后端启动后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc