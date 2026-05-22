# 批量操作按钮收纳菜单实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为设备列表页面添加批量启用/批量停用功能，并实现按钮收纳菜单优化界面。

**Architecture:** 后端新增批量启用/停用 API（含校验逻辑），前端使用 ElDropdown 组件收纳批量操作按钮。

**Tech Stack:** FastAPI + Pydantic (后端), Vue 3 + Element Plus (前端)

---

## 文件结构

| 文件 | 负责内容 |
|------|----------|
| `backend-fastapi/core/env_machine/schema.py` | 新增批量启用/停用请求和响应 Schema |
| `backend-fastapi/core/env_machine/service.py` | 新增 `batch_enable_with_validation` 方法 |
| `backend-fastapi/core/env_machine/api.py` | 新增批量启用/停用 API 接口 |
| `web/apps/web-ele/src/api/core/env-machine.ts` | 新增前端 API 方法和类型定义 |
| `web/apps/web-ele/src/views/env-machine/list.vue` | UI 改造：按钮收纳菜单、批量启用/停用逻辑 |

---

### Task 1: 后端 Schema - 新增请求和响应 Schema

**Files:**
- Modify: `backend-fastapi/core/env_machine/schema.py`

- [ ] **Step 1: 在 schema.py 文件末尾添加批量启用/停用 Schema**

在 `EnvMachineBatchCommandResponse` 类之后添加：

```python
class BatchEnableRequest(BaseModel):
    """批量启用请求 Schema"""
    ids: List[str] = Field(..., description="设备 ID 列表")


class BatchDisableRequest(BaseModel):
    """批量停用请求 Schema"""
    ids: List[str] = Field(..., description="设备 ID 列表")


class SkippedItem(BaseModel):
    """批量启用时跳过的设备"""
    id: str = Field(..., description="设备 ID")
    ip: str = Field(default="", description="设备 IP")
    reason: str = Field(..., description="跳过原因")


class FailedItem(BaseModel):
    """批量停用时失败的设备"""
    id: str = Field(..., description="设备 ID")
    ip: str = Field(default="", description="设备 IP")


class BatchEnableResponse(BaseModel):
    """批量启用响应 Schema"""
    success_count: int = Field(..., description="成功启用数量")
    skipped_count: int = Field(default=0, description="跳过数量")
    skipped_items: List[SkippedItem] = Field(default_factory=list, description="跳过设备列表")


class BatchDisableResponse(BaseModel):
    """批量停用响应 Schema"""
    success_count: int = Field(..., description="成功停用数量")
    failed_count: int = Field(default=0, description="失败数量")
    failed_items: List[FailedItem] = Field(default_factory=list, description="失败设备列表")
```

- [ ] **Step 2: 提交 Schema 变更**

```bash
git add backend-fastapi/core/env_machine/schema.py
git commit -m "feat(env_machine): 新增批量启用/停用 Schema 定义"
```

---

### Task 2: 后端 Service - 新增批量启用校验方法

**Files:**
- Modify: `backend-fastapi/core/env_machine/service.py`

- [ ] **Step 1: 在 service.py 文件末尾添加 batch_enable_with_validation 方法**

在 `generate_virtual_import_template` 方法之后添加：

```python
    @classmethod
    async def batch_enable_with_validation(
        cls,
        db: AsyncSession,
        ids: List[str]
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        批量启用设备（带校验）

        校验规则：
        1. mark 字段必须存在且不为空
        2. extra_message 字段必须存在且为有效 dict
        3. 对于 mark 中的每个标签，extra_message[tag] 必须存在且为 dict

        Args:
            db: 数据库会话
            ids: 设备 ID 列表

        Returns:
            (success_count, skipped_items)
        """
        success_count = 0
        skipped_items = []

        machines = await cls.get_by_ids(db, ids)

        for machine in machines:
            # 校验 1: 标签字段
            mark = machine.mark
            if not mark or not mark.strip():
                skipped_items.append({
                    "id": str(machine.id),
                    "ip": machine.ip or "",
                    "reason": "缺少标签"
                })
                continue

            # 校验 2: 扩展信息字段
            extra_message = machine.extra_message
            if not extra_message or not isinstance(extra_message, dict):
                skipped_items.append({
                    "id": str(machine.id),
                    "ip": machine.ip or "",
                    "reason": "缺少扩展信息"
                })
                continue

            # 校验 3: 标签与扩展信息匹配
            mark_str = str(mark).strip()
            tags = [t.strip() for t in mark_str.split(',') if t.strip()]
            validation_failed = False
            for tag in tags:
                if not extra_message.get(tag):
                    skipped_items.append({
                        "id": str(machine.id),
                        "ip": machine.ip or "",
                        "reason": f"标签 '{tag}' 在扩展信息中缺少对应配置"
                    })
                    validation_failed = True
                    break
                if not isinstance(extra_message.get(tag), dict):
                    skipped_items.append({
                        "id": str(machine.id),
                        "ip": machine.ip or "",
                        "reason": f"标签 '{tag}' 的配置必须是对象格式"
                    })
                    validation_failed = True
                    break

            if validation_failed:
                continue

            # 校验通过，启用设备
            machine.available = True
            success_count += 1

        if success_count > 0:
            await db.commit()

        return success_count, skipped_items
```

- [ ] **Step 2: 提交 Service 变更**

```bash
git add backend-fastapi/core/env_machine/service.py
git commit -m "feat(env_machine): 新增 batch_enable_with_validation 方法"
```

---

### Task 3: 后端 API - 新增批量启用/停用接口

**Files:**
- Modify: `backend-fastapi/core/env_machine/api.py`

- [ ] **Step 1: 在 api.py 导入部分添加新 Schema 导入**

在现有 `from core.env_machine.schema import (...)` 语句中添加新类：

```python
from core.env_machine.schema import (
    EnvRegisterRequest,
    EnvMachineIdItem,
    EnvSuccessResponse,
    EnvFailResponse,
    EnvMachineListRequest,
    EnvMachineCreateRequest,
    EnvMachineUpdateRequest,
    EnvMachineResponse,
    DebugActionRequest,
    DebugActionResponse,
    EnvMachineBatchDeleteRequest,
    EnvMachineBatchImportResponse,
    EnvMachineBatchCommandRequest,
    CommandResultItem,
    EnvMachineBatchCommandResponse,
    BatchEnableRequest,        # 新增
    BatchEnableResponse,       # 新增
    BatchDisableRequest,       # 新增
    BatchDisableResponse,      # 新增
    SkippedItem,               # 新增
    FailedItem,                # 新增
)
```

- [ ] **Step 2: 在 api.py 文件末尾（batch-import-virtual 之后）添加批量启用接口**

```python
@router.post("/batch-enable", response_model=BatchEnableResponse, summary="批量启用设备")
async def batch_enable_env_machines(
    data: BatchEnableRequest,
    db: AsyncSession = Depends(get_db)
) -> BatchEnableResponse:
    """
    批量启用设备（带校验）

    校验规则：
    - 标签字段必须存在
    - 扩展信息字段必须存在且为有效 dict
    - 每个标签在扩展信息中必须有对应配置

    不满足条件的设备会被跳过，返回跳过原因。
    """
    success_count, skipped_items = await EnvMachineService.batch_enable_with_validation(
        db, data.ids
    )

    return BatchEnableResponse(
        success_count=success_count,
        skipped_count=len(skipped_items),
        skipped_items=[SkippedItem(**item) for item in skipped_items]
    )
```

- [ ] **Step 3: 在批量启用接口之后添加批量停用接口**

使用现有的 `batch_update_available` 方法实现：

```python
@router.post("/batch-disable", response_model=BatchDisableResponse, summary="批量停用设备")
async def batch_disable_env_machines(
    data: BatchDisableRequest,
    db: AsyncSession = Depends(get_db)
) -> BatchDisableResponse:
    """
    批量停用设备

    直接停用所有选中的设备，无需校验。
    """
    # 使用现有方法批量更新
    success_count, failed_ids = await EnvMachineService.batch_update_available(
        db, data.ids, available=False
    )

    # 同步 Redis 缓存
    machines = await EnvMachineService.get_by_ids(db, data.ids)
    for machine in machines:
        await EnvPoolManager.sync_machine_to_cache(machine)

    # 构建失败项详情
    failed_items = []
    if failed_ids:
        for fid in failed_ids:
            failed_items.append(FailedItem(id=fid, ip=""))

    return BatchDisableResponse(
        success_count=success_count,
        failed_count=len(failed_ids),
        failed_items=failed_items
    )
```

- [ ] **Step 4: 提交 API 变更**

```bash
git add backend-fastapi/core/env_machine/api.py
git commit -m "feat(env_machine): 新增批量启用/停用 API 接口"
```

---

### Task 4: 前端 API - 新增 API 方法和类型定义

**Files:**
- Modify: `web/apps/web-ele/src/api/core/env-machine.ts`

- [ ] **Step 1: 在 env-machine.ts 文件末尾添加类型定义和 API 方法**

在 `batchExecuteCommandApi` 函数之后添加：

```typescript
/**
 * 批量启用时跳过的设备
 */
export interface SkippedItem {
  id: string;
  ip: string;
  reason: string;
}

/**
 * 批量停用时失败的设备
 */
export interface FailedItem {
  id: string;
  ip: string;
}

/**
 * 批量启用响应
 */
export interface BatchEnableResponse {
  success_count: number;
  skipped_count: number;
  skipped_items: SkippedItem[];
}

/**
 * 批量停用响应
 */
export interface BatchDisableResponse {
  success_count: number;
  failed_count: number;
  failed_items: FailedItem[];
}

/**
 * 批量启用设备
 */
export async function batchEnableEnvMachineApi(ids: string[]) {
  return requestClient.post<BatchEnableResponse>('/api/core/env/batch-enable', { ids });
}

/**
 * 批量停用设备
 */
export async function batchDisableEnvMachineApi(ids: string[]) {
  return requestClient.post<BatchDisableResponse>('/api/core/env/batch-disable', { ids });
}
```

- [ ] **Step 2: 提交前端 API 变更**

```bash
git add web/apps/web-ele/src/api/core/env-machine.ts
git commit -m "feat(env-machine): 新增批量启用/停用 API 方法"
```

---

### Task 5: 前端 UI - 实现按钮收纳菜单和批量启用/停用逻辑

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/list.vue`

- [ ] **Step 1: 在 import 部分添加 Grid 图标和 ElDropdown 组件**

修改组件导入部分：

```typescript
import {
  ElButton,
  ElDialog,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElPagination,
  ElSelect,
  ElTable,
  ElTableColumn,
} from 'element-plus';

import { Grid } from '@element-plus/icons-vue';
```

- [ ] **Step 2: 在 API 导入部分添加新方法导入**

修改 API 导入部分：

```typescript
import {
  deleteEnvMachineApi,
  getEnvMachineListApi,
  updateEnvMachineApi,
  batchDeleteEnvMachineApi,
  batchImportVirtualDevicesApi,
  downloadImportTemplateApi,
  batchEnableEnvMachineApi,
  batchDisableEnvMachineApi,
} from '#/api/core/env-machine';
```

- [ ] **Step 3: 添加批量启用/停用处理函数**

在 `handleOpenBatchCommand` 函数之后添加：

```typescript
// 批量启用
async function handleBatchEnable() {
  const count = selectedIds.value.size;
  if (count === 0) {
    ElMessage.warning('请先选择要启用的设备');
    return;
  }

  // 获取所有选中设备的信息，预估跳过数量
  const machines = getSelectedMachines();
  let estimatedSkip = 0;
  machines.forEach((m) => {
    if (!m.mark || !m.extra_message) {
      estimatedSkip++;
    }
  });

  const confirmMsg = estimatedSkip > 0
    ? `确定要启用选中的 ${count} 台设备吗？（其中 ${estimatedSkip} 台可能因缺少必要信息而跳过）`
    : `确定要启用选中的 ${count} 台设备吗？`;

  ElMessageBox.confirm(confirmMsg, '批量启用确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'info',
  }).then(async () => {
    try {
      const ids = Array.from(selectedIds.value);
      const res = await batchEnableEnvMachineApi(ids);
      if (res.success_count > 0) {
        ElMessage.success(`成功启用 ${res.success_count} 台设备`);
      }
      if (res.skipped_count > 0) {
        const details = res.skipped_items.map((item) => `${item.ip}: ${item.reason}`).join('\n');
        ElMessageBox.alert(`${res.skipped_count} 台设备因不符合条件而跳过：\n\n${details}`, '部分设备跳过', {
          confirmButtonText: '确定',
          type: 'warning',
        });
      }
      loadData();
    } catch {
      ElMessage.error('批量启用失败');
    }
  });
}

// 批量停用
async function handleBatchDisable() {
  const count = selectedIds.value.size;
  if (count === 0) {
    ElMessage.warning('请先选择要停用的设备');
    return;
  }

  ElMessageBox.confirm(`确定要停用选中的 ${count} 台设备吗？`, '批量停用确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      const ids = Array.from(selectedIds.value);
      const res = await batchDisableEnvMachineApi(ids);
      if (res.success_count > 0) {
        ElMessage.success(`成功停用 ${res.success_count} 台设备`);
      }
      if (res.failed_count > 0) {
        ElMessage.warning(`${res.failed_count} 台设备停用失败`);
      }
      loadData();
    } catch {
      ElMessage.error('批量停用失败');
    }
  });
}

// 批量操作菜单命令处理
function handleBatchCommand(command: string) {
  switch (command) {
    case 'import':
      handleOpenImport();
      break;
    case 'delete':
      handleBatchDelete();
      break;
    case 'execute':
      handleOpenBatchCommand();
      break;
    case 'enable':
      handleBatchEnable();
      break;
    case 'disable':
      handleBatchDisable();
      break;
  }
}
```

- [ ] **Step 4: 替换按钮区域的模板代码**

将搜索按钮区域的批量按钮替换为下拉菜单：

```vue
<div class="env-search-buttons">
  <ElButton type="primary" @click="handleSearch">查询</ElButton>
  <ElButton @click="handleReset">重置</ElButton>
  <ElDropdown trigger="click" @command="handleBatchCommand">
    <ElButton :icon="Grid" />
    <template #dropdown>
      <ElDropdownMenu>
        <ElDropdownItem command="import">批量导入</ElDropdownItem>
        <ElDropdownItem command="delete" :disabled="selectedIds.size === 0">
          批量删除{{ selectedIds.size > 0 ? ` (${selectedIds.size})` : '' }}
        </ElDropdownItem>
        <ElDropdownItem command="execute" :disabled="selectedIds.size === 0">
          批量执行命令{{ selectedIds.size > 0 ? ` (${selectedIds.size})` : '' }}
        </ElDropdownItem>
        <ElDropdownItem command="enable" :disabled="selectedIds.size === 0">
          批量启用{{ selectedIds.size > 0 ? ` (${selectedIds.size})` : '' }}
        </ElDropdownItem>
        <ElDropdownItem command="disable" :disabled="selectedIds.size === 0">
          批量停用{{ selectedIds.size > 0 ? ` (${selectedIds.size})` : '' }}
        </ElDropdownItem>
      </ElDropdownMenu>
    </template>
  </ElDropdown>
</div>
```

- [ ] **Step 5: 提交前端 UI 变更**

```bash
git add web/apps/web-ele/src/views/env-machine/list.vue
git commit -m "feat(env-machine): 实现批量操作按钮收纳菜单"
```

---

### Task 6: 验证功能

- [ ] **Step 1: 启动后端服务**

```bash
cd backend-fastapi
# Windows: conda activate zq-fastapi 或直接运行
python main.py
```

预期：服务在 http://localhost:8000 启动，Swagger UI 可访问

- [ ] **Step 2: 启动前端开发服务器**

```bash
cd web
pnpm dev
```

预期：前端在 http://localhost:5555 启动

- [ ] **Step 3: 测试批量启用功能**

测试步骤：
1. 打开设备列表页面
2. 选择 3 台设备（假设 1 台有完整信息，2 台缺少标签）
3. 点击批量操作菜单图标，选择"批量启用"

预期结果：
- 弹窗显示："确定要启用选中的 3 台设备吗？（其中 2 台可能因缺少必要信息而跳过）"
- 点击确定后，提示"成功启用 1 台设备"
- 弹窗显示跳过详情："xxx IP: 缺少标签"

- [ ] **Step 4: 测试批量停用功能**

测试步骤：
1. 选择 2 台已启用的设备
2. 点击批量操作菜单图标，选择"批量停用"

预期结果：
- 弹窗显示："确定要停用选中的 2 台设备吗？"
- 点击确定后，提示"成功停用 2 台设备"
- 设备列表刷新，设备状态变为"未启用"

- [ ] **Step 5: 测试空选择校验**

测试步骤：
1. 不选择任何设备
2. 点击批量操作菜单，观察菜单项状态

预期结果：
- "批量导入"菜单项可用
- 其他菜单项显示禁用状态
- 点击禁用的菜单项无响应

- [ ] **Step 6: 最终确认**

```bash
git status
git log --oneline -5
```

预期：所有变更已提交，共 5 个 commit

---

## 预期结果

完成后：
1. 设备列表页面搜索区域只显示"查询"、"重置"和一个四方块图标按钮
2. 点击图标按钮弹出下拉菜单，包含5个批量操作选项
3. 批量启用功能会校验设备条件，跳过不符合的设备并显示原因
4. 批量停用功能直接停用所有选中设备
5. 菜单项在未选择设备时显示禁用状态