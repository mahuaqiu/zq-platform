# 设备列表批量执行命令功能设计

## 概述

为设备列表页面新增"批量执行命令"功能，支持批量向 Worker 发送 CMD/Shell 命令，同时修复批量选择跨分页数据丢失的 Bug。

## 需求确认

### 批量执行命令功能

| 需求项 | 确认内容 |
|--------|----------|
| 命令执行方式 | 通过 Worker HTTP 接口 `/task/execute` |
| 设备类型区分 | Windows → CMD，Mac → Shell |
| 不支持设备 | iOS/Android 设备自动过滤 |
| 混合选择处理 | 只执行支持的设备类型，过滤不支持的 |
| 结果展示 | 弹窗内显示每台设备的 stdout/stderr，可滚动查看 |
| 执行方式 | 并行流控，每批最多 20 台，逐批执行 |
| 执行超时 | 单台设备 60 秒 |
| 弹窗交互 | 打开弹窗 → 输入命令 → 执行 → 结果展示 → 用户手动关闭 |
| 下次打开 | 清空上次执行结果 |
| 按钮位置 | 批量删除按钮右边，使用 Terminal 图标 |

### 批量选择 Bug 修复

| 需求项 | 确认内容 |
|--------|----------|
| 当前问题 | 第一页全选后切换分页，选择数据丢失 |
| 期望行为 | 跨页保持选择状态 |
| 解决方案 | 使用 row-key + 手动管理选中 ID Set |

## 设计详情

### 一、前端批量选择 Bug 修复

**改动位置：** `web/apps/web-ele/src/views/env-machine/list.vue`

**改动内容：**

1. 添加 `row-key="id"` 到 ElTable，确保行唯一性
2. 新增 `selectedIds` ref（Set 类型）存储选中 ID，跨页保存
3. 修改 `handleSelectionChange` 函数：更新 Set 而非直接覆盖数组
4. 分页切换时：在 `loadData` 后使用 `nextTick` 同步 checkbox 状态

```typescript
// 新增变量
const selectedIds = ref<Set<string>>(new Set());

// 选择变化时更新 Set
function handleSelectionChange(rows: EnvMachine[]) {
  // 先移除当前页不在选中列表的 ID
  const currentPageIds = tableData.value.map(r => r.id);
  for (const id of currentPageIds) {
    if (!rows.find(r => r.id === id)) {
      selectedIds.value.delete(id);
    }
  }
  // 再添加当前页选中的 ID
  for (const row of rows) {
    selectedIds.value.add(row.id);
  }
}

// 数据加载后同步选中状态
async function loadData() {
  // ... 加载逻辑
  // 同步选中状态
  nextTick(() => {
    const table = tableRef.value;
    if (table) {
      tableData.value.forEach(row => {
        if (selectedIds.value.has(row.id)) {
          table.toggleRowSelection(row, true);
        }
      });
    }
  });
}
```

### 二、批量执行命令按钮和弹窗

#### 1. 按钮新增

**位置：** 批量删除按钮右边

```vue
<ElButton
  type="primary"
  :icon="Terminal"
  :disabled="selectedIds.size === 0"
  @click="handleOpenBatchCommand"
>
  批量执行命令{{ selectedIds.size > 0 ? ` (${selectedIds.size})` : '' }}
</ElButton>
```

#### 2. 命令执行弹窗组件

**新增文件：** `web/apps/web-ele/src/views/env-machine/modules/BatchCommandDialog.vue`

**弹窗结构：**

```
┌─────────────────────────────────────────────────────────────┐
│ 批量执行命令                                            [X] │
├─────────────────────────────────────────────────────────────┤
│ 已选中 15 台设备（Windows: 10, Mac: 5）                      │
│ 注意：iOS/Android 设备不支持命令执行，已自动过滤              │
├─────────────────────────────────────────────────────────────┤
│ 命令内容：                                                   │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [输入框 - 多行文本，支持滚动]                            │ │
│ │ placeholder: "Windows 输入 CMD 命令，Mac 输入 Shell 命令"│ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                                          [执行命令] [取消]   │
├─────────────────────────────────────────────────────────────┤
│ 执行结果：                                                   │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │ 10.173.94.49 (Windows)          ✓ 成功   耗时 2.3s  │ │ │
│ │ │ stdout: tasklist /fi "imagename eq chrome.exe"      │ │ │
│ │ │ chrome.exe    1234 Console    1    50,000 K        │ │ │
│ │ │ stderr: (无)                                        │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │ 10.173.94.50 (Mac)              ✗ 失败   耗时 1.5s  │ │ │
│ │ │ stdout: (无)                                        │ │ │
│ │ │ stderr: Connection refused                         │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ │ ... (可滚动查看更多)                                  │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**组件 Props：**
- `visible: boolean` - 弹窗可见性
- `selectedMachines: EnvMachine[]` - 选中的设备列表（从父组件传入完整数据）

**组件内部状态：**
- `command: string` - 输入的命令
- `executing: boolean` - 执行状态
- `results: CommandResultItem[]` - 执行结果列表
- `currentBatch: number` - 当前批次（用于进度显示）

**组件事件：**
- `update:visible` - 关闭弹窗时触发

### 三、后端 API 设计

#### 1. 新增批量执行命令 API

**文件位置：** `backend-fastapi/core/env_machine/api.py`

**API 定义：**

```python
@router.post("/batch-execute-command", summary="批量执行命令")
async def batch_execute_command(
    data: EnvMachineBatchCommandRequest,
    db: AsyncSession = Depends(get_db)
) -> EnvMachineBatchCommandResponse:
    """
    批量执行命令
    
    - 支持设备类型：Windows (CMD), Mac (Shell)
    - iOS/Android 设备不支持，返回错误
    - 单台设备超时 60 秒
    """
```

#### 2. 新增 Schema 定义

**文件位置：** `backend-fastapi/core/env_machine/schema.py`

```python
class EnvMachineBatchCommandRequest(BaseModel):
    """批量执行命令请求"""
    ids: List[str]  # 设备 ID 列表
    command: str    # 命令内容

class CommandResultItem(BaseModel):
    """单台设备执行结果"""
    id: str                # 设备 ID
    ip: str                 # 设备 IP
    device_type: str        # 设备类型
    device_name: str        # 设备名称（asset_number 或 ip）
    success: bool           # 执行状态
    stdout: str = ""        # 标准输出
    stderr: str = ""        # 错误输出
    duration_seconds: float # 执行耗时（秒）

class EnvMachineBatchCommandResponse(BaseModel):
    """批量执行命令响应"""
    results: List[CommandResultItem]
    total: int      # 总设备数
    success_count: int  # 成功数
    failed_count: int   # 失败数
```

#### 3. 执行逻辑

**流程：**

1. 根据 ID 列表查询设备信息
2. 校验设备类型（过滤 iOS/Android）
3. 遍历设备，构造 Worker 请求：
   - Windows: `{ "action_type": "cmd", "command": "..." }`
   - Mac: `{ "action_type": "shell", "command": "..." }`
4. POST 到 `http://{ip}:{port}/task/execute`
5. 超时设置 60 秒
6. 收集结果返回

**Worker 请求体构造：**

```python
# Windows CMD 命令
actions = [{"action_type": "cmd", "command": data.command}]

# Mac Shell 命令
actions = [{"action_type": "shell", "command": data.command}]

worker_request = {
    "platform": machine.device_type,
    "device_id": machine.device_sn or machine.id,
    "actions": actions
}
```

### 四、前端 API 接口和执行逻辑

#### 1. 前端 API 接口定义

**文件位置：** `web/apps/web-ele/src/api/core/env-machine.ts`

```typescript
/**
 * 批量执行命令请求
 */
export interface BatchCommandRequest {
  ids: string[];
  command: string;
}

/**
 * 单台设备执行结果
 */
export interface CommandResultItem {
  id: string;
  ip: string;
  device_type: string;
  device_name: string;
  success: boolean;
  stdout: string;
  stderr: string;
  duration_seconds: number;
}

/**
 * 批量执行命令响应
 */
export interface BatchCommandResponse {
  results: CommandResultItem[];
  total: number;
  success_count: number;
  failed_count: number;
}

/**
 * 批量执行命令
 */
export async function batchExecuteCommandApi(data: BatchCommandRequest) {
  return requestClient.post<BatchCommandResponse>(
    '/api/core/env/batch-execute-command',
    data,
    { timeout: 120000 }  // 整体超时 2 分钟（支持多批次）
  );
}
```

#### 2. 弹窗内分批执行逻辑

**组件内部实现：**

```typescript
// 执行命令
async function handleExecute() {
  if (!command.value.trim()) {
    ElMessage.warning('请输入命令内容');
    return;
  }

  executing.value = true;
  results.value = [];  // 清空上次结果

  // 获取选中设备列表（从 props 传入）
  const machines = props.selectedMachines;
  
  // 过滤支持的设备类型
  const supportedMachines = machines.filter(
    m => m.device_type === 'windows' || m.device_type === 'mac'
  );

  if (supportedMachines.length === 0) {
    ElMessage.warning('选中的设备不支持命令执行');
    executing.value = false;
    return;
  }

  // 分批执行（每批 20 台）
  const batchSize = 20;
  const batches = [];
  for (let i = 0; i < supportedMachines.length; i += batchSize) {
    batches.push(supportedMachines.slice(i, i + batchSize));
  }

  // 逐批执行
  for (let i = 0; i < batches.length; i++) {
    currentBatch.value = i + 1;
    const batchIds = batches[i].map(m => m.id);

    try {
      const res = await batchExecuteCommandApi({
        ids: batchIds,
        command: command.value.trim(),
      });
      // 追加结果
      results.value.push(...res.results);
    } catch (error) {
      // 批次失败，标记所有设备为失败
      for (const machine of batches[i]) {
        results.value.push({
          id: machine.id,
          ip: machine.ip || '',
          device_type: machine.device_type,
          device_name: machine.asset_number || machine.ip || machine.id,
          success: false,
          stdout: '',
          stderr: '请求失败',
          duration_seconds: 0,
        });
      }
    }
  }

  executing.value = false;
}
```

## 文件改动清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `web/apps/web-ele/src/views/env-machine/list.vue` | 修改 | 批量选择修复 + 新增按钮 + 引入弹窗 |
| `web/apps/web-ele/src/views/env-machine/modules/BatchCommandDialog.vue` | 新增 | 命令执行弹窗组件 |
| `web/apps/web-ele/src/api/core/env-machine.ts` | 修改 | 新增批量执行命令 API 接口 |
| `backend-fastapi/core/env_machine/api.py` | 修改 | 新增批量执行命令 API 路由 |
| `backend-fastapi/core/env_machine/schema.py` | 修改 | 新增请求/响应 Schema |
| `backend-fastapi/core/env_machine/__init__.py` | 可能修改 | 导出新 Schema |

## 测试要点

### 功能测试

1. **批量选择跨页保持**
   - 第一页选中几条 → 切换第二页选中几条 → 返回第一页验证选中状态
   - 第一页全选 → 切换第二页 → 返回第一页验证全选状态
   - 跨页选择后执行批量操作验证 ID 正确

2. **批量执行命令**
   - 单选 Windows 设备执行 CMD 命令
   - 单选 Mac 设备执行 Shell 命令
   - 多选混合设备类型（验证自动过滤）
   - 选中 iOS/Android 设备（验证提示和过滤）
   - 超过 20 台设备（验证分批执行）
   - 命令执行成功/失败的展示
   - 弹窗关闭后再次打开（验证结果清空）

### 边界测试

1. 空命令输入验证
2. 设备离线时的错误处理
3. Worker 超时处理（60秒）
4. 网络异常处理
5. 批次请求失败时的容错处理

## 注意事项

1. Worker 端需要确认是否已支持 `cmd` 和 `shell` action_type，若无需要先实现
2. 命令执行存在安全风险，建议后续增加命令白名单或权限控制
3. 虚拟设备（is_virtual=true）不支持命令执行，应在过滤逻辑中排除