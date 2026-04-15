# Namespace 配置动态化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 namespace 配置从硬编码改为 .env 文件动态加载，一处配置多处生效

**Architecture:** 前后端独立配置，JSON 格式，错误时使用默认值。后端使用 Settings 类 @property 模式，前端在 types.ts 中统一解析并导出。

**Tech Stack:** Python pydantic-settings, TypeScript Vite env, JSON 配置

---

## 文件结构

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `backend-fastapi/env/example.env` | Modify | 新增 NAMESPACE_CONFIG 配置项说明 |
| `backend-fastapi/env/dev.env` | Modify | 新增实际配置值 |
| `backend-fastapi/app/config.py` | Modify | 新增 NAMESPACE_CONFIG 字段和 namespace_map 属性 |
| `backend-fastapi/core/config_template/service.py` | Modify | 删除硬编码，引用 settings.namespace_map |
| `backend-fastapi/core/env_machine/service.py` | Modify | 删除硬编码，引用 settings.namespace_map |
| `web/apps/web-ele/.env.development` | Modify | 新增 VITE_NAMESPACE_CONFIG |
| `web/apps/web-ele/.env.production` | Modify | 新增 VITE_NAMESPACE_CONFIG |
| `web/apps/web-ele/src/views/env-machine/types.ts` | Modify | 动态解析配置生成 OPTIONS 和 DISPLAY_MAP |
| `web/apps/web-ele/src/views/env-machine/upgrade.vue` | Modify | 删除本地 NAMESPACE_OPTIONS，导入 types.ts |
| `web/apps/web-ele/src/views/env-machine/config.vue` | Modify | 删除本地定义，导入 types.ts |

---

## Task 1: 后端配置文件 - env 文件

**Files:**
- Modify: `backend-fastapi/env/example.env`
- Modify: `backend-fastapi/env/dev.env`

- [ ] **Step 1: 添加 NAMESPACE_CONFIG 到 example.env**

在 `backend-fastapi/env/example.env` 文件末尾添加配置说明：

```bash
# Namespace 配置（JSON 格式）
# 键为 namespace value，值为显示标签
# 示例：NAMESPACE_CONFIG={"meeting_gamma":"集成验证","meeting_app":"APP","meeting_av":"音视频","meeting_public":"公共设备"}
NAMESPACE_CONFIG=
```

- [ ] **Step 2: 添加 NAMESPACE_CONFIG 到 dev.env**

在 `backend-fastapi/env/dev.env` 文件末尾添加：

```bash
# Namespace 配置（JSON 格式）
NAMESPACE_CONFIG={"meeting_gamma":"集成验证","meeting_app":"APP","meeting_av":"音视频","meeting_public":"公共设备"}
```

- [ ] **Step 3: Commit 后端配置文件**

```bash
git add backend-fastapi/env/example.env backend-fastapi/env/dev.env
git commit -m "feat: 后端新增 NAMESPACE_CONFIG 配置项"
```

---

## Task 2: 后端 config.py - 配置解析

**Files:**
- Modify: `backend-fastapi/app/config.py`

- [ ] **Step 1: 添加 NAMESPACE_CONFIG 字段到 Settings 类**

在第 72 行（TASK_AGGREGATION_CONFIG 后面）添加：

```python
    # Namespace 配置（JSON 格式）
    NAMESPACE_CONFIG: str = ""
```

- [ ] **Step 2: 添加 namespace_map 属性**

在第 179 行（task_aggregation_map 属性后面）添加：

```python
    @property
    def namespace_map(self) -> Dict[str, str]:
        """解析 namespace 配置"""
        default_config = {"meeting_gamma": "集成验证", "meeting_app": "APP", "meeting_av": "音视频", "meeting_public": "公共设备"}
        if not self.NAMESPACE_CONFIG:
            return default_config
        try:
            return json.loads(self.NAMESPACE_CONFIG)
        except json.JSONDecodeError as e:
            logger.warning(f"NAMESPACE_CONFIG JSON 解析失败: {e}, 使用默认配置")
            return default_config
```

- [ ] **Step 3: Commit config.py**

```bash
git add backend-fastapi/app/config.py
git commit -m "feat: config.py 新增 namespace_map 属性"
```

---

## Task 3: 后端 config_template/service.py - 删除硬编码

**Files:**
- Modify: `backend-fastapi/core/config_template/service.py`

- [ ] **Step 1: 删除硬编码 VALID_NAMESPACE_LIST**

删除第 36-37 行的硬编码：
```python
# 删除这两行
# 合法的命名空间列表（用于配置下发筛选）
VALID_NAMESPACE_LIST = ["meeting_gamma", "meeting_app", "meeting_av", "meeting_public"]
```

- [ ] **Step 2: 添加 settings 导入和动态引用**

在第 31 行（logger 后面）添加导入和引用：

```python
from app.config import get_settings

settings = get_settings()

# 合法的命名空间列表（用于配置下发筛选，从配置动态获取）
VALID_NAMESPACE_LIST = list(settings.namespace_map.keys())
```

- [ ] **Step 3: Commit config_template/service.py**

```bash
git add backend-fastapi/core/config_template/service.py
git commit -m "feat: config_template 使用动态 namespace 配置"
```

---

## Task 4: 后端 env_machine/service.py - 删除硬编码

**Files:**
- Modify: `backend-fastapi/core/env_machine/service.py`

- [ ] **Step 1: 删除硬编码 VALID_NAMESPACES**

删除第 195-196 行的硬编码：
```python
# 删除这两行
VALID_NAMESPACES = ['meeting_gamma', 'meeting_app', 'meeting_av', 'meeting_public']
```

- [ ] **Step 2: 添加 settings 导入**

在文件头部（约第 20 行，from app.base_service 导入后）添加：

```python
from app.config import get_settings

settings = get_settings()
```

- [ ] **Step 3: 添加动态引用**

在第 198 行（filters 定义前）添加：

```python
        # 定义有效的命名空间列表（排除手工使用，从配置动态获取）
        VALID_NAMESPACES = list(settings.namespace_map.keys())
```

- [ ] **Step 4: Commit env_machine/service.py**

```bash
git add backend-fastapi/core/env_machine/service.py
git commit -m "feat: env_machine 使用动态 namespace 配置"
```

---

## Task 5: 前端配置文件 - .env

**Files:**
- Modify: `web/apps/web-ele/.env.development`
- Modify: `web/apps/web-ele/.env.production`

- [ ] **Step 1: 添加 VITE_NAMESPACE_CONFIG 到 .env.development**

在 `web/apps/web-ele/.env.development` 文件末尾添加：

```bash
# Namespace 配置（JSON 格式）
VITE_NAMESPACE_CONFIG={"meeting_gamma":"集成验证","meeting_app":"APP","meeting_av":"音视频","meeting_public":"公共设备"}
```

- [ ] **Step 2: 添加 VITE_NAMESPACE_CONFIG 到 .env.production**

在 `web/apps/web-ele/.env.production` 文件末尾添加：

```bash
# Namespace 配置（JSON 格式）
VITE_NAMESPACE_CONFIG={"meeting_gamma":"集成验证","meeting_app":"APP","meeting_av":"音视频","meeting_public":"公共设备"}
```

- [ ] **Step 3: Commit 前端配置文件**

```bash
git add web/apps/web-ele/.env.development web/apps/web-ele/.env.production
git commit -m "feat: 前端新增 VITE_NAMESPACE_CONFIG 配置"
```

---

## Task 6: 前端 types.ts - 动态解析配置

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/types.ts`

- [ ] **Step 1: 替换 NAMESPACE_OPTIONS 定义**

将第 30-36 行替换为：

```typescript
/**
 * 默认 Namespace 配置
 */
const DEFAULT_NAMESPACE_CONFIG: Record<string, string> = {
  meeting_gamma: '集成验证',
  meeting_app: 'APP',
  meeting_av: '音视频',
  meeting_public: '公共设备',
};

/**
 * 动态解析 Namespace 配置
 */
let namespaceConfig: Record<string, string>;
try {
  namespaceConfig = JSON.parse(
    import.meta.env.VITE_NAMESPACE_CONFIG ||
    JSON.stringify(DEFAULT_NAMESPACE_CONFIG)
  );
} catch (e) {
  console.error('VITE_NAMESPACE_CONFIG JSON 解析失败，使用默认配置:', e);
  namespaceConfig = DEFAULT_NAMESPACE_CONFIG;
}

/**
 * 命名空间选项（用于筛选下拉框）
 */
export const NAMESPACE_OPTIONS = [
  { label: '全部', value: '' },
  ...Object.entries(namespaceConfig).map(([value, label]) => ({
    label: String(label),
    value,
  })),
];

/**
 * 命名空间选项（带全部选项，value='all'）
 */
export const NAMESPACE_OPTIONS_WITH_ALL = [
  { label: '全部', value: 'all' },
  ...Object.entries(namespaceConfig).map(([value, label]) => ({
    label: String(label),
    value,
  })),
];

/**
 * 命名空间选项（弹窗用，第一项为"全部命名空间"）
 */
export const NAMESPACE_OPTIONS_DIALOG = [
  { label: '全部命名空间', value: '' },
  ...Object.entries(namespaceConfig).map(([value, label]) => ({
    label: String(label),
    value,
  })),
];

/**
 * 命名空间中文映射（用于表格显示）
 */
export const NAMESPACE_DISPLAY_MAP: Record<string, string> = namespaceConfig;
```

- [ ] **Step 2: Commit types.ts**

```bash
git add web/apps/web-ele/src/views/env-machine/types.ts
git commit -m "feat: types.ts 动态解析 namespace 配置"
```

---

## Task 7: 前端 upgrade.vue - 删除重复定义

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/upgrade.vue`

- [ ] **Step 1: 添加导入**

在第 2 行的 import type 后面添加导入：

```typescript
import { NAMESPACE_OPTIONS_WITH_ALL, NAMESPACE_DISPLAY_MAP } from './types';
```

- [ ] **Step 2: 删除本地 NAMESPACE_OPTIONS 定义**

删除第 46-52 行：

```typescript
// 删除这些行
const NAMESPACE_OPTIONS = [
  { label: '全部', value: 'all' },
  { label: '集成验证', value: 'meeting_gamma' },
  { label: 'APP', value: 'meeting_app' },
  { label: '音视频', value: 'meeting_av' },
  { label: '公共设备', value: 'meeting_public' },
];
```

- [ ] **Step 3: 使用导入的常量**

将代码中引用的 `NAMESPACE_OPTIONS` 改为 `NAMESPACE_OPTIONS_WITH_ALL`（筛选表单用的是 value='all'）

- [ ] **Step 4: Commit upgrade.vue**

```bash
git add web/apps/web-ele/src/views/env-machine/upgrade.vue
git commit -m "feat: upgrade.vue 删除重复 namespace 定义，使用 types.ts 导出"
```

---

## Task 8: 前端 config.vue - 删除重复定义

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/config.vue`

- [ ] **Step 1: 添加导入**

在第 2 行的 import type 后面添加导入：

```typescript
import { NAMESPACE_OPTIONS_WITH_ALL, NAMESPACE_OPTIONS_DIALOG, NAMESPACE_DISPLAY_MAP } from './types';
```

- [ ] **Step 2: 删除本地 NAMESPACE_OPTIONS 定义**

删除第 61-67 行：

```typescript
// 删除这些行
const NAMESPACE_OPTIONS = [
  { label: '全部', value: 'all' },
  { label: '集成验证', value: 'meeting_gamma' },
  { label: 'APP', value: 'meeting_app' },
  { label: '音视频', value: 'meeting_av' },
  { label: '公共设备', value: 'meeting_public' },
];
```

- [ ] **Step 3: 删除本地 NAMESPACE_OPTIONS_DIALOG 定义**

删除第 70-76 行：

```typescript
// 删除这些行
const NAMESPACE_OPTIONS_DIALOG = [
  { label: '全部命名空间', value: '' },
  { label: '集成验证', value: 'meeting_gamma' },
  { label: 'APP', value: 'meeting_app' },
  { label: '音视频', value: 'meeting_av' },
  { label: '公共设备', value: 'meeting_public' },
];
```

- [ ] **Step 4: 删除本地 NAMESPACE_DISPLAY 定义**

删除第 79-84 行：

```typescript
// 删除这些行
const NAMESPACE_DISPLAY: Record<string, string> = {
  meeting_gamma: '集成验证',
  meeting_app: 'APP',
  meeting_av: '音视频',
  meeting_public: '公共设备',
};
```

- [ ] **Step 5: 使用导入的常量**

将代码中引用的 `NAMESPACE_OPTIONS` 改为 `NAMESPACE_OPTIONS_WITH_ALL`，`NAMESPACE_DISPLAY` 改为 `NAMESPACE_DISPLAY_MAP`

- [ ] **Step 6: Commit config.vue**

```bash
git add web/apps/web-ele/src/views/env-machine/config.vue
git commit -m "feat: config.vue 删除重复 namespace 定义，使用 types.ts 导出"
```

---

## Task 9: 验证测试

**Files:**
- None (手动验证)

- [ ] **Step 1: 启动后端服务验证**

```bash
cd backend-fastapi
python main.py
```

访问 Swagger UI http://localhost:8000/docs，检查配置模板相关接口是否正常。

- [ ] **Step 2: 启动前端服务验证**

```bash
cd web
pnpm dev
```

访问升级管理页面和配置管理页面，检查 namespace 下拉框是否正常显示。

- [ ] **Step 3: 验证配置修改生效**

修改 `.env` 文件中的 NAMESPACE_CONFIG，添加或删除一个 namespace，重启服务验证变化生效。

---

## Task 10: 最终提交

**Files:**
- None (git 操作)

- [ ] **Step 1: 检查所有改动**

```bash
git status
```

- [ ] **Step 2: 推送到远程仓库**

```bash
git push origin main
```

---

## 扩展说明

添加新 namespace（如 `meeting_test`）只需修改 `.env` 文件：

```bash
# 后端
NAMESPACE_CONFIG={"meeting_gamma":"集成验证","meeting_app":"APP","meeting_av":"音视频","meeting_public":"公共设备","meeting_test":"测试环境"}

# 前端
VITE_NAMESPACE_CONFIG={"meeting_gamma":"集成验证","meeting_app":"APP","meeting_av":"音视频","meeting_public":"公共设备","meeting_test":"测试环境"}
```

重启服务后即可生效。