---
name: batch-operations-menu
description: 设备列表页面批量操作按钮收纳菜单设计
---

# 设备列表页面批量操作按钮收纳菜单设计

## 背景

设备列表页面当前有多个批量操作按钮（批量导入、批量删除、批量执行命令），用户需要新增批量启用和批量停用按钮。但按钮数量过多会导致界面拥挤，需要引入按钮收纳功能来优化用户体验。

## 目标

1. 新增批量启用和批量停用功能
2. 实现按钮收纳菜单，将批量操作按钮收纳到一个下拉菜单中
3. 保持界面简洁，提升用户体验

## 设计方案

### 1. 按钮收纳菜单

#### 位置和样式
- **位置**：放在"重置"按钮右边
- **图标**：Element Plus 的 `Grid` 图标（四个小方块）
- **按钮类型**：纯图标按钮（无文字）

#### 交互方式
- 点击触发：点击按钮后弹出菜单
- 点击菜单项后自动收起
- 再次点击按钮也收起
- 点击页面其他区域也收起（blur 失焦）

#### 菜单内容
菜单包含以下操作项：
1. 批量导入
2. 批量删除
3. 批量执行命令
4. 批量启用（新增）
5. 批量停用（新增）

### 2. 批量启用/批量停用逻辑

#### 批量启用
- 检查每个设备的启用条件：
  - 是否有标签（mark 字段）
  - 是否有扩展信息（extra_message 字段）
  - 扩展信息是否包含标签对应的配置
- 不具备启用条件的设备跳过，不执行启用
- 返回成功数量和跳过数量及原因

#### 批量停用
- 直接停用所有选中的设备
- 无需额外校验

### 3. 后端 API 设计

#### 新增接口

**批量启用**
```
POST /api/core/env/batch-enable
Request: { ids: string[] }
Response: {
  success_count: number,
  skipped_count: number,
  skipped_items: Array<{ id: string, ip: string, reason: string }>
}
```

**批量停用**
```
POST /api/core/env/batch-disable
Request: { ids: string[] }
Response: {
  success_count: number,
  failed_count: number,
  failed_ids: string[]
}
```

#### 实现方式
- 利用已有的 `EnvMachineService.batch_update_available` 方法
- 批量启用时增加校验逻辑（检查标签和扩展信息）

### 4. 前端实现

#### 新增前端 API 方法
```typescript
// 批量启用
batchEnableEnvMachineApi(ids: string[]): Promise<BatchEnableResponse>

// 批量停用
batchDisableEnvMachineApi(ids: string[]): Promise<BatchDisableResponse>
```

#### UI 组件
使用 Element Plus 的 `ElDropdown` 组件实现按钮收纳菜单：
- `trigger="click"` 点击触发
- 配合 `@command` 处理菜单项点击
- 使用 `Grid` 图标作为触发按钮

### 5. 实现步骤

1. 后端：新增批量启用和批量停用 API
2. 前端 API：新增调用接口的方法
3. 前端 UI：
   - 创建按钮收纳菜单组件
   - 将现有批量按钮移入菜单
   - 新增批量启用和批量停用菜单项
   - 实现批量启用/停用的业务逻辑

### 6. 文件变更清单

**后端**
- `backend-fastapi/core/env_machine/api.py` - 新增批量启用/停用接口
- `backend-fastapi/core/env_machine/schema.py` - 新增请求/响应 Schema
- `backend-fastapi/core/env_machine/service.py` - 新增批量启用校验逻辑

**前端**
- `web/apps/web-ele/src/api/core/env-machine.ts` - 新增 API 方法
- `web/apps/web-ele/src/views/env-machine/list.vue` - UI 改造