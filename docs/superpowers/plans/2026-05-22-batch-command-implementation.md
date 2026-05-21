# 设备列表批量执行命令功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为设备列表页面新增批量执行命令功能，并修复批量选择跨分页数据丢失 Bug

**Architecture:** 前端使用 Vue 3 + Element Plus，通过 Set 跨页保存选中 ID；后端新增批量执行命令 API，使用 asyncio.gather 并行请求 Worker

**Tech Stack:** Vue 3, Element Plus, TypeScript, FastAPI, SQLAlchemy, httpx, asyncio

---

## 文件结构

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `backend-fastapi/core/env_machine/schema.py` | 修改 | 新增批量执行命令请求/响应 Schema |
| `backend-fastapi/core/env_machine/service.py` | 修改 | 新增 get_by_ids 方法 |
| `backend-fastapi/core/env_machine/api.py` | 修改 | 新增批量执行命令 API 路由 |
| `web/apps/web-ele/src/api/core/env-machine.ts` | 修改 | 新增批量执行命令 API 接口 |
| `web/apps/web-ele/src/views/env-machine/modules/BatchCommandDialog.vue` | 新增 | 命令执行弹窗组件 |
| `web/apps/web-ele/src/views/env-machine/list.vue` | 修改 | 批量选择修复 + 新增按钮 + 引入弹窗 |

---

## Task 1: 后端 Schema 定义

**Files:**
- Modify: `backend-fastapi/core/env_machine/schema.py` (末尾追加)

- [ ] **Step 1: 新增批量执行命令 Schema**

在 `schema.py` 文件末尾追加以下代码：

```python
class EnvMachineBatchCommandRequest(BaseModel):
    """批量执行命令请求 Schema"""
    ids: List[str] = Field(..., description="设备 ID 列表")
    command: str = Field(..., description="命令内容")


class CommandResultItem(BaseModel):
    """单台设备执行结果 Schema"""
    id: str = Field(..., description="设备 ID")
    ip: str = Field(default="", description="设备 IP")
    device_type: str = Field(..., description="设备类型")
    device_name: str = Field(..., description="设备名称（asset_number 或 ip）")
    success: bool = Field(..., description="执行状态")
    stdout: str = Field(default="", description="标准输出")
    stderr: str = Field(default="", description="错误输出")
    duration_seconds: float = Field(default=0.0, description="执行耗时（秒）")


class EnvMachineBatchCommandResponse(BaseModel):
    """批量执行命令响应 Schema"""
    results: List[CommandResultItem] = Field(default_factory=list, description="执行结果列表")
    total: int = Field(..., description="总设备数")
    success_count: int = Field(default=0, description="成功数")
    failed_count: int = Field(default=0, description="失败数")
```

- [ ] **Step 2: 验证语法正确**

运行: `python -c "from core.env_machine.schema import EnvMachineBatchCommandRequest, CommandResultItem, EnvMachineBatchCommandResponse; print('Schema OK')"`

Expected: 输出 `Schema OK`

- [ ] **Step 3: 提交**

```bash
git add backend-fastapi/core/env_machine/schema.py
git commit -m "feat(env_machine): 新增批量执行命令 Schema 定义"
```

---

## Task 2: 后端 Service 新增 get_by_ids 方法

**Files:**
- Modify: `backend-fastapi/core/env_machine/service.py`

- [ ] **Step 1: 新增 get_by_ids 方法**

在 `EnvMachineService` 类中新增 `get_by_ids` 方法（位于现有 `get_by_id` 方法附近）：

```python
async def get_by_ids(cls, db: AsyncSession, ids: List[str]) -> List[EnvMachine]:
    """
    根据 ID 列表批量获取设备

    Args:
        db: 数据库会话
        ids: 设备 ID 列表

    Returns:
        设备列表
    """
    if not ids:
        return []
    stmt = select(cls.model).where(
        cls.model.id.in_(ids),
        cls.model.is_deleted == False
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
```

注意：由于 `EnvMachineService` 继承自 `BaseService`，该方法需要添加 `@classmethod` 装饰器（如果其他方法有）或者作为实例方法。查看现有代码确认方法类型。

- [ ] **Step 2: 验证语法正确**

运行: `python -c "from core.env_machine.service import EnvMachineService; print('Service OK')"`

Expected: 输出 `Service OK`

- [ ] **Step 3: 提交**

```bash
git add backend-fastapi/core/env_machine/service.py
git commit -m "feat(env_machine): 新增 get_by_ids 批量查询方法"
```

---

## Task 3: 后端批量执行命令 API

**Files:**
- Modify: `backend-fastapi/core/env_machine/api.py` (在 batch-delete 路由之前插入)

- [ ] **Step 1: 导入新 Schema**

在 `api.py` 文件顶部的导入区域，添加新 Schema 的导入：

```python
from core.env_machine.schema import (
    # ... 现有导入 ...
    EnvMachineBatchCommandRequest,
    CommandResultItem,
    EnvMachineBatchCommandResponse,
)
```

- [ ] **Step 2: 新增批量执行命令 API 路由**

在 `debug_device_action` 路由函数结束后、`batch_delete_env_machines` 路由函数定义之前（约第 874 行），插入以下代码：

```python
import time
import asyncio


async def _execute_single_machine(machine: EnvMachine, command: str) -> CommandResultItem:
    """
    执行单台设备命令

    Args:
        machine: 设备对象
        command: 命令内容

    Returns:
        执行结果
    """
    start_time = time.time()
    device_name = machine.asset_number or machine.ip or str(machine.id)

    # 构造 Worker 请求
    action_type = "cmd" if machine.device_type == "windows" else "shell"
    worker_request = {
        "platform": machine.device_type,
        "device_id": machine.device_sn or str(machine.id),
        "actions": [{"action_type": action_type, "command": command}]
    }

    try:
        async with httpx.AsyncClient(timeout=60.0, trust_env=False, verify=False) as client:
            resp = await client.post(
                f"http://{machine.ip}:{machine.port}/task/execute",
                json=worker_request
            )

            duration_seconds = time.time() - start_time

            if resp.status_code == 200:
                worker_result = resp.json()

                # 检查顶层状态
                if worker_result.get("status") == "failed":
                    return CommandResultItem(
                        id=str(machine.id),
                        ip=machine.ip or "",
                        device_type=machine.device_type,
                        device_name=device_name,
                        success=False,
                        stdout="",
                        stderr=worker_result.get("error", "执行失败"),
                        duration_seconds=duration_seconds
                    )

                # 提取 action 结果
                actions_result = worker_result.get("actions", [])
                if actions_result:
                    first_action = actions_result[0]
                    if first_action.get("status") == "failed":
                        return CommandResultItem(
                            id=str(machine.id),
                            ip=machine.ip or "",
                            device_type=machine.device_type,
                            device_name=device_name,
                            success=False,
                            stdout=first_action.get("stdout", ""),
                            stderr=first_action.get("stderr", "") or first_action.get("error", "操作执行失败"),
                            duration_seconds=duration_seconds
                        )

                    return CommandResultItem(
                        id=str(machine.id),
                        ip=machine.ip or "",
                        device_type=machine.device_type,
                        device_name=device_name,
                        success=True,
                        stdout=first_action.get("stdout", ""),
                        stderr=first_action.get("stderr", ""),
                        duration_seconds=duration_seconds
                    )

                return CommandResultItem(
                    id=str(machine.id),
                    ip=machine.ip or "",
                    device_type=machine.device_type,
                    device_name=device_name,
                    success=True,
                    stdout="",
                    stderr="",
                    duration_seconds=duration_seconds
                )
            else:
                return CommandResultItem(
                    id=str(machine.id),
                    ip=machine.ip or "",
                    device_type=machine.device_type,
                    device_name=device_name,
                    success=False,
                    stdout="",
                    stderr=f"Worker 返回异常: {resp.status_code}",
                    duration_seconds=time.time() - start_time
                )
    except httpx.TimeoutException:
        return CommandResultItem(
            id=str(machine.id),
            ip=machine.ip or "",
            device_type=machine.device_type,
            device_name=device_name,
            success=False,
            stdout="",
            stderr="执行超时（60秒）",
            duration_seconds=60.0
        )
    except httpx.ConnectError:
        return CommandResultItem(
            id=str(machine.id),
            ip=machine.ip or "",
            device_type=machine.device_type,
            device_name=device_name,
            success=False,
            stdout="",
            stderr="无法连接到设备",
            duration_seconds=time.time() - start_time
        )
    except Exception as e:
        logger.error(f"执行命令失败: {e}")
        return CommandResultItem(
            id=str(machine.id),
            ip=machine.ip or "",
            device_type=machine.device_type,
            device_name=device_name,
            success=False,
            stdout="",
            stderr=str(e),
            duration_seconds=time.time() - start_time
        )


@router.post("/batch-execute-command", response_model=EnvMachineBatchCommandResponse, summary="批量执行命令")
async def batch_execute_command(
    data: EnvMachineBatchCommandRequest,
    db: AsyncSession = Depends(get_db)
) -> EnvMachineBatchCommandResponse:
    """
    批量执行命令

    - 支持设备类型：Windows (CMD), Mac (Shell)
    - iOS/Android 设备和虚拟设备不支持，自动过滤
    - 单台设备超时 60 秒
    - 并行执行所有设备
    """
    # 查询设备
    machines = await EnvMachineService.get_by_ids(db, data.ids)

    # 过滤支持的设备（排除 iOS/Android 和虚拟设备）
    supported_machines = [
        m for m in machines
        if m.device_type in ('windows', 'mac')
        and not m.is_virtual
        and m.ip and m.port  # 必须有 IP 和端口
    ]

    # 并行执行所有设备
    results = await asyncio.gather(
        *[_execute_single_machine(m, data.command) for m in supported_machines],
        return_exceptions=True
    )

    # 处理结果（异常转为失败结果）
    final_results: List[CommandResultItem] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            machine = supported_machines[i]
            final_results.append(CommandResultItem(
                id=str(machine.id),
                ip=machine.ip or "",
                device_type=machine.device_type,
                device_name=machine.asset_number or machine.ip or str(machine.id),
                success=False,
                stdout="",
                stderr=str(result),
                duration_seconds=0.0
            ))
        else:
            final_results.append(result)

    # 统计成功/失败
    success_count = sum(1 for r in final_results if r.success)
    failed_count = len(final_results) - success_count

    # 对于不支持的设备，添加提示结果
    unsupported_machines = [m for m in machines if m not in supported_machines]
    for machine in unsupported_machines:
        reason = "虚拟设备不支持" if machine.is_virtual else "设备类型不支持（仅支持 Windows/Mac）"
        if not machine.ip or not machine.port:
            reason = "设备无 IP 或端口"
        final_results.append(CommandResultItem(
            id=str(machine.id),
            ip=machine.ip or "",
            device_type=machine.device_type,
            device_name=machine.asset_number or machine.ip or str(machine.id),
            success=False,
            stdout="",
            stderr=f"已过滤: {reason}",
            duration_seconds=0.0
        ))

    return EnvMachineBatchCommandResponse(
        results=final_results,
        total=len(data.ids),
        success_count=success_count,
        failed_count=len(final_results) - success_count
    )
```

- [ ] **Step 3: 验证语法正确**

运行: `python -c "from core.env_machine.api import batch_execute_command; print('API OK')"`

Expected: 输出 `API OK`

- [ ] **Step 4: 提交**

```bash
git add backend-fastapi/core/env_machine/api.py
git commit -m "feat(env_machine): 新增批量执行命令 API"
```

---

## Task 4: 前端 API 接口定义

**Files:**
- Modify: `web/apps/web-ele/src/api/core/env-machine.ts` (末尾追加)

- [ ] **Step 1: 新增接口类型和函数**

在 `env-machine.ts` 文件末尾追加以下代码：

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
    { timeout: 600000 }  // 整体超时 10 分钟（支持大批量执行）
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/api/core/env-machine.ts
git commit -m "feat(env-machine): 新增批量执行命令 API 接口"
```

---

## Task 5: 前端命令执行弹窗组件

**Files:**
- Create: `web/apps/web-ele/src/views/env-machine/modules/BatchCommandDialog.vue`

- [ ] **Step 1: 创建弹窗组件**

创建 `BatchCommandDialog.vue` 文件：

```vue
<script lang="ts" setup>
import type { EnvMachine, CommandResultItem } from '#/api/core/env-machine';

import { computed, ref, watch } from 'vue';

import {
  ElButton,
  ElDialog,
  ElInput,
  ElMessage,
  ElScrollbar,
} from 'element-plus';

import { batchExecuteCommandApi } from '#/api/core/env-machine';

interface Props {
  visible: boolean;
  selectedMachines: EnvMachine[];
}

interface Emits {
  (e: 'update:visible', value: boolean): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

// 命令输入
const command = ref('');

// 执行状态
const executing = ref(false);
const currentBatch = ref(0);
const totalBatches = ref(0);

// 执行结果
const results = ref<CommandResultItem[]>([]);

// 设备类型统计
const deviceStats = computed(() => {
  const machines = props.selectedMachines;
  const supported = machines.filter(
    m => (m.device_type === 'windows' || m.device_type === 'mac') && !m.is_virtual
  );
  const windows = supported.filter(m => m.device_type === 'windows').length;
  const mac = supported.filter(m => m.device_type === 'mac').length;
  const unsupported = machines.length - supported.length;
  return { windows, mac, unsupported, supported };
});

// 命令输入提示
const commandPlaceholder = computed(() => {
  if (deviceStats.value.windows > 0 && deviceStats.value.mac > 0) {
    return 'Windows 输入 CMD 命令，Mac 输入 Shell 命令';
  }
  if (deviceStats.value.windows > 0) {
    return '请输入 CMD 命令（Windows）';
  }
  if (deviceStats.value.mac > 0) {
    return '请输入 Shell 命令（Mac）';
  }
  return '无支持的设备';
});

// 监听弹窗打开，清空数据
watch(() => props.visible, (newVal) => {
  if (newVal) {
    command.value = '';
    results.value = [];
    executing.value = false;
    currentBatch.value = 0;
    totalBatches.value = 0;
  }
});

// 关闭弹窗
function handleClose() {
  if (executing.value) {
    ElMessage.warning('正在执行命令，请等待完成后再关闭');
    return;
  }
  emit('update:visible', false);
}

// 执行命令
async function handleExecute() {
  if (!command.value.trim()) {
    ElMessage.warning('请输入命令内容');
    return;
  }

  if (deviceStats.value.supported === 0) {
    ElMessage.warning('选中的设备不支持命令执行（仅支持 Windows/Mac 真实设备）');
    return;
  }

  executing.value = true;
  results.value = [];

  // 获取支持的设备
  const supportedMachines = props.selectedMachines.filter(
    m => (m.device_type === 'windows' || m.device_type === 'mac') && !m.is_virtual
  );

  // 分批执行（每批 20 台）
  const batchSize = 20;
  const batches: EnvMachine[][] = [];
  for (let i = 0; i < supportedMachines.length; i += batchSize) {
    batches.push(supportedMachines.slice(i, i + batchSize));
  }
  totalBatches.value = batches.length;

  // 逐批执行
  for (let i = 0; i < batches.length; i++) {
    currentBatch.value = i + 1;
    const batchIds = batches[i].map(m => m.id);

    try {
      const res = await batchExecuteCommandApi({
        ids: batchIds,
        command: command.value.trim(),
      });
      results.value.push(...res.results);
    } catch (error: any) {
      // 批次请求失败，标记所有设备为失败
      for (const machine of batches[i]) {
        results.value.push({
          id: machine.id,
          ip: machine.ip || '',
          device_type: machine.device_type,
          device_name: machine.asset_number || machine.ip || machine.id,
          success: false,
          stdout: '',
          stderr: error?.message || '请求失败',
          duration_seconds: 0,
        });
      }
    }
  }

  executing.value = false;

  // 显示完成提示
  const successCount = results.value.filter(r => r.success).length;
  const failedCount = results.value.length - successCount;
  if (failedCount === 0) {
    ElMessage.success(`全部执行成功 (${successCount} 台)`);
  } else if (successCount === 0) {
    ElMessage.error(`全部执行失败 (${failedCount} 台)`);
  } else {
    ElMessage.warning(`执行完成：成功 ${successCount} 台，失败 ${failedCount} 台`);
  }
}

// 格式化结果项标题
function getResultTitle(result: CommandResultItem): string {
  const typeText = result.device_type === 'windows' ? 'Windows' : 'Mac';
  return `${result.device_name || result.ip} (${typeText})`;
}

// 格式化耗时
function formatDuration(seconds: number): string {
  if (seconds < 1) {
    return `${Math.round(seconds * 1000)}ms`;
  }
  return `${seconds.toFixed(1)}s`;
}
</script>

<template>
  <ElDialog
    :model-value="visible"
    title="批量执行命令"
    width="700px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:visible', $event)"
    @close="handleClose"
  >
    <!-- 设备统计 -->
    <div class="stats-area">
      <div class="stats-row">
        已选中 <strong>{{ props.selectedMachines.length }}</strong> 台设备
        <span v-if="deviceStats.windows > 0">（Windows: {{ deviceStats.windows }}）</span>
        <span v-if="deviceStats.mac > 0">（Mac: {{ deviceStats.mac }}）</span>
      </div>
      <div v-if="deviceStats.unsupported > 0" class="stats-warning">
        注意：{{ deviceStats.unsupported }} 台设备不支持命令执行（iOS/Android 或虚拟设备），已自动过滤
      </div>
    </div>

    <!-- 命令输入 -->
    <div class="command-area">
      <div class="command-label">命令内容：</div>
      <ElInput
        v-model="command"
        type="textarea"
        :rows="3"
        :placeholder="commandPlaceholder"
        :disabled="executing"
      />
    </div>

    <!-- 执行进度 -->
    <div v-if="executing" class="progress-area">
      正在执行... 第 {{ currentBatch }}/{{ totalBatches }} 批
    </div>

    <!-- 执行按钮 -->
    <div class="button-area">
      <ElButton @click="handleClose">取消</ElButton>
      <ElButton
        type="primary"
        :loading="executing"
        :disabled="deviceStats.supported === 0"
        @click="handleExecute"
      >
        执行命令
      </ElButton>
    </div>

    <!-- 执行结果 -->
    <div v-if="results.length > 0" class="result-area">
      <div class="result-header">
        执行结果：
        <span class="result-summary">
          成功 {{ results.filter(r => r.success).length }} 台，
          失败 {{ results.filter(r => !r.success).length }} 台
        </span>
      </div>
      <ElScrollbar height="300px">
        <div class="result-list">
          <div
            v-for="result in results"
            :key="result.id"
            class="result-item"
            :class="{ 'result-success': result.success, 'result-failed': !result.success }"
          >
            <div class="result-title">
              <span class="result-icon">{{ result.success ? '✓' : '✗' }}</span>
              {{ getResultTitle(result) }}
              <span class="result-status">{{ result.success ? '成功' : '失败' }}</span>
              <span class="result-duration">{{ formatDuration(result.duration_seconds) }}</span>
            </div>
            <div v-if="result.stdout" class="result-output">
              <div class="output-label">stdout:</div>
              <pre class="output-content">{{ result.stdout }}</pre>
            </div>
            <div v-if="result.stderr" class="result-output result-stderr">
              <div class="output-label">stderr:</div>
              <pre class="output-content">{{ result.stderr }}</pre>
            </div>
          </div>
        </div>
      </ElScrollbar>
    </div>
  </ElDialog>
</template>

<style scoped>
.stats-area {
  margin-bottom: 16px;
  padding: 12px;
  background: #f5f5f5;
  border-radius: 4px;
}

.stats-row {
  font-size: 14px;
}

.stats-row strong {
  color: #1890ff;
}

.stats-warning {
  margin-top: 8px;
  font-size: 12px;
  color: #ff4d4f;
}

.command-area {
  margin-bottom: 16px;
}

.command-label {
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 500;
}

.progress-area {
  margin-bottom: 16px;
  padding: 8px 12px;
  background: #e6f7ff;
  border-radius: 4px;
  color: #1890ff;
  font-size: 13px;
}

.button-area {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-bottom: 16px;
}

.result-area {
  margin-top: 16px;
}

.result-header {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 500;
}

.result-summary {
  font-size: 12px;
  color: #666;
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.result-item {
  padding: 12px;
  border-radius: 4px;
  border: 1px solid #e8e8e8;
}

.result-success {
  background: #f6ffed;
  border-color: #b7eb8f;
}

.result-failed {
  background: #fff2f0;
  border-color: #ffccc7;
}

.result-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
}

.result-icon {
  font-size: 16px;
}

.result-success .result-icon {
  color: #52c41a;
}

.result-failed .result-icon {
  color: #ff4d4f;
}

.result-status {
  font-size: 12px;
}

.result-success .result-status {
  color: #52c41a;
}

.result-failed .result-status {
  color: #ff4d4f;
}

.result-duration {
  font-size: 12px;
  color: #999;
}

.result-output {
  margin-top: 8px;
}

.output-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}

.output-content {
  margin: 0;
  padding: 8px;
  font-size: 12px;
  font-family: Consolas, Monaco, 'Courier New', monospace;
  background: #fafafa;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}

.result-stderr .output-content {
  color: #ff4d4f;
}
</style>
```

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/env-machine/modules/BatchCommandDialog.vue
git commit -m "feat(env-machine): 新增批量执行命令弹窗组件"
```

---

## Task 6: 前端批量选择 Bug 修复 + 新增按钮

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/list.vue`

- [ ] **Step 1: 导入 Terminal 图标和弹窗组件**

在 `<script>` 部分的导入区域添加：

```typescript
import { Terminal } from '@element-plus/icons-vue';
import BatchCommandDialog from './modules/BatchCommandDialog.vue';
```

- [ ] **Step 2: 添加 tableRef、selectedIds 和 selectedMachinesMap**

在数据定义区域（约第 50 行），添加：

```typescript
// 表格引用（用于跨页选择同步）
const tableRef = ref<any>(null);

// 跨页选中的设备 ID
const selectedIds = ref<Set<string>>(new Set());

// 跨页选中的设备数据（Map: id -> machine，用于传递给弹窗）
const selectedMachinesMap = ref<Map<string, EnvMachine>>(new Map());
```

- [ ] **Step 3: 添加批量命令弹窗状态**

添加弹窗状态变量：

```typescript
// 批量命令弹窗
const batchCommandVisible = ref(false);
```

- [ ] **Step 4: 修改 handleSelectionChange 函数**

将现有的 `handleSelectionChange` 函数（约第 264 行）替换为：

```typescript
// 选择变化（跨页保持，同时存储设备数据）
function handleSelectionChange(rows: EnvMachine[]) {
  // 先移除当前页取消选中的设备
  const currentPageIds = tableData.value.map(r => r.id);
  for (const id of currentPageIds) {
    if (!rows.find(r => r.id === id)) {
      selectedIds.value.delete(id);
      selectedMachinesMap.value.delete(id);
    }
  }
  // 再添加当前页选中的设备
  for (const row of rows) {
    selectedIds.value.add(row.id);
    selectedMachinesMap.value.set(row.id, row);
  }
}
```

- [ ] **Step 5: 修改 loadData 函数同步选中状态**

在 `loadData` 函数的 `tableData.value = res.items || [];` 之后、`finally` 块之前，添加选中状态同步逻辑：

只需添加以下代码片段：

```typescript
    // 同步选中状态（跨页保持）
    nextTick(() => {
      if (tableRef.value) {
        tableData.value.forEach(row => {
          if (selectedIds.value.has(row.id)) {
            tableRef.value.toggleRowSelection(row, true);
          }
        });
      }
    });
```

注意：需要在文件顶部的 Vue 导入中添加 `nextTick`：
```typescript
import { onMounted, ref, nextTick } from 'vue';
```

- [ ] **Step 6: 修改批量删除函数使用 selectedIds**

将 `handleBatchDelete` 函数（约第 269 行）中的 `selectedRows.value` 改为使用 `selectedIds`：

```typescript
// 批量删除
function handleBatchDelete() {
  if (selectedIds.value.size === 0) {
    ElMessage.warning('请先选择要删除的设备');
    return;
  }

  const count = selectedIds.value.size;
  ElMessageBox.confirm(`确定要删除选中的 ${count} 台设备吗？`, '批量删除确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      const ids = Array.from(selectedIds.value);
      const res = await batchDeleteEnvMachineApi(ids);
      if (res.success_count > 0) {
        ElMessage.success(`成功删除 ${res.success_count} 台设备`);
      }
      // 注意：后端返回的是 failed_ids 数组，不是 failed_count
      const failedCount = res.failed_ids?.length || 0;
      if (failedCount > 0) {
        ElMessage.warning(`${failedCount} 台设备删除失败`);
      }
      selectedIds.value.clear();
      selectedMachinesMap.value.clear();
      loadData();
    } catch {
      ElMessage.error('批量删除失败');
    }
  });
}
```

- [ ] **Step 7: 添加打开批量命令弹窗函数和 getSelectedMachines**

添加新函数：

```typescript
// 打开批量命令弹窗
function handleOpenBatchCommand() {
  batchCommandVisible.value = true;
}

// 获取选中的设备列表（从 Map 中获取完整数据）
function getSelectedMachines(): EnvMachine[] {
  return Array.from(selectedMachinesMap.value.values());
}
```

- [ ] **Step 8: 修改模板中的 ElTable**

在 `<template>` 中的 `ElTable` 添加 `ref` 和 `row-key`：

```vue
<ElTable
  ref="tableRef"
  :data="tableData"
  v-loading="loading"
  class="env-table"
  border
  row-key="id"
  @selection-change="handleSelectionChange"
>
```

- [ ] **Step 9: 修改批量删除按钮显示数量**

将批量删除按钮的显示改为使用 `selectedIds.size`：

```vue
<ElButton
  type="danger"
  :disabled="selectedIds.size === 0"
  @click="handleBatchDelete"
>
  批量删除{{ selectedIds.size > 0 ? ` (${selectedIds.size})` : '' }}
</ElButton>
```

- [ ] **Step 10: 新增批量执行命令按钮**

在批量删除按钮代码块之后（`env-search-buttons` 区域内），插入以下按钮：

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

- [ ] **Step 11: 添加批量命令弹窗组件**

在模板末尾（日志弹窗之后）添加：

```vue
<!-- 批量命令弹窗 -->
<BatchCommandDialog
  v-model:visible="batchCommandVisible"
  :selected-machines="getSelectedMachines()"
/>
```

- [ ] **Step 12: 提交**

```bash
git add web/apps/web-ele/src/views/env-machine/list.vue
git commit -m "fix(env-machine): 修复批量选择跨页丢失 Bug，新增批量执行命令按钮"
```

---

## Task 7: 整合提交和验证

- [ ] **Step 1: 检查所有文件改动**

运行: `git status`

Expected: 所有改动文件已提交

- [ ] **Step 2: 检查前端类型**

运行: `cd web && pnpm check:type`

Expected: 无类型错误

- [ ] **Step 3: 启动后端服务测试**

运行: `cd backend-fastapi && python main.py`

Expected: 服务正常启动，无报错

- [ ] **Step 4: 启动前端服务测试**

运行: `cd web && pnpm dev`

Expected: 服务正常启动，可在浏览器访问

- [ ] **Step 5: 功能验证**

手动测试：
1. 批量选择跨页保持：第一页选中几条 → 切换第二页 → 返回第一页验证选中状态
2. 批量执行命令按钮：点击后弹窗打开
3. 弹窗显示设备统计和过滤提示

- [ ] **Step 6: 整合提交（如有遗漏）**

```bash
git add -A
git commit -m "feat(env-machine): 完成批量执行命令功能实现"
```