<script lang="ts" setup>
import type { EnvMachine } from '#/api/core/env-machine';

import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

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
                <a v-if="!isMobileDevice(row.device_type) && row.status !== 'offline'" class="env-link" @click="handleViewLogs(row)">日志</a>
                <a v-if="isMobileDevice(row.device_type) && row.status === 'online'" class="env-link" @click="handleDebug(row)">调试</a>
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