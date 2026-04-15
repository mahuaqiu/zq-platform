# 配置管理功能设计文档

> 日期：2026-04-15
> 状态：设计评审中

## 1. 概述

### 1.1 背景

当前设备管理模块已有"设备列表"和"设备升级"两个功能页面。需要新增"配置管理"功能，用于管理执行机（Worker）的配置文件，支持按模板批量下发配置到目标机器。

### 1.2 目标

- 提供配置模板管理功能（新建、编辑、删除）
- 支持批量下发配置到选定的机器
- 自动追踪配置同步状态

## 2. 功能需求

### 2.1 配置模板管理

| 功能 | 说明 |
|------|------|
| 新建模板 | 输入模板名称、适用命名空间、备注、完整YAML配置内容 |
| 编辑模板 | 修改模板内容，保存后自动生成新版本号 |
| 删除模板 | 二次确认后删除，已下发的配置不受影响 |
| 模板列表 | 左侧展示所有模板，点击选中高亮 |

**模板字段**：
- `name`: 模板名称
- `namespace`: 适用命名空间（可选，默认全部）
- `note`: 备注说明
- `config_content`: 完整的 YAML 配置内容
- `version`: 自动生成的时间戳版本号（格式：YYYYMMDD-HHMMSS）

### 2.2 配置下发

**下发流程**：
1. 选择配置模板（左侧点击选中）
2. 筛选目标机器（命名空间、设备类型、IP）
3. 勾选需要下发的机器（仅"在线"状态可勾选）
4. 点击"下发配置"按钮

**下发状态追踪**：
- 下发后，机器状态变为"配置更新中"
- 机器接收配置后自动重启服务
- 重启注册时上报 `config_version`
- 版本匹配后，状态恢复"在线"，配置状态显示"已同步"

### 2.3 配置状态对比

| 配置状态 | 条件 | 显示颜色 |
|----------|------|----------|
| 已同步 | 机器上报版本 = 当前模板版本 | 绿色 |
| 待更新 | 机器上报版本 ≠ 当前模板版本 | 橙色 |
| 更新中 | 下发后等待重启 | 紫色 |
| 离线 | 机器离线 | 红色 |

## 3. API 设计

### 3.1 配置模板 API

**后端模块**：`backend-fastapi/core/config_template/`

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/core/config-template/list` | GET | 获取模板列表 |
| `/api/core/config-template/{id}` | GET | 获取模板详情 |
| `/api/core/config-template` | POST | 新建模板 |
| `/api/core/config-template/{id}` | PUT | 编辑模板 |
| `/api/core/config-template/{id}` | DELETE | 删除模板 |

**模板 Schema**：
```python
class ConfigTemplateCreate(BaseModel):
    name: str              # 模板名称
    namespace: str | None  # 适用命名空间（可选）
    note: str | None       # 备注
    config_content: str    # YAML 配置内容

class ConfigTemplate(BaseModel):
    id: str
    name: str
    namespace: str | None
    note: str | None
    config_content: str
    version: str           # YYYYMMDD-HHMMSS
    sys_create_datetime: datetime
    sys_update_datetime: datetime
```

### 3.2 配置下发 API

**下发预览接口**：
```
GET /api/core/config-template/preview
参数：namespace, device_type, ip, template_id
返回：机器列表 + 配置状态
```

**执行下发接口**：
```
POST /api/core/config-template/deploy
参数：
{
  "template_id": "xxx",
  "machine_ids": ["id1", "id2", ...]
}
返回：
{
  "success_count": 10,
  "failed_count": 2,
  "details": [...]
}
```

### 3.3 Worker 配置接收接口

**接口路径**：`POST /worker/config`

**请求参数**：
```json
{
  "config_content": "完整的 YAML 配置文件内容",
  "config_version": "20260415-143000"
}
```

**机器端处理**：
1. 接收配置内容，保存到本地配置文件
2. 记录 `config_version` 到本地
3. 重启 Worker 服务
4. 重启注册时上报 `config_version`

### 3.4 机器注册接口变更

**新增字段**：`config_version`

```json
{
  "namespace": "meeting_public",
  "ip": "192.168.0.101",
  "port": "8088",
  "device_type": "windows",
  "version": "20260415",
  "config_version": "20260415-143000"  // 新增
}
```

## 4. 数据模型

### 4.1 配置模板表

```sql
CREATE TABLE config_template (
    id UUID PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    namespace VARCHAR(64),
    note TEXT,
    config_content TEXT NOT NULL,
    version VARCHAR(20) NOT NULL,  -- YYYYMMDD-HHMMSS
    sort INTEGER DEFAULT 0,
    is_deleted BOOLEAN DEFAULT FALSE,
    sys_create_datetime TIMESTAMP,
    sys_update_datetime TIMESTAMP,
    sys_creator_id UUID,
    sys_modifier_id UUID
);
```

### 4.2 执行机表变更

**新增字段**：`config_version`

```sql
ALTER TABLE env_machine ADD COLUMN config_version VARCHAR(20);
```

## 5. 页面设计

### 5.1 页面布局

**左右分栏布局**：
- **左侧（300px）**：配置模板列表 + 新建按钮
- **右侧**：下发配置区

### 5.2 左侧模板区

- 模板列表卡片，每行包含：
  - 模板名称
  - 适用命名空间
  - 版本号（YYYYMMDD-HHMMSS）
  - 编辑/删除按钮
- 点击选中高亮（蓝色边框 + 背景）
- 顶部"新建"按钮

### 5.3 右侧下发区

**内容从上到下**：
1. 筛选条件行（命名空间、设备类型、IP搜索、查询/重置按钮）
2. 当前模板提示条（橙色背景，显示模板名称+版本）
3. 统计信息（可下发/更新中/离线数量）
4. 机器表格（勾选框、IP、命名空间、设备类型、机器状态、配置状态、配置版本）
5. 操作按钮（下发配置）

### 5.4 弹窗设计

**新建/编辑模板弹窗**：
- 弹窗宽度：720px
- 基本信息：模板名称、适用命名空间、备注
- 配置内容：YAML 编辑区（深色背景，320px 高度）
- 操作按钮：取消、保存模板

**删除确认弹窗**：
- 提示"删除后将无法恢复，已下发的配置不受影响"
- 显示模板名称
- 操作按钮：取消、确认删除

## 6. 状态流转

### 6.1 配置下发状态流转

```
[在线+已同步] --> 选择下发 --> [配置更新中] --> 机器接收 --> [机器重启] --> [注册上报] --> [在线+已同步]
```

### 6.2 机器可勾选条件

| 机器状态 | 配置状态 | 是否可勾选 |
|----------|----------|------------|
| 在线 | 已同步 | ✓ 可勾选 |
| 在线 | 待更新 | ✓ 可勾选 |
| 配置更新中 | 更新中 | ✗ 不可勾选 |
| 离线 | 离线 | ✗ 不可勾选 |

## 7. 实现要点

### 7.1 后端实现

1. 新建 `config_template` 模块（model.py, schema.py, service.py, api.py）
2. 在 `env_machine.model.py` 新增 `config_version` 字段
3. 在 `env_machine.api.py` 修改注册接口，接收 `config_version`
4. 实现下发逻辑：调用 Worker 的 `/worker/config` 接口

### 7.2 前端实现

1. 新建 `web/apps/web-ele/src/views/config-template/index.vue`
2. 新建 `web/apps/web-ele/src/api/core/config-template.ts`
3. 新建路由配置
4. 新建菜单初始化脚本

### 7.3 Worker 实现

1. 新增 `/worker/config` 接口，接收配置内容
2. 保存配置文件到本地
3. 记录 `config_version`
4. 重启服务
5. 注册时上报 `config_version`

## 8. 菜单配置

**菜单位置**：设备管理 > 配置管理

```json
{
  "name": "配置管理",
  "path": "/env-machine/config",
  "icon": "setting",
  "parent": "设备管理"
}
```

## 9. 参考资料

- 现有设备升级页面：`web/apps/web-ele/src/views/env-machine/upgrade.vue`
- Worker 配置示例：`D:\code\autotest\config\worker.yaml`