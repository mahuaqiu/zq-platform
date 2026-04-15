# 设备管理页面合并实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将集成验证/APP/音视频/公共设备4个页面合并为统一的"设备列表"页面，增加命名空间筛选和表格列。

**Architecture:** 
- 后端：修改 schema.py/service.py/api.py，支持 namespace 参数可选
- 前端：新增 list.vue 页面组件，基于 index.vue 改造，增加命名空间筛选和表格列
- 菜单：更新脚本删除旧菜单、创建新菜单

**Tech Stack:** FastAPI, SQLAlchemy, Vue 3, Element Plus, TypeScript

---

## 文件结构

### 后端文件
| 文件 | 操作 | 说明 |
|------|------|------|
| `backend-fastapi/core/env_machine/schema.py` | 修改 | namespace 参数改为 Optional |
| `backend-fastapi/core/env_machine/service.py` | 修改 | get_list_with_filters 支持可选 namespace |
| `backend-fastapi/core/env_machine/api.py` | 修改 | list_env_machines 参数改为 Optional |
| `backend-fastapi/scripts/init_env_machine_menu.py` | 修改 | 更新菜单配置 |
| `backend-fastapi/scripts/update_env_machine_menu.py` | 创建 | 新增菜单更新脚本 |

### 前端文件
| 文件 | 操作 | 说明 |
|------|------|------|
| `web/apps/web-ele/src/views/env-machine/types.ts` | 修改 | 新增命名空间选项和映射 |
| `web/apps/web-ele/src/api/core/env-machine.ts` | 修改 | namespace 参数改为可选 |
| `web/apps/web-ele/src/views/env-machine/list.vue` | 创建 | 新增设备列表页面 |
| `web/apps/web-ele/src/router/routes/modules/env-machine-list.ts` | 创建 | 新增路由配置 |

### 文档文件
| 文件 | 操作 | 说明 |
|------|------|------|
| `CLAUDE.md` | 修改 | 更新模块说明和脚本命令 |

---

## Task 1: 后端 Schema 改动

**Files:**
- Modify: `backend-fastapi/core/env_machine/schema.py:25-36`

- [ ] **Step 1: 修改 EnvMachineListRequest 的 namespace 参数**

将 `namespace: str` 改为 `namespace: Optional[str]`

```python
class EnvMachineListRequest(BaseModel):
    """执行机列表查询请求 Schema"""
    namespace: Optional[str] = Field(None, description="机器分类，None表示查询全部")
    device_type: Optional[str] = Field(None, description="机器类型")
    ip: Optional[str] = Field(None, description="IP地址（模糊查询）")
    asset_number: Optional[str] = Field(None, description="资产编号（模糊查询）")
    mark: Optional[str] = Field(None, description="标签（模糊查询）")
    available: Optional[bool] = Field(None, description="是否启用")
    note: Optional[str] = Field(None, description="备注（模糊查询）")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
```

- [ ] **Step 2: 提交改动**

```bash
git add backend-fastapi/core/env_machine/schema.py
git commit -m "feat(env_machine): schema namespace 参数改为可选"
```

---

## Task 2: 后端 Service 改动

**Files:**
- Modify: `backend-fastapi/core/env_machine/service.py:166-219`

- [ ] **Step 1: 修改 get_list_with_filters 方法签名**

将 `namespace: str` 改为 `namespace: Optional[str] = None`

```python
@classmethod
async def get_list_with_filters(
    cls,
    db: AsyncSession,
    namespace: Optional[str] = None,  # 改为 Optional
    device_type: Optional[str] = None,
    ip: Optional[str] = None,
    asset_number: Optional[str] = None,
    mark: Optional[str] = None,
    available: Optional[bool] = None,
    note: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
) -> Tuple[List[EnvMachine], int]:
```

- [ ] **Step 2: 修改方法实现逻辑**

```python
"""
多条件查询执行机列表

:param db: 数据库会话
:param namespace: 机器分类（可选，None表示查询全部）
:param device_type: 机器类型
:param ip: IP地址（模糊查询）
:param asset_number: 资产编号（模糊查询）
:param mark: 标签（模糊查询）
:param available: 是否启用
:param note: 备注（模糊查询）
:param page: 页码
:param page_size: 每页数量
:return: (机器列表, 总数)
"""
# 定义有效的命名空间列表（排除手工使用）
VALID_NAMESPACES = ['meeting_gamma', 'meeting_app', 'meeting_av', 'meeting_public']

filters = [EnvMachine.is_deleted == False]

if namespace:
    filters.append(EnvMachine.namespace == namespace)
else:
    # namespace 为 None 时，查询所有4个命名空间
    filters.append(EnvMachine.namespace.in_(VALID_NAMESPACES))

if device_type:
    filters.append(EnvMachine.device_type == device_type)

if ip:
    escaped_ip = ip.replace("%", r"\%").replace("_", r"\_")
    filters.append(EnvMachine.ip.ilike(f"%{escaped_ip}%"))

if asset_number:
    escaped_asset_number = asset_number.replace("%", r"\%").replace("_", r"\_")
    filters.append(EnvMachine.asset_number.ilike(f"%{escaped_asset_number}%"))

if mark:
    escaped_mark = mark.replace("%", r"\%").replace("_", r"\_")
    filters.append(EnvMachine.mark.ilike(f"%{escaped_mark}%"))

if available is not None:
    filters.append(EnvMachine.available == available)

if note:
    escaped_note = note.replace("%", r"\%").replace("_", r"\_")
    filters.append(EnvMachine.note.ilike(f"%{escaped_note}%"))

return await cls.get_list(db, page=page, page_size=page_size, filters=filters)
```

- [ ] **Step 3: 提交改动**

```bash
git add backend-fastapi/core/env_machine/service.py
git commit -m "feat(env_machine): service 支持可选 namespace 查询全部设备"
```

---

## Task 3: 后端 API 改动

**Files:**
- Modify: `backend-fastapi/core/env_machine/api.py:315-349`

- [ ] **Step 1: 修改 list_env_machines 函数参数**

将 `namespace: str` 改为 `namespace: Optional[str] = None`

```python
@router.get("", response_model=PaginatedResponse[EnvMachineResponse], summary="查询执行机列表")
async def list_env_machines(
    namespace: Optional[str] = None,  # 改为 Optional
    device_type: Optional[str] = None,
    ip: Optional[str] = None,
    asset_number: Optional[str] = None,
    mark: Optional[str] = None,
    available: Optional[bool] = None,
    note: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db)
) -> PaginatedResponse[EnvMachineResponse]:
    """
    查询执行机列表

    支持 namespace 可选筛选，其他条件可选。
    - namespace 为 None 时查询所有4个分类设备
    - namespace 有值时按指定分类筛选
    """
    machines, total = await EnvMachineService.get_list_with_filters(
        db,
        namespace=namespace,
        device_type=device_type,
        ip=ip,
        asset_number=asset_number,
        mark=mark,
        available=available,
        note=note,
        page=page,
        page_size=page_size,
    )

    return PaginatedResponse(
        items=[EnvMachineResponse.model_validate(m) for m in machines],
        total=total,
    )
```

- [ ] **Step 2: 提交改动**

```bash
git add backend-fastapi/core/env_machine/api.py
git commit -m "feat(env_machine): API namespace 参数改为可选"
```

---

## Task 4: 前端 types.ts 更新

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/types.ts`

- [ ] **Step 1: 在 NAMESPACE_MAP 后添加命名空间选项和显示映射**

```typescript
/**
 * Namespace 映射（路由参数到后端值）
 */
export const NAMESPACE_MAP: Record<string, string> = {
  gamma: 'meeting_gamma',
  app: 'meeting_app',
  av: 'meeting_av',
  public: 'meeting_public',
  manual: 'meeting_manual',
};

/**
 * 命名空间选项（用于筛选下拉框）
 */
export const NAMESPACE_OPTIONS = [
  { label: '全部', value: '' },
  { label: '集成验证', value: 'meeting_gamma' },
  { label: 'APP', value: 'meeting_app' },
  { label: '音视频', value: 'meeting_av' },
  { label: '公共设备', value: 'meeting_public' },
];

/**
 * 命名空间中文映射（用于表格显示）
 */
export const NAMESPACE_DISPLAY_MAP: Record<string, string> = {
  meeting_gamma: '集成验证',
  meeting_app: 'APP',
  meeting_av: '音视频',
  meeting_public: '公共设备',
};
```

- [ ] **Step 2: 提交改动**

```bash
git add web/apps/web-ele/src/views/env-machine/types.ts
git commit -m "feat(env_machine): 新增命名空间选项和中文映射"
```

---

## Task 5: 前端 API 更新

**Files:**
- Modify: `web/apps/web-ele/src/api/core/env-machine.ts:32-43`

- [ ] **Step 1: 修改 EnvMachineQueryParams 的 namespace 为可选**

```typescript
/**
 * 查询参数
 */
export interface EnvMachineQueryParams {
  namespace?: string;  // 改为可选，空表示查询全部
  device_type?: string;
  ip?: string;
  asset_number?: string;
  mark?: string;
  available?: boolean;
  status?: string;
  note?: string;
  page: number;
  page_size: number;
}
```

- [ ] **Step 2: 提交改动**

```bash
git add web/apps/web-ele/src/api/core/env-machine.ts
git commit -m "feat(env_machine): API namespace 参数改为可选"
```

---

## Task 6: 前端创建设备列表页面

**Files:**
- Create: `web/apps/web-ele/src/views/env-machine/list.vue`

- [ ] **Step 1: 创建 list.vue 组件**

基于 index.vue 改造，主要改动：
1. 移除 namespace 路由计算逻辑（不再从路由获取）
2. 新增命名空间筛选下拉框（首位，默认"全部"）
3. 表格新增首列"命名空间"（显示中文）

完整代码见下方：

```vue
<script lang="ts" setup>
import type { EnvMachine } from '#/api/core/env-machine';

import { onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElDialog,
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

import {
  deleteEnvMachineApi,
  getEnvMachineListApi,
  updateEnvMachineApi,
} from '#/api/core/env-machine';
import type { EnvMachineUpdateParams } from '#/api/core/env-machine';

import {
  NAMESPACE_OPTIONS,
  NAMESPACE_DISPLAY_MAP,
  DEVICE_TYPE_OPTIONS,
  STATUS_OPTIONS,
  isMobileDevice,
} from './types';
import LogDialog from './LogDialog.vue';

defineOptions({ name: 'EnvMachineListPage' });

// 数据
const tableData = ref<EnvMachine[]>([]);
const total = ref(0);
const loading = ref(false);
const currentPage = ref(1);
const pageSize = ref(20);

// 篮选条件
const searchForm = ref({
  namespace: '',  // 默认全部
  device_type: '',
  ip: '',
  asset_number: '',
  mark: '',
  available: undefined as boolean | undefined,
  note: '',
});

// 弹窗
const dialogVisible = ref(false);
const dialogLoading = ref(false);
const isEdit = ref(false);
const editId = ref('');

// 表单数据
const formData = ref({
  asset_number: '',
  ip: '',
  device_sn: '',
  note: '',
  mark: '',
  available: false,
  extra_message_raw: '',
});

// JSON 格式错误提示
const jsonError = ref('');

// 日志弹窗
const logDialogVisible = ref(false);
const logMachineId = ref('');
const logMachineIp = ref('');
const logMachinePort = ref('');

// 打开日志弹窗
function handleViewLogs(row: EnvMachine) {
  logMachineId.value = row.id;
  logMachineIp.value = row.ip || row.id;
  logMachinePort.value = row.port || '';
  logDialogVisible.value = true;
}

// 验证扩展信息是否包含标签对应的账号信息
function validateExtraMessageWithTag(): boolean {
  const raw = formData.value.extra_message_raw.trim();
  const mark = formData.value.mark?.trim();

  if (!raw || !mark) {
    return false;
  }

  try {
    const parsed = JSON.parse(raw);
    return parsed.hasOwnProperty(mark) && typeof parsed[mark] === 'object';
  } catch {
    return false;
  }
}

// 清理 JSON 中的 key/value 首尾空格
function trimJsonKeysAndValues(obj: Record<string, any>): Record<string, any> {
  const result: Record<string, any> = {};
  for (const key of Object.keys(obj)) {
    const trimmedKey = key.trim();
    const value = obj[key];
    if (typeof value === 'string') {
      result[trimmedKey] = value.trim();
    } else if (typeof value === 'object' && value !== null) {
      result[trimmedKey] = trimJsonKeysAndValues(value);
    } else {
      result[trimmedKey] = value;
    }
  }
  return result;
}

// 验证 JSON 格式
function validateJson(): Record<string, any> | null {
  const raw = formData.value.extra_message_raw.trim();
  if (!raw) {
    jsonError.value = '';
    return {};
  }
  try {
    const parsed = JSON.parse(raw);
    jsonError.value = '';
    return trimJsonKeysAndValues(parsed);
  } catch (e) {
    jsonError.value = 'JSON 格式不正确，请检查格式';
    return null;
  }
}

// 加载数据
async function loadData() {
  loading.value = true;
  try {
    const res = await getEnvMachineListApi({
      namespace: searchForm.value.namespace || undefined,  // 空则不传
      device_type: searchForm.value.device_type || undefined,
      ip: searchForm.value.ip || undefined,
      asset_number: searchForm.value.asset_number || undefined,
      mark: searchForm.value.mark || undefined,
      available: searchForm.value.available,
      note: searchForm.value.note || undefined,
      page: currentPage.value,
      page_size: pageSize.value,
    });
    tableData.value = res.items || [];
    total.value = res.total || 0;
  } catch (error) {
    console.error('加载数据失败:', error);
    ElMessage.error('加载数据失败');
  } finally {
    loading.value = false;
  }
}

// 搜索
function handleSearch() {
  currentPage.value = 1;
  loadData();
}

// 重置
function handleReset() {
  searchForm.value = {
    namespace: '',
    device_type: '',
    ip: '',
    asset_number: '',
    mark: '',
    available: undefined,
    note: '',
  };
  currentPage.value = 1;
  loadData();
}

// 分页
function handlePageChange(page: number) {
  currentPage.value = page;
  loadData();
}

function handleSizeChange(size: number) {
  pageSize.value = size;
  currentPage.value = 1;
  loadData();
}

// 编辑
function handleEdit(row: EnvMachine) {
  isEdit.value = true;
  editId.value = row.id;
  formData.value = {
    asset_number: row.asset_number || '',
    ip: row.ip || '',
    device_sn: row.device_sn || '',
    note: row.note || '',
    mark: row.mark || '',
    available: row.available,
    extra_message_raw: row.extra_message ? JSON.stringify(row.extra_message, null, 2) : '',
  };
  jsonError.value = '';
  dialogVisible.value = true;
}

// 删除
function handleDelete(row: EnvMachine) {
  const displayName = row.asset_number || row.ip || row.id;
  ElMessageBox.confirm(`确定要删除设备 "${displayName}" 吗？`, '删除确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      await deleteEnvMachineApi(row.id);
      ElMessage.success('删除成功');
      loadData();
    } catch {
      ElMessage.error('删除失败');
    }
  });
}

// 获取命名空间显示文本
function getNamespaceText(namespace: string) {
  return NAMESPACE_DISPLAY_MAP[namespace] || namespace;
}

// 获取状态文本
function getStatusText(status: string) {
  const opt = STATUS_OPTIONS.find((o) => o.value === status);
  return opt?.label || status;
}

// 获取状态样式类
function getStatusClass(status: string) {
  const statusMap: Record<string, string> = {
    online: 'env-status-success',
    using: 'env-status-orange',
    offline: 'env-status-warning',
    upgrading: 'env-status-upgrading',
  };
  return statusMap[status] || '';
}

// 格式化扩展信息
function formatExtraMessage(extra: Record<string, any>) {
  const parts: string[] = [];
  if (extra.CPU) parts.push(`CPU: ${extra.CPU}`);
  if (extra.RAM) parts.push(`RAM: ${extra.RAM}`);
  if (extra.device_model) parts.push(extra.device_model);
  return parts.join(', ') || JSON.stringify(extra);
}

// 获取设备类型文本
function getDeviceTypeText(type: string) {
  const opt = DEVICE_TYPE_OPTIONS.find((o) => o.value === type);
  return opt?.label || type;
}

// 提交表单
async function handleSubmit() {
  // 验证扩展信息
  const extraMessage = validateJson();
  if (extraMessage === null) {
    ElMessage.warning('扩展信息 JSON 格式不正确，请修正后再保存');
    return;
  }

  // 启用时检查标签和扩展信息
  if (formData.value.available) {
    const mark = formData.value.mark?.trim();

    // 检查标签是否填写
    if (!mark) {
      ElMessageBox.alert(
        '启用设备时必须填写标签。\n\n标签用于匹配扩展信息中的账号配置。',
        '无法启用',
        {
          confirmButtonText: '确定',
          type: 'warning',
        }
      );
      return;
    }

    // 检查扩展信息是否填写且包含对应标签
    if (!validateExtraMessageWithTag()) {
      ElMessageBox.alert(
        `需要填入扩展信息（机器使用的账号信息）才能启用设备。\n\n扩展信息需要包含标签 "${mark}" 对应的账号配置。`,
        '无法启用',
        {
          confirmButtonText: '确定',
          type: 'warning',
        }
      );
      return;
    }
  }

  dialogLoading.value = true;
  try {
    const updateData: EnvMachineUpdateParams = {
      asset_number: formData.value.asset_number,
      ip: formData.value.ip,
      device_sn: formData.value.device_sn,
      mark: formData.value.mark,
      available: formData.value.available,
      note: formData.value.note,
    };
    if (formData.value.extra_message_raw.trim()) {
      updateData.extra_message = JSON.parse(formData.value.extra_message_raw.trim());
    }
    await updateEnvMachineApi(editId.value, updateData);
    ElMessage.success('更新成功');
    dialogVisible.value = false;
    loadData();
  } catch (error: any) {
    const msg = error?.response?.data?.detail || '操作失败';
    ElMessage.error(msg);
  } finally {
    dialogLoading.value = false;
  }
}

// 初始加载
onMounted(() => {
  loadData();
});
</script>

<template>
  <Page auto-content-height>
    <div class="flex h-full flex-col">
      <!-- 搜索区域 -->
      <div class="env-search-area">
        <div class="env-search-form">
          <div class="env-search-item">
            <label class="env-search-label">命名空间</label>
            <ElSelect
              v-model="searchForm.namespace"
              placeholder="请选择"
              clearable
              style="width: 120px"
            >
              <ElOption
                v-for="opt in NAMESPACE_OPTIONS"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </ElSelect>
          </div>
          <div class="env-search-item">
            <label class="env-search-label">机器类型</label>
            <ElSelect
              v-model="searchForm.device_type"
              placeholder="请选择"
              clearable
              style="width: 150px"
            >
              <ElOption
                v-for="opt in DEVICE_TYPE_OPTIONS"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </ElSelect>
          </div>
          <div class="env-search-item">
            <label class="env-search-label">机器信息</label>
            <ElInput
              v-model="searchForm.ip"
              placeholder="搜索IP地址"
              clearable
              style="width: 180px"
            />
          </div>
          <div class="env-search-item">
            <label class="env-search-label">资产编号</label>
            <ElInput
              v-model="searchForm.asset_number"
              placeholder="搜索资产编号"
              clearable
              style="width: 150px"
            />
          </div>
          <div class="env-search-item">
            <label class="env-search-label">标签</label>
            <ElInput
              v-model="searchForm.mark"
              placeholder="搜索标签"
              clearable
              style="width: 150px"
            />
          </div>
          <div class="env-search-item">
            <label class="env-search-label">是否启用</label>
            <ElSelect
              v-model="searchForm.available"
              placeholder="全部"
              clearable
              style="width: 100px"
            >
              <ElOption label="是" :value="true" />
              <ElOption label="否" :value="false" />
            </ElSelect>
          </div>

          <div class="env-search-buttons">
            <ElButton type="primary" @click="handleSearch">查询</ElButton>
            <ElButton @click="handleReset">重置</ElButton>
          </div>
        </div>
      </div>

      <!-- 表格区域 -->
      <div class="env-table-wrapper">
        <ElTable :data="tableData" v-loading="loading" class="env-table" border>
          <ElTableColumn prop="namespace" label="命名空间" min-width="100">
            <template #default="{ row }">
              {{ getNamespaceText(row.namespace) }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="device_type" label="机器类型" min-width="90">
            <template #default="{ row }">
              {{ getDeviceTypeText(row.device_type) }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="ip" label="机器信息" min-width="120">
            <template #default="{ row }">
              <code v-if="row.ip" class="env-code">{{ row.ip }}</code>
              <span v-else class="env-dash">-</span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="device_sn" label="SN" min-width="100">
            <template #default="{ row }">
              {{ row.device_sn || '-' }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="asset_number" label="资产编号" min-width="110" />
          <ElTableColumn prop="mark" label="标签" min-width="80">
            <template #default="{ row }">
              {{ row.mark || '-' }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="status" label="状态" min-width="60" align="center">
            <template #default="{ row }">
              <span :class="getStatusClass(row.status)">{{ getStatusText(row.status) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="available" label="是否启用" min-width="70" align="center">
            <template #default="{ row }">
              <span :class="row.available ? 'env-status-success' : 'env-status-danger'">
                {{ row.available ? '是' : '否' }}
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="note" label="备注" min-width="100" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.note || '-' }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="extra_message" label="扩展信息" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">
              <template v-if="row.extra_message">
                {{ formatExtraMessage(row.extra_message) }}
              </template>
              <span v-else class="env-dash">-</span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="version" label="版本" min-width="100">
            <template #default="{ row }">
              <span class="nowrap">{{ row.version || '-' }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" min-width="160">
            <template #default="{ row }">
              <span class="nowrap">
                <a v-if="!isMobileDevice(row.device_type) && row.status !== 'offline'" class="env-link" @click="handleViewLogs(row)">日志</a>
                <a class="env-link" @click="handleEdit(row)">编辑</a>
                <a class="env-link env-link-danger" @click="handleDelete(row)">删除</a>
              </span>
            </template>
          </ElTableColumn>
        </ElTable>

        <!-- 分页 -->
        <div class="env-pagination">
          <ElPagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :total="total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            @current-change="handlePageChange"
            @size-change="handleSizeChange"
          />
        </div>
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <ElDialog
      v-model="dialogVisible"
      title="编辑设备"
      width="500px"
      :close-on-click-modal="false"
    >
      <ElForm label-width="80px">
        <ElFormItem label="资产编号">
          <ElInput v-model="formData.asset_number" placeholder="请输入资产编号" />
        </ElFormItem>

        <ElFormItem label="IP地址">
          <ElInput v-model="formData.ip" placeholder="请输入IP地址" />
        </ElFormItem>

        <ElFormItem label="SN">
          <ElInput v-model="formData.device_sn" placeholder="请输入设备SN号（可选）" />
        </ElFormItem>

        <ElFormItem label="标签">
          <ElInput v-model="formData.mark" placeholder="请输入标签，多个用逗号分隔" />
        </ElFormItem>

        <ElFormItem label="是否启用">
          <ElSelect v-model="formData.available" style="width: 100%">
            <ElOption label="是" :value="true" />
            <ElOption label="否" :value="false" />
          </ElSelect>
        </ElFormItem>

        <ElFormItem label="扩展信息">
          <ElInput
            v-model="formData.extra_message_raw"
            type="textarea"
            :rows="8"
            placeholder="JSON格式，按标签存储账号信息"
          />
          <div v-if="jsonError" class="json-error">{{ jsonError }}</div>
        </ElFormItem>

        <ElFormItem label="备注">
          <ElInput
            v-model="formData.note"
            type="textarea"
            :rows="3"
            placeholder="请输入备注信息"
          />
        </ElFormItem>
      </ElForm>

      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="dialogLoading" @click="handleSubmit">
          确定
        </ElButton>
      </template>
    </ElDialog>

    <!-- 日志弹窗 -->
    <LogDialog
      v-model:visible="logDialogVisible"
      :machine-id="logMachineId"
      :machine-ip="logMachineIp"
      :machine-port="logMachinePort"
    />
  </Page>
</template>

<style scoped>
.json-error {
  color: #ff4d4f;
  font-size: 12px;
  margin-top: 4px;
}

/* 搜索区域 */
.env-search-area {
  padding: 16px;
  margin-bottom: 16px;
  background: #fafafa;
  border-radius: 4px;
}

.env-search-form {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: flex-end;
}

.env-search-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.env-search-label {
  display: block;
  font-size: 12px;
  color: #666;
}

.env-search-buttons {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

/* 表格区域 */
.env-table-wrapper {
  flex: 1;
  padding: 16px;
  overflow: auto;
  background: #fff;
  border-radius: 4px;
}

.env-table-wrapper :deep(.el-table__body-wrapper) {
  overflow-x: auto;
}

.env-table {
  --el-table-border-color: #e8e8e8;
  --el-table-header-bg-color: #fafafa;
  --el-table-tr-bg-color: #fff;
  --el-table-row-hover-bg-color: #fafafa;
  --el-table-text-color: #333;
  --el-table-header-text-color: #333;
}

.env-table :deep(.el-table__inner-wrapper::before) {
  display: none;
}

.env-table :deep(.el-table__border-left-patch) {
  background-color: #e8e8e8 !important;
}

.env-table :deep(th.el-table__cell) {
  padding: 12px 10px !important;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  white-space: nowrap;
  background: #fafafa !important;
  border-color: #e8e8e8 !important;
  border-right: 1px solid #e8e8e8 !important;
  border-bottom: 1px solid #e8e8e8 !important;
}

.env-table :deep(td.el-table__cell) {
  padding: 12px 10px !important;
  font-size: 13px;
  color: #333;
  border-color: #e8e8e8 !important;
  border-right: 1px solid #e8e8e8 !important;
  border-bottom: 1px solid #e8e8e8 !important;
}

.env-code {
  padding: 2px 6px;
  font-family: Consolas, Monaco, 'Courier New', monospace;
  font-size: 13px;
  background: #f5f5f5;
  border-radius: 4px;
}

.env-dash {
  color: #999;
}

.env-status-success {
  color: #52c41a;
}

.env-status-orange {
  color: #e6a23c;
}

.env-status-warning {
  color: #faad14;
}

.env-status-danger {
  color: #ff4d4f;
}

.env-status-upgrading {
  color: #1890ff;
}

.env-link {
  margin-right: 12px;
  color: #1890ff;
  text-decoration: none;
  cursor: pointer;
}

.env-link:hover {
  text-decoration: underline;
}

.env-link-danger {
  margin-right: 0;
  color: #ff4d4f;
}

.env-pagination {
  display: flex;
  justify-content: flex-end;
  padding: 16px 0 0;
}

.nowrap {
  white-space: nowrap;
}
</style>
```

- [ ] **Step 2: 提交改动**

```bash
git add web/apps/web-ele/src/views/env-machine/list.vue
git commit -m "feat(env_machine): 新增设备列表页面"
```

---

## Task 7: 前端路由配置

**Files:**
- Create: `web/apps/web-ele/src/router/routes/modules/env-machine-list.ts`

- [ ] **Step 1: 创建路由配置文件**

```typescript
import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/env-machine/list',
    name: 'EnvMachineList',
    component: () => import('#/views/env-machine/list.vue'),
    meta: {
      title: '设备列表',
      hideInMenu: true, // 菜单从后端获取，前端只定义组件映射
    },
  },
];

export default routes;
```

- [ ] **Step 2: 提交改动**

```bash
git add web/apps/web-ele/src/router/routes/modules/env-machine-list.ts
git commit -m "feat(env_machine): 新增设备列表路由配置"
```

---

## Task 8: 菜单初始化脚本更新

**Files:**
- Modify: `backend-fastapi/scripts/init_env_machine_menu.py`

- [ ] **Step 1: 更新菜单配置**

删除 gamma/app/av/public 四个子菜单，新增"设备列表"菜单：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
初始化执行机管理菜单
执行方式: cd backend-fastapi && python scripts/init_env_machine_menu.py

注意：超级管理员（is_superuser=True）自动拥有所有菜单权限，无需额外分配
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from core.menu.model import Menu


# 菜单配置数据
MENUS = [
    # 一级菜单
    {
        "id": "env-machine-root",
        "name": "EnvMachine",
        "title": "设备管理",
        "path": "/env-machine",
        "type": "catalog",
        "icon": "ep:monitor",
        "order": 100,
        "parent_id": None,
    },
    # 二级菜单：设备列表（合并）
    {
        "id": "env-machine-list",
        "name": "EnvMachineList",
        "title": "设备列表",
        "path": "/env-machine/list",
        "type": "menu",
        "component": "/views/env-machine/list",
        "parent_id": "env-machine-root",
        "order": 1,
    },
    # 二级菜单：手工使用
    {
        "id": "env-machine-manual",
        "name": "EnvMachineManual",
        "title": "手工使用",
        "path": "/env-machine/manual",
        "type": "menu",
        "component": "/views/env-machine/index",
        "parent_id": "env-machine-root",
        "order": 2,
    },
]


async def init_menus():
    """初始化菜单"""
    async with AsyncSessionLocal() as session:
        # 创建菜单
        for menu_data in MENUS:
            result = await session.execute(
                select(Menu).where(Menu.id == menu_data["id"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"菜单已存在，跳过: {menu_data['title']}")
                continue

            menu = Menu(
                id=menu_data["id"],
                name=menu_data["name"],
                title=menu_data["title"],
                path=menu_data["path"],
                type=menu_data["type"],
                icon=menu_data.get("icon"),
                component=menu_data.get("component"),
                parent_id=menu_data.get("parent_id"),
                order=menu_data.get("order", 0),
                sort=menu_data.get("order", 0),
            )
            session.add(menu)
            print(f"创建菜单: {menu_data['title']}")

        await session.commit()
        print("\n菜单初始化完成！超级管理员用户请刷新前端页面查看。")


if __name__ == "__main__":
    asyncio.run(init_menus())
```

- [ ] **Step 2: 提交改动**

```bash
git add backend-fastapi/scripts/init_env_machine_menu.py
git commit -m "feat(env_machine): 更新菜单初始化脚本，合并子菜单"
```

---

## Task 9: 菜单更新脚本

**Files:**
- Create: `backend-fastapi/scripts/update_env_machine_menu.py`

- [ ] **Step 1: 创建菜单更新脚本**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新执行机管理菜单（合并4个子菜单为设备列表）
执行方式: cd backend-fastapi && python scripts/update_env_machine_menu.py
"""
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select, delete
from app.database import AsyncSessionLocal
from core.menu.model import Menu

# 要删除的旧菜单ID
OLD_MENU_IDS = [
    "env-machine-gamma",
    "env-machine-app",
    "env-machine-av",
    "env-machine-public",
]

# 新菜单配置
NEW_MENUS = [
    {
        "id": "env-machine-list",
        "name": "EnvMachineList",
        "title": "设备列表",
        "path": "/env-machine/list",
        "type": "menu",
        "component": "/views/env-machine/list",
        "parent_id": "env-machine-root",
        "order": 1,
    },
]


async def update_menus():
    """更新菜单"""
    async with AsyncSessionLocal() as session:
        # 1. 删除旧菜单
        for menu_id in OLD_MENU_IDS:
            result = await session.execute(delete(Menu).where(Menu.id == menu_id))
            if result.rowcount > 0:
                print(f"删除菜单: {menu_id}")
        
        # 2. 创建新菜单
        for menu_data in NEW_MENUS:
            result = await session.execute(
                select(Menu).where(Menu.id == menu_data["id"])
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                print(f"菜单已存在，跳过: {menu_data['title']}")
                continue
            
            menu = Menu(
                id=menu_data["id"],
                name=menu_data["name"],
                title=menu_data["title"],
                path=menu_data["path"],
                type=menu_data["type"],
                component=menu_data.get("component"),
                parent_id=menu_data.get("parent_id"),
                order=menu_data.get("order", 0),
                sort=menu_data.get("order", 0),
            )
            session.add(menu)
            print(f"创建菜单: {menu_data['title']}")
        
        # 3. 更新手工使用菜单的order
        result = await session.execute(
            select(Menu).where(Menu.id == "env-machine-manual")
        )
        manual_menu = result.scalar_one_or_none()
        if manual_menu:
            manual_menu.order = 2
            manual_menu.sort = 2
            print(f"更新菜单顺序: 手工使用 -> order=2")
        
        await session.commit()
        print("\n菜单更新完成！请刷新前端页面查看。")


if __name__ == "__main__":
    asyncio.run(update_menus())
```

- [ ] **Step 2: 提交改动**

```bash
git add backend-fastapi/scripts/update_env_machine_menu.py
git commit -m "feat(env_machine): 新增菜单更新脚本"
```

---

## Task 10: 文档更新

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 更新核心模块表格**

将 `env_machine` 的说明改为：

```markdown
| env_machine | 执行机管理（设备管理）- 设备列表页面（合并集成验证/APP/音视频/公共设备）、手工使用页面 |
```

- [ ] **Step 2: 更新初始化脚本命令列表**

在"初始化菜单脚本"部分添加更新脚本说明：

```bash
# 初始化菜单脚本
python scripts/init_env_machine_menu.py    # 设备管理菜单（设备列表+手工使用）
# 或使用更新脚本合并旧菜单
python scripts/update_env_machine_menu.py  # 合并4个子菜单为设备列表
```

- [ ] **Step 3: 提交改动**

```bash
git add CLAUDE.md
git commit -m "docs: 更新设备管理模块说明和脚本命令"
```

---

## Task 11: 执行菜单更新脚本

**Files:**
- Run: `python scripts/update_env_machine_menu.py`

- [ ] **Step 1: 激活虚拟环境并执行脚本**

```bash
cd backend-fastapi
conda activate zq-fastapi
python scripts/update_env_machine_menu.py
```

预期输出：
```
删除菜单: env-machine-gamma
删除菜单: env-machine-app
删除菜单: env-machine-av
删除菜单: env-machine-public
创建菜单: 设备列表
更新菜单顺序: 手工使用 -> order=2

菜单更新完成！请刷新前端页面查看。
```

---

## 验收清单

- [ ] 后端 API 支持 namespace 参数可选（空值查询全部）
- [ ] 前端设备列表页面筛选区有命名空间下拉框，默认"全部"
- [ ] 选择"全部"时显示所有4个分类的设备
- [ ] 表格首列显示命名空间中文名称
- [ ] 菜单结构为：设备管理 → 设备列表、手工使用
- [ ] 旧菜单（集成验证/APP/音视频/公共设备）已删除
- [ ] CLAUDE.md 文档已更新
- [ ] 手工使用页面功能保持不变