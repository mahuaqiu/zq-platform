<script lang="ts" setup>
import type { EnvMachine } from '#/api/core/env-machine';

import { nextTick, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { Terminal } from '@element-plus/icons-vue';

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
  batchDeleteEnvMachineApi,
  batchImportVirtualDevicesApi,
  downloadImportTemplateApi,
} from '#/api/core/env-machine';
import type { EnvMachineUpdateParams } from '#/api/core/env-machine';

import {
  NAMESPACE_OPTIONS,
  NAMESPACE_DISPLAY_MAP,
  DEVICE_TYPE_OPTIONS,
  STATUS_OPTIONS,
  isMobileDevice,
} from './types';
import LogDialogV2 from './LogDialogV2.vue';
import BatchCommandDialog from './modules/BatchCommandDialog.vue';
import CodeEditor from '#/components/zq-form/code-editor/code-editor.vue';

defineOptions({ name: 'EnvMachineListPage' });

// 路由
const router = useRouter();

// 数据
const tableData = ref<EnvMachine[]>([]);
const total = ref(0);
const loading = ref(false);
const currentPage = ref(1);
const pageSize = ref(20);
const selectedRows = ref<EnvMachine[]>([]);  // 选中的行
const tableRef = ref();  // 表格实例
const selectedIds = ref<Set<string>>(new Set());  // 跨分页选中的 ID
const selectedMachinesMap = ref<Map<string, EnvMachine>>(new Map());  // 跨分页选中的设备信息

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

// 导入弹窗
const importDialogVisible = ref(false);
const importLoading = ref(false);
const importFile = ref<File | null>(null);
const importResult = ref<{
  success_count: number;
  failed_items: Array<{ row: number; reason: string }>;
} | null>(null);

// 批量命令弹窗
const batchCommandVisible = ref(false);

// 打开日志弹窗
function handleViewLogs(row: EnvMachine) {
  logMachineId.value = row.id;
  logMachineIp.value = row.ip || row.id;
  logMachinePort.value = row.port || '';
  logDialogVisible.value = true;
}

// 打开调试页面
function handleDebug(row: EnvMachine) {
  router.push(`/device-debug/${row.id}`);
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
    // 标签可能是多个（用逗号分隔），需要拆分检查每个标签
    const tags = mark.split(',').map((t) => t.trim()).filter((t) => t);
    // 检查每个标签是否都在扩展信息中有对应配置
    return tags.every((tag) => parsed.hasOwnProperty(tag) && typeof parsed[tag] === 'object');
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
    // 跨分页选中：恢复选中状态
    await nextTick();
    if (tableRef.value) {
      tableData.value.forEach((row) => {
        if (selectedIds.value.has(row.id)) {
          tableRef.value.toggleRowSelection(row, true);
        }
      });
    }
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

// 选择变化
function handleSelectionChange(rows: EnvMachine[]) {
  selectedRows.value = rows;
  // 更新跨分页选中状态
  const currentPageIds = new Set(tableData.value.map((row) => row.id));
  // 移除当前页面未选中的
  currentPageIds.forEach((id) => {
    if (!rows.find((r) => r.id === id)) {
      selectedIds.value.delete(id);
      selectedMachinesMap.value.delete(id);
    }
  });
  // 添加当前页面选中的
  rows.forEach((row) => {
    selectedIds.value.add(row.id);
    selectedMachinesMap.value.set(row.id, row);
  });
}

// 批量删除
function handleBatchDelete() {
  const count = selectedIds.value.size;
  if (count === 0) {
    ElMessage.warning('请先选择要删除的设备');
    return;
  }

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
      if (res.failed_count > 0 && res.failed_ids && res.failed_ids.length > 0) {
        ElMessage.warning(`${res.failed_count} 台设备删除失败`);
      }
      // 清空选中状态
      selectedIds.value.clear();
      selectedMachinesMap.value.clear();
      loadData();
    } catch {
      ElMessage.error('批量删除失败');
    }
  });
}

// 打开批量命令弹窗
function handleOpenBatchCommand() {
  if (selectedIds.value.size === 0) {
    ElMessage.warning('请先选择要执行命令的设备');
    return;
  }
  batchCommandVisible.value = true;
}

// 获取选中的设备列表
function getSelectedMachines(): EnvMachine[] {
  return Array.from(selectedMachinesMap.value.values());
}

// 打开导入弹窗
function handleOpenImport() {
  importFile.value = null;
  importResult.value = null;
  importDialogVisible.value = true;
}

// 文件选择变化
function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    importFile.value = target.files[0];
    importResult.value = null;
  }
}

// 下载导入模板
async function handleDownloadTemplate() {
  try {
    const blob = await downloadImportTemplateApi();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = '虚拟设备导入模板.xlsx';
    a.click();
    window.URL.revokeObjectURL(url);
    ElMessage.success('模板下载成功');
  } catch {
    ElMessage.error('模板下载失败');
  }
}

// 执行导入
async function handleImport() {
  if (!importFile.value) {
    ElMessage.warning('请先选择要导入的文件');
    return;
  }

  importLoading.value = true;
  try {
    const res = await batchImportVirtualDevicesApi(importFile.value);
    importResult.value = res;
    if (res.success_count > 0) {
      ElMessage.success(`成功导入 ${res.success_count} 台设备`);
      loadData();
    }
  } catch (error: any) {
    const msg = error?.response?.data?.detail || '导入失败';
    ElMessage.error(msg);
  } finally {
    importLoading.value = false;
  }
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
            <ElButton type="success" @click="handleOpenImport">批量导入</ElButton>
            <ElButton
              type="danger"
              :disabled="selectedIds.size === 0"
              @click="handleBatchDelete"
            >
              批量删除{{ selectedIds.size > 0 ? ` (${selectedIds.size})` : '' }}
            </ElButton>
            <ElButton
              type="primary"
              :disabled="selectedIds.size === 0"
              @click="handleOpenBatchCommand"
            >
              <Terminal class="mr-1 size-4" />
              批量执行命令{{ selectedIds.size > 0 ? ` (${selectedIds.size})` : '' }}
            </ElButton>
          </div>
        </div>
      </div>

      <!-- 表格区域 -->
      <div class="env-table-wrapper">
        <ElTable
          ref="tableRef"
          :data="tableData"
          v-loading="loading"
          class="env-table"
          border
          row-key="id"
          @selection-change="handleSelectionChange"
        >
          <ElTableColumn type="selection" width="50" />
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
          <ElTableColumn prop="device_sn" label="SN" min-width="100" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.device_sn || '-' }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="asset_number" label="资产编号" min-width="110" />
          <ElTableColumn prop="mark" label="标签" min-width="80" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.mark || '-' }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="status" label="状态" min-width="70" align="center">
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
                <!-- 虚拟设备不显示日志和远程按钮 -->
                <a
                  v-if="!row.is_virtual && !isMobileDevice(row.device_type) && row.status !== 'offline'"
                  class="env-link"
                  @click="handleViewLogs(row)"
                >
                  日志
                </a>
                <a
                  v-if="!row.is_virtual && (row.status === 'online' || row.status === 'using')"
                  class="env-link"
                  @click="handleDebug(row)"
                >
                  远程
                </a>
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
          <CodeEditor
            v-model="formData.extra_message_raw"
            language="json"
            :height="300"
            placeholder="JSON格式，按标签存储账号信息"
            :line-wrapping="true"
            :line-numbers="false"
          />
          <div v-if="jsonError" class="json-error">{{ jsonError }}</div>
        </ElFormItem>

        <ElFormItem label="备注">
          <ElInput
            v-model="formData.note"
            type="textarea"
            :rows="1"
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
    <LogDialogV2
      v-model:visible="logDialogVisible"
      :machine-id="logMachineId"
      :machine-ip="logMachineIp"
      :machine-port="logMachinePort"
    />

    <!-- 批量导入弹窗 -->
    <ElDialog
      v-model="importDialogVisible"
      title="批量导入虚拟设备"
      width="500px"
      :close-on-click-modal="false"
    >
      <div class="import-dialog-content">
        <div class="import-step">
          <div class="import-step-title">第一步：下载导入模板</div>
          <ElButton type="primary" @click="handleDownloadTemplate">
            下载模板
          </ElButton>
        </div>

        <div class="import-step">
          <div class="import-step-title">第二步：选择要导入的文件</div>
          <input
            type="file"
            accept=".xlsx"
            class="import-file-input"
            @change="handleFileChange"
          />
          <div v-if="importFile" class="import-file-name">
            已选择：{{ importFile.name }}
          </div>
        </div>

        <div v-if="importResult" class="import-result">
          <div class="import-result-title">导入结果</div>
          <div class="import-result-success">
            成功导入：{{ importResult.success_count }} 台
          </div>
          <div v-if="importResult.failed_items.length > 0" class="import-result-failed">
            <div>失败项：</div>
            <ul>
              <li v-for="item in importResult.failed_items" :key="item.row">
                第 {{ item.row }} 行：{{ item.reason }}
              </li>
            </ul>
          </div>
        </div>
      </div>

      <template #footer>
        <ElButton @click="importDialogVisible = false">关闭</ElButton>
        <ElButton
          type="primary"
          :loading="importLoading"
          :disabled="!importFile"
          @click="handleImport"
        >
          导入
        </ElButton>
      </template>
    </ElDialog>

    <!-- 批量命令弹窗 -->
    <BatchCommandDialog
      v-model:visible="batchCommandVisible"
      :selected-ids="Array.from(selectedIds)"
      :selected-machines="getSelectedMachines()"
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

/* 导入弹窗 */
.import-dialog-content {
  padding: 0 16px;
}

.import-step {
  margin-bottom: 24px;
}

.import-step-title {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.import-file-input {
  width: 100%;
  padding: 8px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 14px;
}

.import-file-name {
  margin-top: 8px;
  color: #52c41a;
  font-size: 13px;
}

.import-result {
  margin-top: 24px;
  padding: 16px;
  background: #f5f5f5;
  border-radius: 4px;
}

.import-result-title {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.import-result-success {
  color: #52c41a;
  font-size: 13px;
}

.import-result-failed {
  margin-top: 12px;
  color: #ff4d4f;
  font-size: 13px;
}

.import-result-failed ul {
  margin: 8px 0 0;
  padding-left: 20px;
}

.import-result-failed li {
  margin-bottom: 4px;
}
</style>