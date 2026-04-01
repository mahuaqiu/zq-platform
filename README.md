# zq-platform

## 🏗️ 技术栈

### 后端技术

**FastAPI 后端 (backend-fastapi)**
- **核心框架**: FastAPI 0.115+
- **ORM**: SQLAlchemy 2.0+ (异步)
- **数据库**: PostgreSQL 16+
- **迁移**: Alembic
- **认证**: JWT
- **缓存**: Redis
- **Python**: 3.12+

### 前端技术

- **核心框架**: Vue 3.x
- **构建工具**: Vite 5.x
- **UI 组件库**: Element Plus
- **状态管理**: Pinia
- **路由**: Vue Router
- **HTTP 客户端**: Axios
- **工具库**: VueUse, dayjs, lodash-es
- **代码规范**: ESLint, Prettier, Stylelint
- **包管理**: pnpm 10.14.0
- **Monorepo**: Turbo

## 📁 项目结构

```
zq-platform/
├── backend-fastapi/         # FastAPI 后端（推荐）
│   ├── app/                # 核心应用模块
│   ├── core/               # 核心业务模块
│   │   ├── auth/           # 认证授权
│   │   ├── user/           # 用户管理
│   │   ├── role/           # 角色管理
│   │   ├── permission/     # 权限管理
│   │   ├── dept/           # 部门管理
│   │   ├── post/           # 岗位管理
│   │   ├── menu/           # 菜单管理
│   │   ├── login_log/      # 登录日志
│   │   ├── oauth/          # OAuth 登录
│   │   ├── env_machine/    # 执行机管理
│   │   ├── feature_analysis/ # 特性分析
│   │   ├── issues_analysis/  # 问题分析
│   │   └── websocket/      # WebSocket 支持
│   ├── scripts/            # 工具脚本
│   │   ├── dumpdata.py     # 数据导出
│   │   ├── loaddata.py     # 数据导入
│   │   └── init_env_machine_menu.py # 初始化设备菜单
│   ├── alembic/            # 数据库迁移
│   ├── env/                # 环境配置
│   ├── requirements.txt    # Python 依赖
│   └── main.py            # 应用入口
│
└── web/                    # Vue 前端 (Monorepo)
    ├── apps/
    │   └── web-ele/        # Element Plus 版本主应用
    │       ├── src/
    │       │   ├── api/    # API 接口
    │       │   ├── views/  # 页面组件
    │       │   ├── router/ # 路由配置
    │       │   └── store/  # 状态管理
    │       └── package.json
    ├── packages/           # 共享包
    │   ├── @core/          # 核心包
    │   ├── effects/        # 副作用包
    │   ├── hooks/          # Hooks
    │   ├── icons/          # 图标
    │   ├── locales/        # 国际化
    │   ├── stores/         # 状态管理
    │   └── utils/          # 工具函数
    ├── internal/           # 内部工具
    └── package.json        # 根配置
```

#### FastAPI 后端（推荐用于高性能场景）

1. **进入 FastAPI 目录**
```bash
cd zq-platform/backend-fastapi
```

2. **创建虚拟环境**
```bash
conda create -n zq-fastapi python=3.12
conda activate zq-fastapi
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **配置环境变量**
```bash
cp env/example.env env/dev.env
# 编辑 env/dev.env 配置数据库连接
```

5. **数据库迁移**
```bash
alembic revision --autogenerate -m "init tables"
alembic upgrade head

# 导入初始数据（可选）
python scripts/loaddata.py db_init.json
```

6. **初始化执行机管理菜单（可选）**
```bash
python scripts/init_env_machine_menu.py
```

7. **启动服务**
```bash
python main.py
# 或
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

8. **访问 API 文档**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 前端安装

1. **进入前端目录**
```bash
cd zq-platform/web
```

2. **安装依赖**
```bash
pnpm install
```

3. **配置环境变量**
```bash
cd apps/web-ele
cp .env.development .env
# 编辑 .env 文件，配置后端 API 地址
```

4. **启动开发服务器**
```bash
# 在 web 根目录下
pnpm dev
```

5. **构建生产版本**
```bash
pnpm build:ele
```

## 📝 默认账号

初始化数据后，可使用以下账号登录：

- 账号: `superadmin`
- 密码: 请查看 `123456` 或联系管理员

## 🔧 主要功能模块

### 系统管理
- **用户管理**: 用户的增删改查、密码重置、状态管理
- **角色管理**: 角色权限分配、数据权限控制
- **权限管理**: 接口权限、按钮权限细粒度控制
- **部门管理**: 树形部门结构管理
- **岗位管理**: 岗位信息维护
- **菜单管理**: 动态菜单配置、路由管理

### 设备管理
- **执行机管理**: 设备资源池、调度与状态监控
- **多命名空间支持**: Gamma、APP、AV、公共设备、手工使用

### 分析功能
- **特性分析**: 特性跟踪与分析
- **问题分析**: 问题跟踪与分析

### 系统日志
- **登录日志**: 用户登录记录、IP 地理位置

## 🔐 API 文档

**FastAPI 后端**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🛠️ 开发指南

### 后端开发

1. **添加新模块**
   - 在 `core/` 或创建新 app
   - 定义 models、schemas、services、api
   - 在 router 中注册路由

2. **API 开发规范**
   - 统一返回格式
   - 异常处理
   - 权限验证

### 前端开发

1. **添加新页面**
   - 在 `src/views/` 创建页面组件
   - 在 `src/router/routes/modules/` 添加路由
   - 在 `src/api/` 添加接口定义

2. **组件开发规范**
   - 使用 Element Plus 组件
   - 优先使用 Tailwind CSS
   - 支持暗黑模式
   - 图标从 `@vben/icons` 导入

## 📦 部署
1. **后端部署**
   - 使用 Gunicorn + Nginx
   - 配置 Supervisor 进程守护
   - 配置 SSL 证书

2. **前端部署**
   - 执行 `pnpm build` 构建
   - 将 `dist` 目录部署到 Nginx
   - 配置反向代理
