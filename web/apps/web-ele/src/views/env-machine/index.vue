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
  ElTag,
  ElText,
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

// 获取状态标签类型
function getStatusType(status: string) {
  const opt = STATUS_OPTIONS.find((o) => o.value === status);
  return opt?.type || 'info';
}

// 获取状态文本
function getStatusText(status: string) {
  const opt = STATUS_OPTIONS.find((o) => o.value === status);
  return opt?.label || status;
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
      <div class="mb-4 rounded bg-white p-4">
        <div class="flex flex-wrap gap-4">
          <!-- 标准页面筛选 -->
          <template v-if="!isManual">
            <ElSelect
              v-model="searchForm.device_type"
              placeholder="机器类型"
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
            <ElInput
              v-model="searchForm.ip"
              placeholder="机器信息"
              clearable
              style="width: 180px"
            />
            <ElInput
              v-model="searchForm.asset_number"
              placeholder="资产编号"
              clearable
              style="width: 150px"
            />
            <ElInput
              v-model="searchForm.mark"
              placeholder="标签"
              clearable
              style="width: 150px"
            />
            <ElSelect
              v-model="searchForm.available"
              placeholder="是否启用"
              clearable
              style="width: 120px"
            >
              <ElOption label="是" :value="true" />
              <ElOption label="否" :value="false" />
            </ElSelect>
          </template>

          <!-- 手工使用页面筛选 -->
          <template v-else>
            <ElSelect
              v-model="searchForm.device_type"
              placeholder="机器类型"
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
            <ElInput
              v-model="searchForm.ip"
              placeholder="机器信息"
              clearable
              style="width: 150px"
            />
            <ElInput
              v-model="searchForm.asset_number"
              placeholder="资产编号"
              clearable
              style="width: 150px"
            />
            <ElInput
              v-model="searchForm.note"
              placeholder="备注"
              clearable
              style="width: 150px"
            />
          </template>

          <div class="flex gap-2">
            <ElButton type="primary" @click="handleSearch">查询</ElButton>
            <ElButton @click="handleReset">重置</ElButton>
          </div>

          <!-- 新增按钮 -->
          <ElButton v-if="isManual" type="success" @click="handleCreate">
            + 新增设备
          </ElButton>
        </div>
      </div>

      <!-- 表格区域 -->
      <div class="flex-1 overflow-auto rounded bg-white">
        <ElTable :data="tableData" v-loading="loading" border stripe>
          <!-- 标准页面表格列 -->
          <template v-if="!isManual">
            <ElTableColumn prop="device_type" label="机器类型" width="100">
              <template #default="{ row }">
                <ElTag type="info">{{ getDeviceTypeText(row.device_type) }}</ElTag>
              </template>
            </ElTableColumn>
            <ElTableColumn prop="ip" label="机器信息" width="150">
              <template #default="{ row }">
                <code v-if="row.ip" class="rounded bg-gray-100 px-1">{{ row.ip }}</code>
                <span v-else class="text-gray-400">-</span>
              </template>
            </ElTableColumn>
            <ElTableColumn prop="device_sn" label="SN" width="140">
              <template #default="{ row }">
                {{ row.device_sn || '-' }}
              </template>
            </ElTableColumn>
            <ElTableColumn prop="asset_number" label="资产编号" width="120" />
            <ElTableColumn prop="mark" label="标签" width="120">
              <template #default="{ row }">
                {{ row.mark || '-' }}
              </template>
            </ElTableColumn>
            <ElTableColumn prop="status" label="状态" width="80" align="center">
              <template #default="{ row }">
                <ElTag :type="getStatusType(row.status)">
                  {{ getStatusText(row.status) }}
                </ElTag>
              </template>
            </ElTableColumn>
            <ElTableColumn prop="available" label="是否启用" width="90" align="center">
              <template #default="{ row }">
                <ElTag :type="row.available ? 'success' : 'danger'">
                  {{ row.available ? '是' : '否' }}
                </ElTag>
              </template>
            </ElTableColumn>
            <ElTableColumn prop="note" label="备注" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.note || '-' }}
              </template>
            </ElTableColumn>
            <ElTableColumn prop="extra_message" label="扩展信息" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">
                <template v-if="row.extra_message">
                  {{ JSON.stringify(row.extra_message) }}
                </template>
                <span v-else class="text-gray-400">-</span>
              </template>
            </ElTableColumn>
            <ElTableColumn prop="version" label="版本" width="100">
              <template #default="{ row }">
                {{ row.version || '-' }}
              </template>
            </ElTableColumn>
            <ElTableColumn label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <ElButton type="primary" link size="small" @click="handleEdit(row)">
                  编辑
                </ElButton>
                <ElButton type="danger" link size="small" @click="handleDelete(row)">
                  删除
                </ElButton>
              </template>
            </ElTableColumn>
          </template>

          <!-- 手工使用页面表格列 -->
          <template v-else>
            <ElTableColumn prop="device_type" label="机器类型" width="100">
              <template #default="{ row }">
                <ElTag type="info">{{ getDeviceTypeText(row.device_type) }}</ElTag>
              </template>
            </ElTableColumn>
            <ElTableColumn prop="ip" label="机器信息" width="150">
              <template #default="{ row }">
                <code v-if="row.ip" class="rounded bg-gray-100 px-1">{{ row.ip }}</code>
                <span v-else class="text-gray-400">-</span>
              </template>
            </ElTableColumn>
            <ElTableColumn prop="device_sn" label="SN" width="140">
              <template #default="{ row }">
                {{ row.device_sn || '-' }}
              </template>
            </ElTableColumn>
            <ElTableColumn prop="asset_number" label="资产编号" width="120" />
            <ElTableColumn prop="note" label="备注" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.note || '-' }}
              </template>
            </ElTableColumn>
            <ElTableColumn label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <ElButton type="primary" link size="small" @click="handleEdit(row)">
                  编辑
                </ElButton>
                <ElButton type="danger" link size="small" @click="handleDelete(row)">
                  删除
                </ElButton>
              </template>
            </ElTableColumn>
          </template>
        </ElTable>

        <!-- 分页 -->
        <div class="flex justify-end p-4">
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
code {
  font-family: 'Consolas', 'Monaco', monospace;
}
</style>