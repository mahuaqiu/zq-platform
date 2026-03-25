<script lang="ts" setup>
import type { EnvMachine } from '#/api/core/env-machine';

import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

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
  createEnvMachineApi,
  updateEnvMachineApi,
} from '#/api/core/env-machine';
import type { EnvMachineCreateParams, EnvMachineUpdateParams } from '#/api/core/env-machine';

import { NAMESPACE_MAP, DEVICE_TYPE_OPTIONS, STATUS_OPTIONS, isMobileDevice } from './types';

defineOptions({ name: 'EnvMachinePage' });

const route = useRoute();

// 数据
const tableData = ref<EnvMachine[]>([]);
const total = ref(0);
const loading = ref(false);
const currentPage = ref(1);
const pageSize = ref(20);

// 筛选条件
const searchForm = ref({
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
  device_type: 'windows',
  asset_number: '',
  ip: '',
  device_sn: '',
  note: '',
  mark: '',
  available: false,
});

// 从路由获取 namespace
const namespaceKey = computed(() => {
  const lastSegment = route.path.split('/').filter(Boolean).pop();
  return lastSegment || '';
});

const namespace = computed(() => {
  return NAMESPACE_MAP[namespaceKey.value] || '';
});

const isManual = computed(() => namespaceKey.value === 'manual');

const isMobileType = computed(() => isMobileDevice(formData.value.device_type as any));

// 加载数据
async function loadData() {
  if (!namespace.value) return;

  loading.value = true;
  try {
    const res = await getEnvMachineListApi({
      namespace: namespace.value,
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

// 新增
function handleCreate() {
  isEdit.value = false;
  editId.value = '';
  formData.value = {
    device_type: 'windows',
    asset_number: '',
    ip: '',
    device_sn: '',
    note: '',
    mark: '',
    available: false,
  };
  dialogVisible.value = true;
}

// 编辑
function handleEdit(row: EnvMachine) {
  isEdit.value = true;
  editId.value = row.id;
  formData.value = {
    device_type: row.device_type,
    asset_number: row.asset_number || '',
    ip: row.ip || '',
    device_sn: row.device_sn || '',
    note: row.note || '',
    mark: row.mark || '',
    available: row.available,
  };
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

// 提交表单
async function handleSubmit() {
  if (!formData.value.asset_number) {
    ElMessage.warning('请输入资产编号');
    return;
  }

  dialogLoading.value = true;
  try {
    if (isEdit.value) {
      // 编辑
      const updateData: EnvMachineUpdateParams = {
        asset_number: formData.value.asset_number,
        ip: formData.value.ip,
        device_sn: formData.value.device_sn,
        mark: formData.value.mark,
        available: formData.value.available,
        note: formData.value.note,
      };
      await updateEnvMachineApi(editId.value, updateData);
      ElMessage.success('更新成功');
    } else {
      // 新增
      const createData: EnvMachineCreateParams = {
        namespace: 'meeting_manual',
        device_type: formData.value.device_type,
        asset_number: formData.value.asset_number,
        ip: formData.value.ip,
        device_sn: formData.value.device_sn,
        note: formData.value.note,
      };
      await createEnvMachineApi(createData);
      ElMessage.success('创建成功');
    }
    dialogVisible.value = false;
    loadData();
  } catch (error: any) {
    const msg = error?.response?.data?.detail || '操作失败';
    ElMessage.error(msg);
  } finally {
    dialogLoading.value = false;
  }
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
    using: 'env-status-success',
    offline: 'env-status-warning',
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

// 监听路由变化
watch(namespaceKey, () => {
  currentPage.value = 1;
  loadData();
});

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
          <!-- 标准页面筛选 -->
          <template v-if="!isManual">
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
          </template>

          <!-- 手工使用页面筛选 -->
          <template v-else>
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
                style="width: 150px"
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
              <label class="env-search-label">备注</label>
              <ElInput
                v-model="searchForm.note"
                placeholder="搜索备注"
                clearable
                style="width: 150px"
              />
            </div>
          </template>

          <div class="env-search-buttons">
            <ElButton type="primary" @click="handleSearch">查询</ElButton>
            <ElButton @click="handleReset">重置</ElButton>
          </div>

          <!-- 新增按钮 -->
          <ElButton v-if="isManual" type="success" class="env-create-btn" @click="handleCreate">
            + 新增设备
          </ElButton>
        </div>
      </div>

      <!-- 表格区域 -->
      <div class="env-table-wrapper">
        <ElTable :data="tableData" v-loading="loading" class="env-table" border>
          <!-- 标准页面表格列 -->
          <template v-if="!isManual">
            <ElTableColumn prop="device_type" label="机器类型" min-width="90">
              <template #default="{ row }">
                {{ getDeviceTypeText(row.device_type) }}
              </template>
            </ElTableColumn>
            <ElTableColumn prop="ip" label="机器信息" min-width="150">
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
            <ElTableColumn prop="status" label="状态" min-width="70" align="center">
              <template #default="{ row }">
                <span :class="getStatusClass(row.status)">{{ getStatusText(row.status) }}</span>
              </template>
            </ElTableColumn>
            <ElTableColumn prop="available" label="是否启用" min-width="90" align="center">
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
            <ElTableColumn prop="version" label="版本" min-width="90">
              <template #default="{ row }">
                {{ row.version || '-' }}
              </template>
            </ElTableColumn>
            <ElTableColumn label="操作" min-width="100">
              <template #default="{ row }">
                <a class="env-link" @click="handleEdit(row)">编辑</a>
                <a class="env-link env-link-danger" @click="handleDelete(row)">删除</a>
              </template>
            </ElTableColumn>
          </template>

          <!-- 手工使用页面表格列 -->
          <template v-else>
            <ElTableColumn prop="device_type" label="机器类型" min-width="100">
              <template #default="{ row }">
                {{ getDeviceTypeText(row.device_type) }}
              </template>
            </ElTableColumn>
            <ElTableColumn prop="ip" label="机器信息" min-width="180">
              <template #default="{ row }">
                <code v-if="row.ip" class="env-code">{{ row.ip }}</code>
                <span v-else class="env-dash">-</span>
              </template>
            </ElTableColumn>
            <ElTableColumn prop="device_sn" label="SN" min-width="140">
              <template #default="{ row }">
                {{ row.device_sn || '-' }}
              </template>
            </ElTableColumn>
            <ElTableColumn prop="asset_number" label="资产编号" min-width="130" />
            <ElTableColumn prop="note" label="备注" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.note || '-' }}
              </template>
            </ElTableColumn>
            <ElTableColumn label="操作" min-width="120">
              <template #default="{ row }">
                <a class="env-link" @click="handleEdit(row)">编辑</a>
                <a class="env-link env-link-danger" @click="handleDelete(row)">删除</a>
              </template>
            </ElTableColumn>
          </template>
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

    <!-- 新增/编辑弹窗 -->
    <ElDialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑设备' : '新增设备'"
      width="500px"
      :close-on-click-modal="false"
    >
      <ElForm label-width="80px">
        <!-- 新增模式：机器类型 -->
        <ElFormItem v-if="!isEdit" label="机器类型" required>
          <ElSelect v-model="formData.device_type" style="width: 100%">
            <ElOption
              v-for="opt in DEVICE_TYPE_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </ElSelect>
        </ElFormItem>

        <!-- 资产编号 -->
        <ElFormItem label="资产编号" required>
          <ElInput v-model="formData.asset_number" placeholder="请输入资产编号，如 A2024582125" />
        </ElFormItem>

        <!-- Windows/Mac: IP地址 -->
        <ElFormItem v-if="!isMobileType" label="IP地址">
          <ElInput v-model="formData.ip" placeholder="请输入IP地址，如 192.168.0.200" />
        </ElFormItem>

        <!-- iOS/Android: SN -->
        <ElFormItem v-else label="SN">
          <ElInput v-model="formData.device_sn" placeholder="请输入设备SN号" />
        </ElFormItem>

        <!-- 编辑模式额外字段 -->
        <template v-if="isEdit">
          <ElFormItem label="标签">
            <ElInput v-model="formData.mark" placeholder="请输入标签" />
          </ElFormItem>
          <ElFormItem label="是否启用">
            <ElSelect v-model="formData.available" style="width: 100%">
              <ElOption label="是" :value="true" />
              <ElOption label="否" :value="false" />
            </ElSelect>
          </ElFormItem>
        </template>

        <!-- 备注 -->
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
  </Page>
</template>

<style scoped>
/* 搜索区域 */
.env-search-area {
  margin-bottom: 16px;
  padding: 16px;
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
  align-items: flex-end;
  gap: 8px;
}

.env-create-btn {
  background: #52c41a !important;
  border-color: #52c41a !important;
  color: #fff !important;
  font-weight: 500;
}

/* 表格区域 */
.env-table-wrapper {
  flex: 1;
  overflow: auto;
  background: #fff;
  padding: 16px;
  border-radius: 4px;
}

/* 表格支持水平滚动 */
.env-table-wrapper :deep(.el-table__body-wrapper) {
  overflow-x: auto;
}

/* 带边框表格样式 */
.env-table {
  --el-table-border-color: #e8e8e8;
  --el-table-header-bg-color: #fafafa;
  --el-table-tr-bg-color: #fff;
  --el-table-row-hover-bg-color: #fafafa;
  --el-table-text-color: #333;
  --el-table-header-text-color: #333;
}

/* 确保表格有外边框 */
.env-table :deep(.el-table__inner-wrapper::before) {
  display: none;
}

.env-table :deep(.el-table__border-left-patch) {
  background-color: #e8e8e8 !important;
}

/* 表头样式 */
.env-table :deep(th.el-table__cell) {
  background: #fafafa !important;
  padding: 12px 10px !important;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  border-color: #e8e8e8 !important;
  border-right: 1px solid #e8e8e8 !important;
  border-bottom: 1px solid #e8e8e8 !important;
  white-space: nowrap;
}

/* 表格单元格样式 */
.env-table :deep(td.el-table__cell) {
  padding: 12px 10px !important;
  font-size: 13px;
  color: #333;
  border-color: #e8e8e8 !important;
  border-right: 1px solid #e8e8e8 !important;
  border-bottom: 1px solid #e8e8e8 !important;
}

/* 机器信息 code 样式 */
.env-code {
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
}

.env-dash {
  color: #999;
}

/* 状态样式 */
.env-status-success {
  color: #52c41a;
}

.env-status-warning {
  color: #faad14;
}

.env-status-danger {
  color: #ff4d4f;
}

/* 操作链接 */
.env-link {
  color: #1890ff;
  cursor: pointer;
  margin-right: 12px;
  text-decoration: none;
}

.env-link:hover {
  text-decoration: underline;
}

.env-link-danger {
  color: #ff4d4f;
  margin-right: 0;
}

/* 分页 */
.env-pagination {
  display: flex;
  justify-content: flex-end;
  padding: 16px 0 0 0;
}
</style>