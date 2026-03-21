# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

zq-platform 是一个基于 Vue Vben Admin 的企业级后台管理平台，使用 pnpm + turbo 的 monorepo 架构。主要技术栈：Vue 3 + TypeScript + Element Plus + Vite。

## 常用命令

```bash
# 开发
pnpm dev                 # 启动主应用开发服务器（apps/web-ele，端口 5777）
pnpm dev:play            # 启动 playground 开发服务器

# 构建
pnpm build               # 构建所有应用
pnpm build:ele           # 仅构建主应用

# 代码质量
pnpm lint                # 检查代码问题
pnpm format              # 格式化代码
pnpm check               # 运行所有检查（循环依赖、依赖、类型、拼写）
pnpm check:type          # 仅类型检查

# 测试
pnpm test:unit           # 运行单元测试（vitest + happy-dom）
pnpm test:e2e            # 运行 E2E 测试

# 其他
pnpm clean               # 清理构建产物和缓存
pnpm reinstall           # 清理后重新安装依赖
```

## 项目架构

```
web/
├── apps/
│   └── web-ele/           # 主应用（Element Plus 版本）
│       └── src/
│           ├── api/       # API 接口定义
│           ├── components/# 业务组件（表格、对话框、设计器等）
│           ├── layouts/   # 布局组件
│           ├── router/    # 路由配置（动态路由在 routes/modules/）
│           ├── store/     # Pinia 状态管理
│           ├── views/     # 页面视图
│           │   ├── _core/ # 核心业务模块（用户、角色、菜单、权限等）
│           │   └── dashboard/
│           └── locales/   # 国际化文件（zh-CN, en-US, zh-TW）
│
├── packages/
│   ├── @core/             # 基础 SDK 和 UI 组件（无业务逻辑）
│   │   ├── base/          # 基础工具
│   │   ├── composables/   # 组合式函数
│   │   ├── preferences/   # 偏好设置
│   │   └── ui-kit/        # UI 组件库
│   └── effects/           # 业务效果包（有副作用的代码）
│       ├── access/        # 权限控制
│       ├── common-ui/     # 通用 UI
│       ├── hooks/         # 业务 Hooks
│       ├── layouts/       # 布局
│       ├── plugins/       # 插件
│       └── request/       # 请求封装
│
├── internal/              # 内部工具包
│   ├── lint-configs/      # ESLint/Stylelint 配置
│   ├── node-utils/        # Node 工具
│   ├── tailwind-config/   # Tailwind 配置
│   ├── tsconfig/          # TypeScript 配置
│   └── vite-config/       # Vite 配置
│
└── scripts/               # 构建脚本
```

## 关键约定

### 路径别名
- `#/*` 映射到 `apps/web-ele/src/*`（应用内模块导入）
- 使用 `@vben/*` 导入 workspace 包

### API 请求
- 请求客户端在 `apps/web-ele/src/api/request.ts`
- API 定义在 `apps/web-ele/src/api/core/`
- 开发环境 API 代理地址：`/basic-api`（配置在 `.env.development`）

### 路由
- 动态路由文件位于 `apps/web-ele/src/router/routes/modules/`
- 路由通过 `import.meta.glob` 自动加载
- 权限控制在 `apps/web-ele/src/router/guard.ts`

### 组件
- 业务组件在 `apps/web-ele/src/components/`
- 核心组件包含：zq-table、zq-dialog、zq-drawer、form-design、dashboard-design、workflow-designer

### 状态管理
- 使用 Pinia，Store 定义在 `apps/web-ele/src/store/`
- 全局状态包在 `packages/stores/`

### 国际化
- 语言文件在 `apps/web-ele/src/locales/langs/`
- 支持 zh-CN、en-US、zh-TW

## Git 提交规范

项目使用 commitlint，提交信息格式：`type(scope): message`

常用类型：`feat`、`fix`、`docs`、`style`、`refactor`、`test`、`chore`

## 环境要求

- Node.js >= 20.10.0
- pnpm >= 9.12.0（项目锁定 pnpm@10.14.0）