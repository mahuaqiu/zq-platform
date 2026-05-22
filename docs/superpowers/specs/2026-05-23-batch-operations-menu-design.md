---
name: batch-operations-menu
description: 设备列表页面批量操作按钮收纳菜单设计
---

# 设备列表页面批量操作按钮收纳菜单设计

## 背景

设备列表页面当前有多个批量操作按钮（批量导入、批量删除、批量执行命令），用户需要新增批量启用和批量停用按钮。但按钮数量过多会导致界面拥挤，需要引入按钮收纳功能来优化用户体验。

当前按钮布局（`list.vue` 第590-607行）：
```vue
<ElButton type="primary" @click="handleSearch">查询</ElButton>
<ElButton @click="handleReset">重置</ElButton>
<ElButton type="success" @click="handleOpenImport">批量导入</ElButton>
<ElButton type="danger" ... >批量删除...</ElButton>
<ElButton type="primary" ... >批量执行命令...</ElButton>
```

改造后：批量导入、批量删除、批量执行命令、批量启用、批量停用这5个按钮收纳到下拉菜单中，只保留查询和重置按钮在外面。

## 目标

1. 新增批量启用和批量停用功能
2. 实现按钮收纳菜单，将批量操作按钮收纳到一个下拉菜单中
3. 保持界面简洁，提升用户体验

## 设计方案

### 1. 按钮收纳菜单

#### 位置和样式
- **位置**：放在"重置"按钮右边，替换原有的3个批量按钮
- **图标**：Element Plus 的 `Grid` 图标（四个小方块），需导入：`import { Grid } from '@element-plus/icons-vue'`
- **按钮类型**：纯图标按钮（无文字）

#### 交互方式
- 点击触发：点击按钮后弹出菜单（`trigger="click"`）
- 点击菜单项后自动收起
- 再次点击按钮也收起
- 点击页面其他区域也收起（`@visible-change` 或 blur 失焦）
- 空选择校验：点击菜单项时检查 `selectedIds.size === 0`，若为空则提示"请先选择设备"

#### 菜单内容
菜单包含以下操作项（每个菜单项使用 `ElDropdownItem`）：
1. 批量导入
2. 批量删除
3. 批量执行命令
4. 批量启用（新增）
5. 批量停用（新增）

### 2. 批量启用/批量停用逻辑

#### 批量启用校验规则
启用设备前必须校验以下条件：

| 序号 | 校验项 | 校验条件 | 跳过原因 |
|------|--------|----------|----------|
| 1 | 标签字段 | `mark` 字段存在且不为空 | "缺少标签" |
| 2 | 扩展信息字段 | `extra_message` 字段存在且为有效 JSON dict | "缺少扩展信息" |
| 3 | 标签与扩展信息匹配 | 对于 `mark` 中的每个标签（逗号分隔），`extra_message[tag]` 必须存在且为 dict | "标签 '{tag}' 在扩展信息中缺少对应配置" |

校验逻辑参考现有 `_virtual_import_processor` 方法（`service.py` 第144-184行）。

#### 批量启用处理流程
1. 查询所有选中设备
2. 对每个设备执行校验
3. 校验通过的设备：设置 `available=True`，计入 `success_count`
4. 校验不通过的设备：跳过，计入 `skipped_count`，记录 `skipped_items`
5. 返回结果汇总

#### 批量停用
- 直接停用所有选中的设备，设置 `available=False`
- 无需额外校验
- 返回成功数量和失败数量

#### 确认弹窗
- **批量启用**：显示确认弹窗，内容："确定要启用选中的 X 台设备吗？（其中 Y 台可能因缺少必要信息而跳过）"
- **批量停用**：显示确认弹窗，内容："确定要停用选中的 X 台设备吗？"

### 3. 后端 API 设计

#### Schema 定义

```python
# === 请求 Schema ===

class BatchEnableRequest(BaseModel):
    ids: List[str] = Field(..., description="设备 ID 列表")

class BatchDisableRequest(BaseModel):
    ids: List[str] = Field(..., description="设备 ID 列表")

# === 响应 Schema ===

class SkippedItem(BaseModel):
    """批量启用时跳过的设备"""
    id: str
    ip: str
    reason: str  # 跳过原因

class FailedItem(BaseModel):
    """批量停用时失败的设备"""
    id: str
    ip: str

class BatchEnableResponse(BaseModel):
    """批量启用响应"""
    success_count: int
    skipped_count: int
    skipped_items: List[SkippedItem]

class BatchDisableResponse(BaseModel):
    """批量停用响应"""
    success_count: int
    failed_count: int
    failed_items: List[FailedItem]
```

#### API 接口

**批量启用**
```
POST /api/core/env/batch-enable
Request: BatchEnableRequest
Response: BatchEnableResponse
```

**批量停用**
```
POST /api/core/env/batch-disable
Request: BatchDisableRequest
Response: BatchDisableResponse
```

#### 实现方式

**批量停用**：
- 直接调用已有的 `batch_update_available(ids, available=False)` 方法
- 返回成功数量和失败数量

**批量启用**：
- 新增 `batch_enable_with_validation` 方法，包含：
  1. 查询所有设备信息
  2. 对每个设备执行校验（使用 `_virtual_import_processor` 中的校验逻辑）
  3. 校验通过的设备调用 `update_available(available=True)`
  4. 返回成功数量和跳过设备列表

### 4. 前端实现

#### 新增前端 API 方法

```typescript
interface SkippedItem {
  id: string;
  ip: string;
  reason: string;
}

interface FailedItem {
  id: string;
  ip: string;
}

interface BatchEnableResponse {
  success_count: number;
  skipped_count: number;
  skipped_items: SkippedItem[];
}

interface BatchDisableResponse {
  success_count: number;
  failed_count: number;
  failed_items: FailedItem[];
}

// 批量启用
export async function batchEnableEnvMachineApi(ids: string[]) {
  return requestClient.post<BatchEnableResponse>('/api/core/env/batch-enable', { ids });
}

// 批量停用
export async function batchDisableEnvMachineApi(ids: string[]) {
  return requestClient.post<BatchDisableResponse>('/api/core/env/batch-disable', { ids });
}
```

#### UI 组件结构

```vue
<template>
  <!-- 搜索按钮 -->
  <ElButton type="primary" @click="handleSearch">查询</ElButton>
  <ElButton @click="handleReset">重置</ElButton>
  
  <!-- 批量操作下拉菜单 -->
  <ElDropdown trigger="click" @command="handleBatchCommand">
    <ElButton :icon="Grid" />
    <template #dropdown>
      <ElDropdownMenu>
        <ElDropdownItem command="import">批量导入</ElDropdownItem>
        <ElDropdownItem command="delete">批量删除</ElDropdownItem>
        <ElDropdownItem command="execute">批量执行命令</ElDropdownItem>
        <ElDropdownItem command="enable">批量启用</ElDropdownItem>
        <ElDropdownItem command="disable">批量停用</ElDropdownItem>
      </ElDropdownMenu>
    </template>
  </ElDropdown>
</template>

<script setup>
import { Grid } from '@element-plus/icons-vue';

function handleBatchCommand(command: string) {
  if (selectedIds.value.size === 0 && command !== 'import') {
    ElMessage.warning('请先选择设备');
    return;
  }
  
  switch (command) {
    case 'import': handleOpenImport(); break;
    case 'delete': handleBatchDelete(); break;
    case 'execute': handleOpenBatchCommand(); break;
    case 'enable': handleBatchEnable(); break;
    case 'disable': handleBatchDisable(); break;
  }
}
</script>
```

### 5. 实现步骤

1. **后端 Schema**：在 `schema.py` 新增请求和响应 Schema
2. **后端 Service**：在 `service.py` 新增 `batch_enable_with_validation` 方法
3. **后端 API**：在 `api.py` 新增批量启用和批量停用接口
4. **前端 API**：在 `env-machine.ts` 新增 API 方法
5. **前端 UI**：在 `list.vue` 实现按钮收纳菜单和批量启用/停用逻辑

### 6. 文件变更清单

**后端**
- `backend-fastapi/core/env_machine/schema.py` - 新增 Schema 类
- `backend-fastapi/core/env_machine/service.py` - 新增 `batch_enable_with_validation` 方法
- `backend-fastapi/core/env_machine/api.py` - 新增批量启用/停用接口

**前端**
- `web/apps/web-ele/src/api/core/env-machine.ts` - 新增 API 方法和类型定义
- `web/apps/web-ele/src/views/env-machine/list.vue` - UI 改造：
  - 导入 Grid 图标
  - 替换批量按钮为下拉菜单
  - 新增批量启用/停用处理函数
  - 新增确认弹窗逻辑