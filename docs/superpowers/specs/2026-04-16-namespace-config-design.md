# Namespace 配置动态化设计

## 背景

当前项目中 `meeting_gamma`、`meeting_app`、`meeting_av`、`meeting_public` 四个 namespace 在多处硬编码，导致：
1. 前端 3 个文件重复定义（`types.ts`、`upgrade.vue`、`config.vue`）
2. 后端 2 处重复定义（`config_template/service.py`、`env_machine/service.py`）
3. 添加或隐藏 namespace 需修改多处代码

## 目标

将 namespace 配置移至 `.env` 文件，实现：
- 一处配置，多处生效
- 添加/隐藏 namespace 只需修改配置文件
- 保持前后端独立配置，避免耦合

## 配置格式

采用 JSON 格式，键为 namespace value，值为显示标签：

```bash
# 后端
NAMESPACE_CONFIG={"meeting_gamma":"集成验证","meeting_app":"APP","meeting_av":"音视频","meeting_public":"公共设备"}

# 前端
VITE_NAMESPACE_CONFIG={"meeting_gamma":"集成验证","meeting_app":"APP","meeting_av":"音视频","meeting_public":"公共设备"}
```

**扩展/隐藏示例：**
- 添加新 namespace：直接在 JSON 中添加新键值对
- 隐藏 namespace：从 JSON 中删除对应条目

## 改动清单

### 后端

| 文件 | 改动 |
|------|------|
| `env/example.env` | 新增 `NAMESPACE_CONFIG` 配置项说明 |
| `env/dev.env` | 新增实际配置值 |
| `app/config.py` | 新增 `NAMESPACE_CONFIG` 字段解析（JSON.loads） |
| `config_template/service.py` | 删除 `VALID_NAMESPACE_LIST` 硬编码，引用 `config.NAMESPACE_CONFIG.keys()` |
| `env_machine/service.py` | 删除 `VALID_NAMESPACES` 硬编码，引用 `config.NAMESPACE_CONFIG.keys()` |

### 前端

| 文件 | 改动 |
|------|------|
| `.env.development` | 新增 `VITE_NAMESPACE_CONFIG` |
| `.env.production` | 新增 `VITE_NAMESPACE_CONFIG` |
| `types.ts` | 改为动态读取配置生成 `NAMESPACE_OPTIONS` 和 `NAMESPACE_DISPLAY_MAP`，导出供其他组件使用 |
| `upgrade.vue` | 删除重复的 namespace 定义，引用 `types.ts` 导出 |
| `config.vue` | 删除重复的 namespace 定义，引用 `types.ts` 导出 |

## 核心代码示例

### 后端 config.py

```python
import json
import os

NAMESPACE_CONFIG: dict = json.loads(
    os.getenv("NAMESPACE_CONFIG", '{"meeting_gamma":"集成验证","meeting_app":"APP","meeting_av":"音视频","meeting_public":"公共设备"}')
)
```

### 后端 service.py

```python
from app.config import NAMESPACE_CONFIG

# 替换硬编码
VALID_NAMESPACE_LIST = list(NAMESPACE_CONFIG.keys())
```

### 前端 types.ts

```typescript
// 动态解析配置
const config = JSON.parse(
  import.meta.env.VITE_NAMESPACE_CONFIG ||
  '{"meeting_gamma":"集成验证","meeting_app":"APP","meeting_av":"音视频","meeting_public":"公共设备"}'
);

// 命名空间选项（用于筛选下拉框）
export const NAMESPACE_OPTIONS = [
  { label: '全部', value: '' },
  ...Object.entries(config).map(([value, label]) => ({ label: String(label), value }))
];

// 命名空间中文映射（用于表格显示）
export const NAMESPACE_DISPLAY_MAP: Record<string, string> = config;
```

### 前端页面引用

```typescript
// upgrade.vue / config.vue
import { NAMESPACE_OPTIONS, NAMESPACE_DISPLAY_MAP } from './types';
```

## 默认值处理

前后端均提供默认值，确保在配置缺失时系统仍能正常运行：
- 后端默认：`{"meeting_gamma":"集成验证","meeting_app":"APP","meeting_av":"音视频","meeting_public":"公共设备"}`
- 前端默认：同上

## 注意事项

1. JSON 字符串在 `.env` 中不需要引号包裹（ dotenv 会自动处理）
2. 修改配置后需重启服务生效
3. 前端 Vite 环境变量必须以 `VITE_` 开头才能被读取