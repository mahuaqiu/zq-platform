# 日志系统设计方案

## 概述

为 zq-platform 后端实现持久化日志系统，使用 loguru 库替换现有的 Python logging，记录请求参数、返回结果及核心业务操作日志。

## 需求

- 日志目录：`backend-fastapi/logs/`
- 日志文件：最多 5 个文件，每个文件最大 20MB（总计 100MB）
- 日志格式：标准格式（时间、级别、模块、消息）
- 请求日志：记录完整请求参数和返回结果，不做敏感信息过滤
- 业务日志：记录核心业务操作

## 技术方案

### 组件结构

```
backend-fastapi/
├── logs/                           # 新建目录（gitignore）
├── utils/
│   ├── logging_config.py           # loguru 配置模块
│   └── request_log_middleware.py   # 请求日志中间件
└── main.py                         # 启动时初始化日志
```

### 1. 日志配置模块 (`utils/logging_config.py`)

**功能：**
- 配置 loguru 的 RotatingFileHandler
- 添加 stderr 控制台输出（开发环境）
- 提供统一的日志获取函数

**配置参数：**
```python
LOG_DIR = "logs"
LOG_FILE = "app.log"
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
RETENTION_COUNT = 5                # 5 个文件
LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
```

**核心接口：**
```python
def setup_logging():
    """初始化日志配置，应用启动时调用"""

def get_logger(name: str = None) -> Logger:
    """获取日志实例，兼容现有 logging.getLogger() 调用"""
```

### 2. 请求日志中间件 (`utils/request_log_middleware.py`)

**功能：**
- 记录每个 HTTP 请求的完整信息
- 记录请求参数（Query、Body、Path）
- 记录响应状态码和响应体
- 记录请求耗时

**日志内容：**
```
请求日志：
- 时间戳
- 客户端 IP
- 请求方法 (GET/POST/PUT/DELETE)
- 请求路径
- 请求参数 (Query + Body)
- 请求头（可选）

响应日志：
- 响应状态码
- 响应体内容
- 请求耗时 (ms)
```

**特殊处理：**
- 大响应体（>10KB）截断为 `{truncated, size=XXXkb}`
- WebSocket 请求不记录
- 静态资源请求不记录（docs、redoc、openapi.json）

### 3. 核心业务日志改造

改造现有使用 `logging.getLogger()` 的模块，替换为 loguru：

| 模块 | 改造内容 |
|------|---------|
| `scheduler/service.py` | 调度器启动/关闭/任务执行日志 |
| `utils/auth_middleware.py` | 认证失败日志 |
| `core/auth/api.py` | 登录/登出/Token刷新日志 |
| `core/user/service.py` | 用户创建/更新/删除日志 |
| `core/env_machine/pool_manager.py` | 执行机池管理日志 |
| `core/websocket/consumers/*.py` | WebSocket 连接日志 |

### 4. 依赖管理

新增依赖：
```
loguru>=0.7.0
```

添加到 `requirements.txt`。

### 5. 目录和 gitignore

在 `backend-fastapi/.gitignore` 添加：
```
logs/
*.log
```

## 数据流

```
请求进入 → RequestLogMiddleware → 记录请求信息 → 业务处理 → 记录响应信息 → 返回响应

业务模块调用 → get_logger("module") → loguru → 写入 logs/app.log
```

## 错误处理

- 日志目录不存在时自动创建
- 日志文件写入失败时降级到 stderr 输出
- 中间件日志记录失败不影响请求正常处理

## 测试要点

1. 启动应用后验证 `logs/app.log` 文件创建
2. 发送 API 请求验证请求日志记录
3. 触发认证失败验证日志记录
4. 验证日志文件旋转（手动测试或模拟大日志量）
5. 验证各核心模块日志改造生效

## 迁移步骤

1. 安装 loguru 依赖
2. 创建 `utils/logging_config.py`
3. 创建 `utils/request_log_middleware.py`
4. 在 `main.py` 初始化日志配置并添加中间件
5. 改造各核心模块的日志调用
6. 更新 `.gitignore`